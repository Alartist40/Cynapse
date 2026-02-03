// main.go - Optimized Zero-Trust Gateway
package main

import (
	"context"
	"crypto/tls"
	"crypto/x509"
	"fmt"
	"log"
	"net/http"
	"net/http/httputil"
	"net/url"
	"os"
	"os/signal"
	"syscall"
	"time"

	"golang.org/x/time/rate"
)

// Config holds runtime configuration
type Config struct {
	ListenAddr    string        `env:"RHINO_ADDR" envDefault:":8443"`
	UpstreamURL   string        `env:"RHINO_UPSTREAM" envDefault:"http://localhost:11434"`
	KeysFile      string        `env:"RHINO_KEYS" envDefault:"keys.txt"`
	CertFile      string        `env:"RHINO_CERT" envDefault:"cert.pem"`
	KeyFile       string        `env:"RHINO_KEY" envDefault:"key.pem"`
	RateLimit     rate.Limit    `env:"RHINO_RATE" envDefault:"10"` // requests per second
	RateBurst     int           `env:"RHINO_BURST" envDefault:"20"`
	RequestTimeout time.Duration `env:"RHINO_TIMEOUT" envDefault:"30s"`
}

// Gateway orchestrates the secure proxy
type Gateway struct {
	config     *Config
	proxy      *httputil.ReverseProxy
	keys       *KeyStore          // Hot-reloadable API keys
	limiter    *rate.Limiter      // Rate limiter per IP (map in production)
	logChan    chan AuditLog      // Async logging channel
	auditFile  *os.File
	tlsConfig  *tls.Config
}

// AuditLog non-blocking log entry
type AuditLog struct {
	Timestamp   time.Time `json:"time"`
	KeyPrefix   string    `json:"key_prefix"`
	KeyHash     string    `json:"key_hash"`
	Path        string    `json:"path"`
	Method      string    `json:"method"`
	Status      int       `json:"status"`
	Size        int       `json:"size"`
	DurationMs  int64     `json:"duration_ms"`
	ClientIP    string    `json:"client_ip"`
}

func main() {
	cfg := loadConfig()
	
	gw, err := NewGateway(cfg)
	if err != nil {
		log.Fatalf("Failed to initialize gateway: %v", err)
	}
	defer gw.Shutdown()

	// Setup graceful shutdown
	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()

	server := &http.Server{
		Addr:         cfg.ListenAddr,
		Handler:      gw.Handler(),
		TLSConfig:    gw.tlsConfig,
		ReadTimeout:  5 * time.Second,
		WriteTimeout: cfg.RequestTimeout,
		IdleTimeout:  120 * time.Second,
	}

	// Hot reload keys on SIGHUP
	go gw.handleReload()

	// Start async logger
	go gw.logWorker()

	// Start server in goroutine
	go func() {
		log.Printf("🦏 Rhino Gateway listening on %s (upstream: %s)", cfg.ListenAddr, cfg.UpstreamURL)
		if err := server.ListenAndServeTLS("", ""); err != nil && err != http.ErrServerClosed {
			log.Fatalf("Server error: %v", err)
		}
	}()

	// Wait for shutdown signal
	<-ctx.Done()
	log.Println("Shutting down gracefully...")
	
	shutdownCtx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()
	
	if err := server.Shutdown(shutdownCtx); err != nil {
		log.Printf("Shutdown error: %v", err)
	}
}

