package models

import (
	"fmt"
	"io"
	"net/http"
	"os"
	"path/filepath"
	"time"
)

// ProgressCallback is called periodically during a download.
type ProgressCallback func(downloaded, total int64, speedMBps float64)

// Download downloads a file from url to dest, reporting progress via callback.
func Download(url, dest string, callback ProgressCallback, authToken string) error {
	// Ensure parent directory exists
	if err := os.MkdirAll(filepath.Dir(dest), 0755); err != nil {
		return fmt.Errorf("creating directory: %w", err)
	}

	client := &http.Client{Timeout: 0} // no timeout for large files
	req, err := http.NewRequest("GET", url, nil)
	if err != nil {
		return fmt.Errorf("creating download request: %w", err)
	}
	if authToken != "" {
		req.Header.Set("Authorization", "Bearer "+authToken)
	}
	resp, err := client.Do(req)
	if err != nil {
		return fmt.Errorf("starting download: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return fmt.Errorf("download HTTP %d: %s", resp.StatusCode, url)
	}

	total := resp.ContentLength
	out, err := os.Create(dest + ".tmp")
	if err != nil {
		return fmt.Errorf("creating file: %w", err)
	}
	defer out.Close()

	var downloaded int64
	start := time.Now()
	lastUpdate := start
	buf := make([]byte, 64*1024)

	for {
		n, err := resp.Body.Read(buf)
		if n > 0 {
			if _, werr := out.Write(buf[:n]); werr != nil {
				_ = os.Remove(dest + ".tmp")
				return fmt.Errorf("writing file: %w", werr)
			}
			downloaded += int64(n)
		}
		if err == io.EOF {
			break
		}
		if err != nil {
			_ = os.Remove(dest + ".tmp")
			return fmt.Errorf("reading response: %w", err)
		}

		if callback != nil && time.Since(lastUpdate) > 500*time.Millisecond {
			elapsed := time.Since(start).Seconds()
			var speed float64
			if elapsed > 0 {
				speed = float64(downloaded) / elapsed / (1024 * 1024)
			}
			callback(downloaded, total, speed)
			lastUpdate = time.Now()
		}
	}

	if err := out.Close(); err != nil {
		_ = os.Remove(dest + ".tmp")
		return fmt.Errorf("closing file: %w", err)
	}

	if err := os.Rename(dest+".tmp", dest); err != nil {
		return fmt.Errorf("finalizing file: %w", err)
	}

	if callback != nil {
		callback(downloaded, total, 0)
	}
	return nil
}

// DownloadHF downloads a specific file from a HuggingFace model repo.
func DownloadHF(modelID, filename, dest string, callback ProgressCallback, authToken string) error {
	url := DownloadURL(modelID, filename)
	return Download(url, dest, callback, authToken)
}

// FormatBytes returns a human-readable byte string.
func FormatBytes(b int64) string {
	const unit = 1024
	if b < unit {
		return fmt.Sprintf("%d B", b)
	}
	div, exp := int64(unit), 0
	for n := b / unit; n >= unit; n /= unit {
		div *= unit
		exp++
	}
	return fmt.Sprintf("%.1f %cB", float64(b)/float64(div), "KMGTPE"[exp])
}

// FormatProgress returns a nice progress string.
func FormatProgress(downloaded, total int64, speedMBps float64) string {
	pct := float64(0)
	if total > 0 {
		pct = float64(downloaded) / float64(total) * 100
	}
	return fmt.Sprintf("%.1f%% (%s / %s) %.2f MB/s", pct, FormatBytes(downloaded), FormatBytes(total), speedMBps)
}
