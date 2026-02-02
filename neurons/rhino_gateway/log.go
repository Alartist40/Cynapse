package main

import (
	"encoding/json"
	"os"
	"time"
)

func logJSON(key, path string, promptTok, respTok, status int) {
	f, _ := os.OpenFile("gateway.log", os.O_APPEND|os.O_CREATE|os.O_WRONLY, 0644)
	defer f.Close()

	// Security: Mask the API key before logging to prevent information disclosure.
	maskedKey := "redacted"
	if len(key) > 4 {
		maskedKey = key[:4] + "****"
	}

	json.NewEncoder(f).Encode(map[string]interface{}{
		"time":    time.Now().Unix(),
		"key":     maskedKey,
		"path":    path,
		"prompt":  promptTok,
		"resp":    respTok,
		"status":  status,
	})
}
