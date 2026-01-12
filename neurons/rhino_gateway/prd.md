# PRD: Zero-Trust LLM Gateway (MVP)

**Vision**  
A single-binary reverse-proxy that adds TLS + API-key auth in front of any Ollama instance.  
Ship in one weekend; recruiters see “built secure LLM gateway, 150 lines Go”.

---

## 1. Core Job Stories
- **As** a hiring manager  
  **I** see TLS + key auth running locally  
  **So** I believe candidate understands production security basics.

- **As** you  
  **I** run `./gateway` and my Elara client still works with one extra header  
  **So** I can demo “secure by default” in interviews.

---

## 2. MVP Scope (Pareto cut)
| Feature | In MVP | Later |
|---------|--------|-------|
| TLS (self-signed) | ✅ | — |
| API-key header check | ✅ | — |
| Forward to Ollama | ✅ | — |
| JSON audit log | ✅ | — |
| Rate-limit, RBAC, prompt scan | ❌ | v2 |

---

## 3. Functional Spec
- **Listen**: `0.0.0.0:8443`  
- **Upstream**: `localhost:11434`  
- **Auth header**: `X-Api-Key: <key>`  
- **Keys source**: `keys.txt` (plain text, one per line)  
- **Log**: `gateway.log` (NDJSON: timestamp, key, path, prompt_tokens, response_tokens, status)  
- **Certs**: auto-generated `cert.pem / key.pem` if missing  
- **Binary size**: < 2 MB static build  
- **Zero config file needed for first run**

---

## 4. API Surface (identical to Ollama)
```
POST https://localhost:8443/api/chat
Headers:
  X-Api-Key: demo-key
Body:
  {"model":"llama3.2","messages":[{"role":"user","content":"hi"}],"stream":false}
```

---

## 5. Success Criteria
- `curl` without key → 403  
- `curl` with key → same response as direct Ollama call  
- Log file grows by exactly one JSON line per request  
- Build command: `go build -ldflags="-s -w"` → single binary

---

## 6. File Layout
```
llm-gateway/
├── main.go
├── cert.go      // generate self-signed
├── auth.go      // key lookup
├── log.go       // append JSON
├── keys.txt     // user supplied
├── cert.pem     // created on first run
├── key.pem
└── gateway.log
```

---

## 7. Build & Run
```bash
go mod init llm-gateway
go build -o gateway
./gateway
# → 2025-06-20 14:03:04 Gateway listening on :8443, upstream :11434
```

---

# Code Skeleton (Ready to Type)

## main.go
```go
package main

import (
	"crypto/tls"
	"io"
	"log"
	"net/http"
	"net/http/httputil"
	"net/url"
	"os"
)

var upstream *url.URL

func init() {
	var err error
	upstream, err = url.Parse("http://localhost:11434")
	if err != nil {
		log.Fatal(err)
	}
}

func main() {
	loadKeys()          // fills keyMap
	genCert()           // creates cert.pem/key.pem if absent

	proxy := httputil.NewSingleHostReverseProxy(upstream)

	director := proxy.Director
	proxy.Director = func(r *http.Request) {
		director(r)
		r.Host = upstream.Host
	}

	http.HandleFunc("/", func(w http.ResponseWriter, r *http.Request) {
		key := r.Header.Get("X-Api-Key")
		if !validKey(key) {
			http.Error(w, "Forbidden", http.StatusForbidden)
			logJSON(key, r.URL.Path, 0, 0, 403)
			return
		}
		// continue proxy
		rec := &responseRecorder{ResponseWriter: w, status: 200}
		proxy.ServeHTTP(rec, r)
		logJSON(key, r.URL.Path, 0, rec.size, rec.status)
	})

	srv := &http.Server{
		Addr: ":8443",
		TLSConfig: &tls.Config{
			Certificates: []tls.Certificate{mustLoadCert()},
		},
	}
	log.Println("Gateway listening on :8443")
	log.Fatal(srv.ListenAndServeTLS("", ""))
}
```

## auth.go
```go
var keyMap = map[string]bool{}

func loadKeys() {
	f, err := os.Open("keys.txt")
	if err != nil {
		log.Fatal("keys.txt missing")
	}
	defer f.Close()
	sc := bufio.NewScanner(f)
	for sc.Scan() {
		keyMap[sc.Text()] = true
	}
}

func validKey(k string) bool { return keyMap[k] }
```

## cert.go
```go
func genCert() {
	if _, err := os.Stat("cert.pem"); err == nil {
		return
	}
	priv, _ := rsa.GenerateKey(rand.Reader, 2048)
	template := x509.Certificate{
		SerialNumber: big.NewInt(1),
		NotBefore:    time.Now(),
		NotAfter:     time.Now().Add(365 * 24 * time.Hour),
		DNSNames:     []string{"localhost"},
	}
	certDER, _ := x509.CreateCertificate(rand.Reader, &template, &template, &priv.PublicKey, priv)
	certOut, _ := os.Create("cert.pem")
	pem.Encode(certOut, &pem.Block{Type: "CERTIFICATE", Bytes: certDER})
	keyOut, _ := os.Create("key.pem")
	pem.Encode(keyOut, &pem.Block{Type: "RSA PRIVATE KEY", Bytes: x509.MarshalPKCS1PrivateKey(priv)})
}
```

## log.go
```go
func logJSON(key, path string, promptTok, respTok, status int) {
	f, _ := os.OpenFile("gateway.log", os.O_APPEND|os.O_CREATE|os.O_WRONLY, 0644)
	defer f.Close()
	json.NewEncoder(f).Encode(map[string]interface{}{
		"time":    time.Now().Unix(),
		"key":     key,
		"path":    path,
		"prompt":  promptTok,
		"resp":    respTok,
		"status":  status,
	})
}
```

## responseRecorder.go
```go
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
```

---

# Next 2 Commands
```bash
echo "demo-key" > keys.txt
go run .   # test locally
```
Then `curl -k https://localhost:8443/api/chat -H "X-Api-Key: demo-key" -d '{"model":"llama3.2","messages":[{"role":"user","content":"hi"}]}'`

**Ship checklist**  
- `README.md` with one GIF, two curl examples, impact line “150-line Go binary adds TLS + auth to any Ollama endpoint”.  
- Release binary for Win/Mac/Linux.  
- Add GitHub Action to auto-build on tag.  
