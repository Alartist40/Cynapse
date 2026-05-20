package llm

import (
	"bufio"
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"time"

	"github.com/Alartist40/cynapse/internal/config"
	"github.com/Alartist40/cynapse/internal/models"
)

// ─── Leafcutter Client ───────────────────────────────────────────────────────
//
// Spawns `leafcutter server` as a subprocess and communicates via its
// OpenAI-compatible HTTP API. This replaces llama-server with Leafcutter's
// unified binary, giving faster startup and lower memory overhead.
//
// The leafcutter binary is auto-detected from PATH, or can be set explicitly
// via config.LLM.LeafcutterPath.

type leafcutterClient struct {
	*baseClient
	cmd     *exec.Cmd
	baseURL string
	modelID string
}

func (c *leafcutterClient) Provider() string { return "leafcutter" }

func (c *leafcutterClient) Close() error {
	if c.cmd != nil && c.cmd.Process != nil {
		_ = c.cmd.Process.Kill()
		_ = c.cmd.Wait()
	}
	return nil
}

// newLeafcutterClient creates a local inference client backed by leafcutter server.
func newLeafcutterClient(base *baseClient, cfg *config.LLMConfig, modelsDir string) (*leafcutterClient, error) {
	modelPath := cfg.Model

	// Resolve model ID to path via registry
	if strings.HasPrefix(modelPath, "hf:") || !filepath.IsAbs(modelPath) {
		mgr := models.NewManager(modelsDir)
		reg, err := mgr.Load()
		if err == nil {
			for _, m := range reg.Models {
				if m.ID == modelPath || filepath.Base(m.Path) == modelPath || m.HFFile == modelPath {
					modelPath = m.Path
					break
				}
			}
		}
	}

	if modelPath == "" {
		return nil, fmt.Errorf("no local model path specified. Set model to a local model ID or absolute GGUF path")
	}
	if _, err := os.Stat(modelPath); err != nil {
		return nil, fmt.Errorf("model file not found: %s", modelPath)
	}

	// Find leafcutter binary
	leafcutterBin := cfg.LeafcutterPath
	if leafcutterBin == "" {
		leafcutterBin = findLeafcutter()
	}
	if leafcutterBin == "" {
		return nil, fmt.Errorf("leafcutter binary not found in PATH. Install from https://github.com/Alartist40/LeafcutterLLM")
	}

	// Find a free port
	port, err := findFreePort(18081)
	if err != nil {
		return nil, fmt.Errorf("finding free port: %w", err)
	}

	// Spawn leafcutter server
	args := []string{
		"server",
		"--model", modelPath,
		"--port", fmt.Sprintf("%d", port),
	}
	if cfg.LocalThreads > 0 {
		args = append(args, "--threads", fmt.Sprintf("%d", cfg.LocalThreads))
	}

	cmd := exec.Command(leafcutterBin, args...)
	cmd.Stdout = os.Stdout
	cmd.Stderr = os.Stderr
	cmd.Env = os.Environ()

	// Set LD_LIBRARY_PATH for llama.cpp shared libs if leafcutter was installed via install.sh
	if home, err := os.UserHomeDir(); err == nil {
		llamaLibPath := filepath.Join(home, ".leafcutter", "llama.cpp", "build", "bin")
		if _, err := os.Stat(llamaLibPath); err == nil {
			cmd.Env = append(cmd.Env, "LD_LIBRARY_PATH="+llamaLibPath+":"+os.Getenv("LD_LIBRARY_PATH"))
		}
	}

	if err := cmd.Start(); err != nil {
		return nil, fmt.Errorf("starting leafcutter server: %w", err)
	}

	baseURL := fmt.Sprintf("http://127.0.0.1:%d", port)

	// Wait for health endpoint
	if err := waitForServer(baseURL+"/health", 30*time.Second); err != nil {
		_ = cmd.Process.Kill()
		return nil, fmt.Errorf("leafcutter server failed to start: %w", err)
	}

	return &leafcutterClient{
		baseClient: base,
		cmd:        cmd,
		baseURL:    baseURL,
		modelID:    cfg.Model,
	}, nil
}

// ─── Chat ────────────────────────────────────────────────────────────────────

