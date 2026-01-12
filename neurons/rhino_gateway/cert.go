package main

import (
	"crypto/rand"
	"crypto/rsa"
	"crypto/tls"
	"crypto/x509"
	"encoding/pem"
	"log"
	"math/big"
	"os"
	"time"
)

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

func mustLoadCert() tls.Certificate {
	cert, err := tls.LoadX509KeyPair("cert.pem", "key.pem")
	if err != nil {
		log.Fatal(err)
	}
	return cert
}
