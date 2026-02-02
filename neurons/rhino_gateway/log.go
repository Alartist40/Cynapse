package main

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"os"
	"time"
)

// maskAPIKey returns a masked version of the API key for safe logging.
// Only the first 4 characters are visible, followed by asterisks.
// This addresses the information disclosure vulnerability (CVSS 6.5).
func maskAPIKey(key string) string {
	if len(key) <= 4 {
		return "****"
	}
	return key[:4] + "****"
}

// hashAPIKey returns a SHA256 hash prefix for log correlation without exposure.
func hashAPIKey(key string) string {
	if key == "" {
		return "<empty>"
	}
	h := sha256.Sum256([]byte(key))
	return hex.EncodeToString(h[:])[:8]
}

func logJSON(key, path string, promptTok, respTok, status int) {
	f, _ := os.OpenFile("gateway.log", os.O_APPEND|os.O_CREATE|os.O_WRONLY, 0600)
	defer f.Close()
	json.NewEncoder(f).Encode(map[string]interface{}{
		"time":       time.Now().Unix(),
		"key_prefix": maskAPIKey(key),
		"key_hash":   hashAPIKey(key),
		"path":       path,
		"prompt":     promptTok,
		"resp":       respTok,
		"status":     status,
	})
}

