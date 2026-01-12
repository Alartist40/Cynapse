package main

import (
	"encoding/json"
	"os"
	"time"
)

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