func (c *leafcutterClient) Chat(ctx context.Context, req *Request) (*Response, error) {
	type oMsg struct {
		Role    string `json:"role"`
		Content string `json:"content"`
	}
	type oReq struct {
		Model       string  `json:"model"`
		MaxTokens   int     `json:"max_tokens,omitempty"`
		Temperature float64 `json:"temperature,omitempty"`
		Messages    []oMsg  `json:"messages"`
	}

	apiReq := oReq{Model: c.modelID, MaxTokens: req.MaxTokens, Temperature: req.Temperature}

	if req.SystemPrompt != "" {
		apiReq.Messages = append(apiReq.Messages, oMsg{Role: "system", Content: req.SystemPrompt})
	}
	for _, m := range req.Messages {
		apiReq.Messages = append(apiReq.Messages, oMsg{Role: string(m.Role), Content: m.Content})
	}

	body, err := json.Marshal(apiReq)
	if err != nil {
		return nil, err
	}

	httpReq, err := http.NewRequestWithContext(ctx, "POST", c.baseURL+"/v1/chat/completions", bytes.NewReader(body))
	if err != nil {
		return nil, err
	}
	httpReq.Header.Set("Content-Type", "application/json")

	resp, err := c.http.Do(httpReq)
	if err != nil {
		return nil, fmt.Errorf("leafcutter request failed: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		b, _ := io.ReadAll(resp.Body)
		return nil, fmt.Errorf("leafcutter HTTP %d: %s", resp.StatusCode, string(b))
	}

	var oResp struct {
		Choices []struct {
			Message struct {
				Content string `json:"content"`
			} `json:"message"`
		} `json:"choices"`
		Usage struct {
			PromptTokens     int `json:"prompt_tokens"`
			CompletionTokens int `json:"completion_tokens"`
		} `json:"usage"`
	}
	if err := json.NewDecoder(resp.Body).Decode(&oResp); err != nil {
		return nil, err
	}

	result := &Response{Usage: Usage{InputTokens: oResp.Usage.PromptTokens, OutputTokens: oResp.Usage.CompletionTokens}}
	if len(oResp.Choices) > 0 {
		result.Content = oResp.Choices[0].Message.Content
	}
	return result, nil
}

// ─── ChatStream ──────────────────────────────────────────────────────────────

func (c *leafcutterClient) ChatStream(ctx context.Context, req *Request) (<-chan string, <-chan error) {
	chunks := make(chan string, 10)
	errors := make(chan error, 1)

	go func() {
		defer close(chunks)
		defer close(errors)

		type oMsg struct {
			Role    string `json:"role"`
			Content string `json:"content"`
		}
		type oReq struct {
			Model       string  `json:"model"`
			MaxTokens   int     `json:"max_tokens,omitempty"`
			Temperature float64 `json:"temperature,omitempty"`
			Messages    []oMsg  `json:"messages"`
			Stream      bool    `json:"stream"`
		}

		apiReq := oReq{Model: c.modelID, MaxTokens: req.MaxTokens, Temperature: req.Temperature, Stream: true}

		if req.SystemPrompt != "" {
			apiReq.Messages = append(apiReq.Messages, oMsg{Role: "system", Content: req.SystemPrompt})
		}
		for _, m := range req.Messages {
			apiReq.Messages = append(apiReq.Messages, oMsg{Role: string(m.Role), Content: m.Content})
		}

		body, err := json.Marshal(apiReq)
		if err != nil {
			errors <- fmt.Errorf("marshaling request: %w", err)
			return
		}

		httpReq, err := http.NewRequestWithContext(ctx, "POST", c.baseURL+"/v1/chat/completions", bytes.NewReader(body))
		if err != nil {
			errors <- fmt.Errorf("creating request: %w", err)
			return
		}
		httpReq.Header.Set("Content-Type", "application/json")
		httpReq.Header.Set("Accept", "text/event-stream")

		resp, err := c.http.Do(httpReq)
		if err != nil {
			errors <- fmt.Errorf("leafcutter request failed: %w", err)
			return
		}
		defer resp.Body.Close()

		if resp.StatusCode != http.StatusOK {
			bodyBytes, _ := io.ReadAll(resp.Body)
			errors <- fmt.Errorf("leafcutter HTTP %d: %s", resp.StatusCode, string(bodyBytes))
			return
		}

		scanner := bufio.NewScanner(resp.Body)
		for scanner.Scan() {
			line := scanner.Text()
			if !strings.HasPrefix(line, "data: ") {
				continue
			}
			data := strings.TrimPrefix(line, "data: ")
			if data == "[DONE]" {
				break
			}

			var streamResp struct {
				Choices []struct {
					Delta struct {
						Content string `json:"content"`
					} `json:"delta"`
				} `json:"choices"`
			}
			if err := json.Unmarshal([]byte(data), &streamResp); err != nil {
				continue
			}
			if len(streamResp.Choices) == 0 {
				continue
			}

			content := streamResp.Choices[0].Delta.Content
			if content != "" {
				select {
				case chunks <- content:
				case <-ctx.Done():
					errors <- ctx.Err()
					return
				}
			}
		}

		if err := scanner.Err(); err != nil {
			errors <- fmt.Errorf("reading stream: %w", err)
		}
	}()

	return chunks, errors
}

// ─── Helpers ─────────────────────────────────────────────────────────────────

func findLeafcutter() string {
	// Check PATH
	if path, err := exec.LookPath("leafcutter"); err == nil {
		return path
	}
	// Check common install locations
	home, _ := os.UserHomeDir()
	candidates := []string{
		filepath.Join(home, ".local", "bin", "leafcutter"),
		filepath.Join(home, ".leafcutter", "LeafcutterLLM", "rust", "target", "release", "leafcutter"),
		"/usr/local/bin/leafcutter",
		"./leafcutter",
	}
	for _, c := range candidates {
		if _, err := os.Stat(c); err == nil {
			return c
		}
	}
	return ""
}



func waitForServer(url string, timeout time.Duration) error {
	client := &http.Client{Timeout: 2 * time.Second}
	deadline := time.Now().Add(timeout)
	for time.Now().Before(deadline) {
		resp, err := client.Get(url)
		if err == nil {
			resp.Body.Close()
			if resp.StatusCode == http.StatusOK {
				return nil
			}
		}
		time.Sleep(200 * time.Millisecond)
	}
	return fmt.Errorf("timed out waiting for server at %s", url)
}
