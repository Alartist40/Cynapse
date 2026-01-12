package main

import (
	"crypto/tls"
	"log"
	"net/http"
	"net/http/httputil"
	"net/url"
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