// NewGateway initializes the optimized gateway
func NewGateway(cfg *Config) (*Gateway, error) {
	// Parse upstream
	upstream, err := url.Parse(cfg.UpstreamURL)
	if err != nil {
		return nil, fmt.Errorf("invalid upstream URL: %w", err)
	}

	// Initialize key store with hot-reload
	keys, err := NewKeyStore(cfg.KeysFile)
	if err != nil {
		return nil, fmt.Errorf("failed to load keys: %w", err)
	}

	// Setup TLS with modern cipher suites
	tlsConfig := &tls.Config{
		MinVersion: tls.VersionTLS12,
		CurvePreferences: []tls.CurveID{
			tls.CurveP256,
			tls.X25519,
		},
		CipherSuites: []uint16{
			tls.TLS_ECDHE_ECDSA_WITH_AES_256_GCM_SHA384,
			tls.TLS_ECDHE_RSA_WITH_AES_256_GCM_SHA384,
			tls.TLS_ECDHE_ECDSA_WITH_CHACHA20_POLY1305,
			tls.TLS_ECDHE_RSA_WITH_CHACHA20_POLY1305,
			tls.TLS_ECDHE_ECDSA_WITH_AES_128_GCM_SHA256,
			tls.TLS_ECDHE_RSA_WITH_AES_128_GCM_SHA256,
		},
	}

	// Generate or load certificates
	if err := ensureCert(cfg.CertFile, cfg.KeyFile); err != nil {
		return nil, err
	}
	
	cert, err := tls.LoadX509KeyPair(cfg.CertFile, cfg.KeyFile)
	if err != nil {
		return nil, fmt.Errorf("failed to load certificates: %w", err)
	}
	tlsConfig.Certificates = []tls.Certificate{cert}

	// Create proxy with connection pooling
	proxy := httputil.NewSingleHostReverseProxy(upstream)
	proxy.Transport = &http.Transport{
		Proxy: http.ProxyFromEnvironment,
		DialContext: (&net.Dialer{
			Timeout:   5 * time.Second,
			KeepAlive: 30 * time.Second,
		}).DialContext,
		ForceAttemptHTTP2:     true,
		MaxIdleConns:          100,
		MaxIdleConnsPerHost:   10,
		IdleConnTimeout:       90 * time.Second,
		TLSHandshakeTimeout:   10 * time.Second,
		ExpectContinueTimeout: 1 * time.Second,
	}
	
	// Custom error handler for upstream failures
	proxy.ErrorHandler = func(w http.ResponseWriter, r *http.Request, err error) {
		log.Printf("Proxy error: %v", err)
		http.Error(w, "Bad Gateway", http.StatusBadGateway)
	}

	gw := &Gateway{
		config:    cfg,
		proxy:     proxy,
		keys:      keys,
		limiter:   rate.NewLimiter(cfg.RateLimit, cfg.RateBurst),
		logChan:   make(chan AuditLog, 100), // Buffered channel
		tlsConfig: tlsConfig,
	}

	return gw, nil
}

// Handler returns the configured http.Handler
func (g *Gateway) Handler() http.Handler {
	mux := http.NewServeMux()
	
	// Health check (no auth required)
	mux.HandleFunc("/health", g.handleHealth)
	
	// Metrics endpoint (prometheus format)
	mux.HandleFunc("/metrics", g.handleMetrics)
	
	// Main proxy handler with middleware chain
	mux.HandleFunc("/", g.chain(
		g.securityHeaders,
		g.rateLimit,
		g.authenticate,
		g.auditLog,
		g.proxyRequest,
	))
	
	return mux
}

// Middleware chain helper
func (g *Gateway) chain(handlers ...func(http.HandlerFunc) http.HandlerFunc) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		// Build chain in reverse
		final := handlers[len(handlers)-1](nil)
		for i := len(handlers) - 2; i >= 0; i-- {
			final = handlers[i](final)
		}
		final(w, r)
	}
}

// Middleware: Security headers
func (g *Gateway) securityHeaders(next http.HandlerFunc) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Strict-Transport-Security", "max-age=63072000; includeSubDomains; preload")
		w.Header().Set("X-Content-Type-Options", "nosniff")
		w.Header().Set("X-Frame-Options", "DENY")
		w.Header().Set("X-XSS-Protection", "1; mode=block")
		w.Header().Set("Content-Security-Policy", "default-src 'none'")
		if next != nil {
			next(w, r)
		}
	}
}

// Middleware: Rate limiting per IP (simplified, use Redis in production)
func (g *Gateway) rateLimit(next http.HandlerFunc) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		if !g.limiter.Allow() {
			http.Error(w, "Rate limit exceeded", http.StatusTooManyRequests)
			return
		}
		if next != nil {
			next(w, r)
		}
	}
}

