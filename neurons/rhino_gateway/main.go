// main.go - Optimized Zero-Trust Gateway v2.0
package main

import (
	"bufio"
	"context"
	"crypto/rand"
	"crypto/rsa"
	"crypto/sha256"
	"crypto/tls"
	"crypto/x509"
	"encoding/hex"
	"encoding/json"
	"encoding/pem"
	"fmt"
	"log"
	"math/big"
	"net"
	"net/http"
	"net/http/httputil"
	"net/url"
	"os"
	"os/signal"
	"sync"
	"syscall"
	"time"

	"golang.org/x/time/rate"
)

// Config holds runtime configuration
type Config struct {
	ListenAddr     string
	UpstreamURL    string
	KeysFile       string
	CertFile       string
	KeyFile        string
	RateLimit      rate.Limit
	RateBurst      int
	RequestTimeout time.Duration
}

// KeyStore manages API keys with hot-reload support
type KeyStore struct {
	path string
	keys map[string]bool
	mu   sync.RWMutex
}

func NewKeyStore(path string) (*KeyStore, error) {
	ks := &KeyStore{path: path, keys: make(map[string]bool)}
	err := ks.Reload()
	return ks, err
}

func (ks *KeyStore) Reload() error {
	f, err := os.Open(ks.path)
	if err != nil {
		return err
	}
	defer f.Close()

	newKeys := make(map[string]bool)
	sc := bufio.NewScanner(f)
	for sc.Scan() {
		key := sc.Text()
		if key != "" {
			newKeys[key] = true
		}
	}

	ks.mu.Lock()
	ks.keys = newKeys
	ks.mu.Unlock()
	return nil
}

func (ks *KeyStore) Valid(key string) bool {
	ks.mu.RLock()
	defer ks.mu.RUnlock()
	return ks.keys[key]
}

func (ks *KeyStore) Count() int {
	ks.mu.RLock()
	defer ks.mu.RUnlock()
	return len(ks.keys)
}

// Gateway orchestrates the secure proxy
type Gateway struct {
	config    *Config
	proxy     *httputil.ReverseProxy
	keys      *KeyStore
	limiter   *rate.Limiter
	logChan   chan AuditLog
	tlsConfig *tls.Config
}

type AuditLog struct {
	Timestamp  time.Time `json:"time"`
	KeyPrefix  string    `json:"key_prefix"`
	KeyHash    string    `json:"key_hash"`
	Path       string    `json:"path"`
	Method     string    `json:"method"`
	Status     int       `json:"status"`
	Size       int       `json:"size"`
	DurationMs int64     `json:"duration_ms"`
	ClientIP   string    `json:"client_ip"`
}

func main() {
	cfg := loadConfig()

	gw, err := NewGateway(cfg)
	if err != nil {
		log.Fatalf("Failed to initialize gateway: %v", err)
	}

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

	go gw.handleReload()
	go gw.logWorker()

	go func() {
		log.Printf("🦏 Rhino Gateway v2.0 listening on %s (upstream: %s)", cfg.ListenAddr, cfg.UpstreamURL)
		if err := server.ListenAndServeTLS("", ""); err != nil && err != http.ErrServerClosed {
			log.Fatalf("Server error: %v", err)
		}
	}()

	<-ctx.Done()
	log.Println("Shutting down gracefully...")

	shutdownCtx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()

	if err := server.Shutdown(shutdownCtx); err != nil {
		log.Printf("Shutdown error: %v", err)
	}
	gw.Shutdown()
}

func NewGateway(cfg *Config) (*Gateway, error) {
	upstream, err := url.Parse(cfg.UpstreamURL)
	if err != nil {
		return nil, fmt.Errorf("invalid upstream URL: %w", err)
	}

	keys, err := NewKeyStore(cfg.KeysFile)
	if err != nil {
		log.Printf("Warning: Failed to load keys from %s: %v", cfg.KeysFile, err)
	}

	if err := ensureCert(cfg.CertFile, cfg.KeyFile); err != nil {
		return nil, err
	}

	cert, err := tls.LoadX509KeyPair(cfg.CertFile, cfg.KeyFile)
	if err != nil {
		return nil, fmt.Errorf("failed to load certificates: %w", err)
	}

	tlsConfig := &tls.Config{
		Certificates: []tls.Certificate{cert},
		MinVersion:   tls.VersionTLS12,
	}

	proxy := httputil.NewSingleHostReverseProxy(upstream)

	gw := &Gateway{
		config:    cfg,
		proxy:     proxy,
		keys:      keys,
		limiter:   rate.NewLimiter(cfg.RateLimit, cfg.RateBurst),
		logChan:   make(chan AuditLog, 100),
		tlsConfig: tlsConfig,
	}

	return gw, nil
}