// Middleware: API Key authentication
func (g *Gateway) authenticate(next http.HandlerFunc) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		key := r.Header.Get("X-Api-Key")
		if !g.keys.Valid(key) {
			g.logChan <- AuditLog{
				Timestamp: time.Now(),
				KeyPrefix: maskKey(key),
				KeyHash:   hashKey(key),
				Path:      r.URL.Path,
				Method:    r.Method,
				Status:    403,
				ClientIP:  r.RemoteAddr,
			}
			http.Error(w, "Forbidden", http.StatusForbidden)
			return
		}
		// Store valid key in context for logger
		ctx := context.WithValue(r.Context(), "api_key", key)
		if next != nil {
			next(w, r.WithContext(ctx))
		}
	}
}

// Middleware: Audit logging (async)
func (g *Gateway) auditLog(next http.HandlerFunc) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		start := time.Now()
		rec := &responseRecorder{ResponseWriter: w, status: http.StatusOK}
		
		if next != nil {
			next(rec, r)
		}
		
		key, _ := r.Context().Value("api_key").(string)
		
		g.logChan <- AuditLog{
			Timestamp:  time.Now(),
			KeyPrefix:  maskKey(key),
			KeyHash:    hashKey(key),
			Path:       r.URL.Path,
			Method:     r.Method,
			Status:     rec.status,
			Size:       rec.size,
			DurationMs: time.Since(start).Milliseconds(),
			ClientIP:   r.RemoteAddr,
		}
	}
}

// Handler: Proxy request
func (g *Gateway) proxyRequest(w http.ResponseWriter, r *http.Request) {
	g.proxy.ServeHTTP(w, r)
}

// Handler: Health check
func (g *Gateway) handleHealth(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]string{
		"status": "healthy",
		"keys_loaded": fmt.Sprintf("%d", g.keys.Count()),
	})
}

// Handler: Prometheus metrics
func (g *Gateway) handleMetrics(w http.ResponseWriter, r *http.Request) {
	// Simplified metrics - integrate prometheus client library for production
	w.Header().Set("Content-Type", "text/plain")
	fmt.Fprintf(w, "# HELP rhino_requests_total Total requests\n")
	fmt.Fprintf(w, "# TYPE rhino_requests_total counter\n")
	fmt.Fprintf(w, "rhino_requests_total %d\n", g.keys.Count())
}

// Async log worker (non-blocking I/O)
func (g *Gateway) logWorker() {
	ticker := time.NewTicker(5 * time.Second)
	defer ticker.Stop()
	
	var batch []AuditLog
	
	for {
		select {
		case entry := <-g.logChan:
			batch = append(batch, entry)
			if len(batch) >= 10 {
				g.flushLogs(batch)
				batch = nil
			}
		case <-ticker.C:
			if len(batch) > 0 {
				g.flushLogs(batch)
				batch = nil
			}
		}
	}
}

func (g *Gateway) flushLogs(batch []AuditLog) {
	f, err := os.OpenFile("gateway.log", os.O_APPEND|os.O_CREATE|os.O_WRONLY, 0600)
	if err != nil {
		log.Printf("Failed to open log: %v", err)
		return
	}
	defer f.Close()
	
	enc := json.NewEncoder(f)
	for _, entry := range batch {
		enc.Encode(entry)
	}
}

func (g *Gateway) handleReload() {
	sig := make(chan os.Signal, 1)
	signal.Notify(sig, syscall.SIGHUP)
	
	for range sig {
		log.Println("Reloading keys...")
		if err := g.keys.Reload(); err != nil {
			log.Printf("Failed to reload keys: %v", err)
		} else {
			log.Printf("Keys reloaded: %d active", g.keys.Count())
		}
	}
}

func (g *Gateway) Shutdown() {
	close(g.logChan)
	if g.auditFile != nil {
		g.auditFile.Close()
	}
}

// Helper functions (maskKey, hashKey, ensureCert, loadConfig, etc.)
// ... [implementation continues]

type responseRecorder struct {
	http.ResponseWriter
	status int
	size   int
}

func (r *responseRecorder) WriteHeader(code int) {
	r.status = code
	r.ResponseWriter.WriteHeader(code)
}

func (r *responseRecorder) Write(b []byte) (int, error) {
	n, err := r.ResponseWriter.Write(b)
	r.size += n
	return n, err
}