func (g *Gateway) Handler() http.Handler {
	mux := http.NewServeMux()
	mux.HandleFunc("/health", g.handleHealth)
	mux.HandleFunc("/", g.chain(
		g.securityHeaders,
		g.rateLimit,
		g.authenticate,
		g.auditLog,
		g.proxyRequest,
	))
	return mux
}

func (g *Gateway) chain(handlers ...func(http.HandlerFunc) http.HandlerFunc) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		final := handlers[len(handlers)-1](nil)
		for i := len(handlers) - 2; i >= 0; i-- {
			final = handlers[i](final)
		}
		final(w, r)
	}
}

func (g *Gateway) securityHeaders(next http.HandlerFunc) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Strict-Transport-Security", "max-age=63072000; includeSubDomains; preload")
		w.Header().Set("X-Content-Type-Options", "nosniff")
		w.Header().Set("X-Frame-Options", "DENY")
		w.Header().Set("X-XSS-Protection", "1; mode=block")
		if next != nil {
			next(w, r)
		}
	}
}

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

func (g *Gateway) authenticate(next http.HandlerFunc) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		key := r.Header.Get("X-Api-Key")
		if g.keys != nil && !g.keys.Valid(key) {
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
		ctx := context.WithValue(r.Context(), "api_key", key)
		if next != nil {
			next(w, r.WithContext(ctx))
		}
	}
}

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

func (g *Gateway) proxyRequest(w http.ResponseWriter, r *http.Request) {
	g.proxy.ServeHTTP(w, r)
}

func (g *Gateway) handleHealth(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	count := 0
	if g.keys != nil {
		count = g.keys.Count()
	}
	json.NewEncoder(w).Encode(map[string]interface{}{
		"status": "healthy",
		"keys_loaded": count,
	})
}

func (g *Gateway) logWorker() {
	ticker := time.NewTicker(5 * time.Second)
	defer ticker.Stop()
	var batch []AuditLog
	for {
		select {
		case entry, ok := <-g.logChan:
			if !ok {
				if len(batch) > 0 { g.flushLogs(batch) }
				return
			}
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
	if err != nil { return }
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
		if g.keys != nil {
			g.keys.Reload()
		}
	}
}

func (g *Gateway) Shutdown() {
	close(g.logChan)
}

// Helpers

func loadConfig() *Config {
	return &Config{
		ListenAddr:     ":8443",
		UpstreamURL:    "http://localhost:11434",
		KeysFile:       "keys.txt",
		CertFile:       "cert.pem",
		KeyFile:        "key.pem",
		RateLimit:      10,
		RateBurst:      20,
		RequestTimeout: 30 * time.Second,
	}
}

func maskKey(key string) string {
	if len(key) <= 4 { return "****" }
	return key[:4] + "****"
}

func hashKey(key string) string {
	h := sha256.New()
	h.Write([]byte(key))
	return hex.EncodeToString(h.Sum(nil))
}

func ensureCert(certFile, keyFile string) error {
	if _, err := os.Stat(certFile); err == nil {
		return nil
	}
	priv, _ := rsa.GenerateKey(rand.Reader, 2048)
	template := x509.Certificate{
		SerialNumber: big.NewInt(1),
		NotBefore:    time.Now(),
		NotAfter:     time.Now().Add(365 * 24 * time.Hour),
		DNSNames:     []string{"localhost"},
	}
	certDER, _ := x509.CreateCertificate(rand.Reader, &template, &template, &priv.PublicKey, priv)
	certOut, _ := os.Create(certFile)
	pem.Encode(certOut, &pem.Block{Type: "CERTIFICATE", Bytes: certDER})
	keyOut, _ := os.Create(keyFile)
	pem.Encode(keyOut, &pem.Block{Type: "RSA PRIVATE KEY", Bytes: x509.MarshalPKCS1PrivateKey(priv)})
	return nil
}

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
