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
	"path/filepath"
	"strings"

	"github.com/Alartist40/cynapse/internal/config"
	"github.com/Alartist40/cynapse/internal/models"
)

// ─── Local Client ────────────────────────────────────────────────────────────

type localClient struct {
	*baseClient
	process *llamaProcess
	modelID string // local model ID or path
}

func (c *localClient) Provider() string { return "local" }
func (c *localClient) Close() error {
	if c.process != nil {
		return c.process.Stop()
	}
	return nil
}

// newLocalClient creates a local inference client backed by llama-server.
func newLocalClient(base *baseClient, cfg *config.LLMConfig, modelsDir string) (*localClient, error) {
	modelPath := cfg.Model

	// If model looks like a local ID, resolve it from registry
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

	proc := newLlamaProcess(modelPath)

	// Look for mmproj in same directory for vision support
	mmproj := ""
	dir := filepath.Dir(modelPath)
	entries, _ := os.ReadDir(dir)
	for _, e := range entries {
		name := strings.ToLower(e.Name())
		if strings.Contains(name, "mmproj") && strings.HasSuffix(name, ".gguf") {
			mmproj = filepath.Join(dir, e.Name())
			break
		}
	}

	binary := cfg.LlamaServerPath
	if err := proc.Start(binary, cfg.LocalGPULayers, cfg.LocalContextSize, cfg.LocalThreads, mmproj); err != nil {
		return nil, err
	}

	return &localClient{
		baseClient: base,
		process:    proc,
		modelID:    cfg.Model,
	}, nil
}

// ─── Chat ────────────────────────────────────────────────────────────────────

func (c *localClient) Chat(ctx context.Context, req *Request) (*Response, error) {
	type oMsg struct {
		Role    string `json:"role"`
		Content any    `json:"content"`
	}
	type oTool struct {
		Type     string `json:"type"`
		Function struct {
			Name        string         `json:"name"`
			Description string         `json:"description"`
			Parameters  map[string]any `json:"parameters"`
		} `json:"function"`
	}
	type oReq struct {
		Model       string   `json:"model"`
		MaxTokens   int      `json:"max_tokens,omitempty"`
		Temperature float64  `json:"temperature,omitempty"`
		Messages    []oMsg   `json:"messages"`
		Tools       []oTool  `json:"tools,omitempty"`
	}

	apiReq := oReq{Model: c.modelID, MaxTokens: req.MaxTokens, Temperature: req.Temperature}

	for _, m := range req.Messages {
		content := c.buildContent(m)
		apiReq.Messages = append(apiReq.Messages, oMsg{Role: string(m.Role), Content: content})
	}
	for _, t := range req.Tools {
		ot := oTool{Type: "function"}
		ot.Function.Name = t.Name
		ot.Function.Description = t.Description
		ot.Function.Parameters = t.Parameters
		apiReq.Tools = append(apiReq.Tools, ot)
	}

	body, err := json.Marshal(apiReq)
	if err != nil {
		return nil, err
	}

	httpReq, err := http.NewRequestWithContext(ctx, "POST", c.process.BaseURL()+"/v1/chat/completions", bytes.NewReader(body))
	if err != nil {
		return nil, err
	}
	httpReq.Header.Set("Content-Type", "application/json")

	resp, err := c.http.Do(httpReq)
	if err != nil {
		return nil, fmt.Errorf("local server request failed: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		b, _ := io.ReadAll(resp.Body)
		return nil, fmt.Errorf("local server HTTP %d: %s", resp.StatusCode, string(b))
	}

	var oResp struct {
		Choices []struct {
			Message struct {
				Content   string `json:"content"`
				ToolCalls []struct {
					ID       string `json:"id"`
					Type     string `json:"type"`
					Function struct {
						Name      string          `json:"name"`
						Arguments json.RawMessage `json:"arguments"`
					} `json:"function"`
				} `json:"tool_calls"`
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
		msg := oResp.Choices[0].Message
		result.Content = msg.Content
		for _, tc := range msg.ToolCalls {
			result.ToolCalls = append(result.ToolCalls, ToolCall{
				ID:        tc.ID,
				Name:      tc.Function.Name,
				Arguments: tc.Function.Arguments,
			})
		}
	}
	return result, nil
}

// ─── ChatStream ──────────────────────────────────────────────────────────────

func (c *localClient) ChatStream(ctx context.Context, req *Request) (<-chan string, <-chan error) {
	chunks := make(chan string, 10)
	errors := make(chan error, 1)

	go func() {
		defer close(chunks)
		defer close(errors)

		type oMsg struct {
			Role    string `json:"role"`
			Content any    `json:"content"`
		}
		type oTool struct {
			Type     string `json:"type"`
			Function struct {
				Name        string         `json:"name"`
				Description string         `json:"description"`
				Parameters  map[string]any `json:"parameters"`
			} `json:"function"`
		}
		type oReq struct {
			Model       string  `json:"model"`
			MaxTokens   int     `json:"max_tokens,omitempty"`
			Temperature float64 `json:"temperature,omitempty"`
			Messages    []oMsg  `json:"messages"`
			Tools       []oTool `json:"tools,omitempty"`
			Stream      bool    `json:"stream"`
		}

		apiReq := oReq{Model: c.modelID, MaxTokens: req.MaxTokens, Temperature: req.Temperature, Stream: true}

		for _, m := range req.Messages {
			content := c.buildContent(m)
			apiReq.Messages = append(apiReq.Messages, oMsg{Role: string(m.Role), Content: content})
		}
		for _, t := range req.Tools {
			ot := oTool{Type: "function"}
			ot.Function.Name = t.Name
			ot.Function.Description = t.Description
			ot.Function.Parameters = t.Parameters
			apiReq.Tools = append(apiReq.Tools, ot)
		}

		body, err := json.Marshal(apiReq)
		if err != nil {
			errors <- fmt.Errorf("marshaling request: %w", err)
			return
		}

		httpReq, err := http.NewRequestWithContext(ctx, "POST", c.process.BaseURL()+"/v1/chat/completions", bytes.NewReader(body))
		if err != nil {
			errors <- fmt.Errorf("creating request: %w", err)
			return
		}
		httpReq.Header.Set("Content-Type", "application/json")
		httpReq.Header.Set("Accept", "text/event-stream")

		resp, err := c.http.Do(httpReq)
		if err != nil {
			errors <- fmt.Errorf("local server request failed: %w", err)
			return
		}
		defer resp.Body.Close()

		if resp.StatusCode != http.StatusOK {
			bodyBytes, _ := io.ReadAll(resp.Body)
			errors <- fmt.Errorf("local server HTTP %d: %s", resp.StatusCode, string(bodyBytes))
			return
		}

		// Read SSE stream
		scanner := bufio.NewScanner(resp.Body)
		var toolCallBuffers []struct {
			ID   string
			Name string
			Args string
			Index int
		}
		var hasToolCalls bool

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
						Content   string `json:"content"`
						ToolCalls []struct {
							Index    int    `json:"index"`
							ID       string `json:"id"`
							Type     string `json:"type"`
							Function struct {
								Name      string `json:"name"`
								Arguments string `json:"arguments"`
							} `json:"function"`
						} `json:"tool_calls"`
					} `json:"delta"`
					FinishReason *string `json:"finish_reason"`
				} `json:"choices"`
			}
			if err := json.Unmarshal([]byte(data), &streamResp); err != nil {
				continue
			}
			if len(streamResp.Choices) == 0 {
				continue
			}

			delta := streamResp.Choices[0].Delta
			if len(delta.ToolCalls) > 0 {
				hasToolCalls = true
				for _, tc := range delta.ToolCalls {
					for len(toolCallBuffers) <= tc.Index {
						toolCallBuffers = append(toolCallBuffers, struct {
							ID    string
							Name  string
							Args  string
							Index int
						}{Index: len(toolCallBuffers)})
					}
					buf := &toolCallBuffers[tc.Index]
					if tc.ID != "" {
						buf.ID = tc.ID
					}
					if tc.Function.Name != "" {
						buf.Name = tc.Function.Name
					}
					buf.Args += tc.Function.Arguments
				}
				continue
			}

			if delta.Content != "" {
				select {
				case chunks <- delta.Content:
				case <-ctx.Done():
					errors <- ctx.Err()
					return
				}
			}
		}

		if err := scanner.Err(); err != nil {
			errors <- fmt.Errorf("reading stream: %w", err)
			return
		}

		if hasToolCalls && len(toolCallBuffers) > 0 {
			var toolCalls []ToolCall
			for _, buf := range toolCallBuffers {
				if buf.Name == "" {
					continue
				}
				toolCalls = append(toolCalls, ToolCall{
					ID:        buf.ID,
					Name:      buf.Name,
					Arguments: json.RawMessage(buf.Args),
				})
			}
			if len(toolCalls) > 0 {
				data, _ := json.Marshal(toolCalls)
				chunks <- string(data)
			}
		}
	}()

	return chunks, errors
}

// ─── Content Builder ─────────────────────────────────────────────────────────

// buildContent creates the message content for the OpenAI-compatible API.
// Supports text-only and multimodal (text + image) formats.
func (c *localClient) buildContent(m Message) any {
	// If no images or attachments, use simple string content
	if len(m.Images) == 0 && len(m.Attachments) == 0 {
		return m.Content
	}

	// Build multimodal content parts
	var parts []map[string]any

	// Start with the text content
	if m.Content != "" {
		parts = append(parts, map[string]any{
			"type": "text",
			"text": m.Content,
		})
	}

	// Add inline images
	for _, img := range m.Images {
		parts = append(parts, map[string]any{
			"type": "image_url",
			"image_url": map[string]string{
				"url": fmt.Sprintf("data:image/png;base64,%s", img),
			},
		})
	}

	// Add attachments
	for _, att := range m.Attachments {
		if att.Type == "image" {
			mime := att.MIME
			if mime == "" {
				mime = "image/png"
			}
			parts = append(parts, map[string]any{
				"type": "image_url",
				"image_url": map[string]string{
					"url": fmt.Sprintf("data:%s;base64,%s", mime, att.Content),
				},
			})
		} else if att.Type == "text" || att.Type == "pdf" {
			parts = append(parts, map[string]any{
				"type": "text",
				"text": fmt.Sprintf("\n[Attachment: %s]\n%s", att.Filename, att.Content),
			})
		}
	}

	if len(parts) == 1 {
		// Single part - extract the text directly for compatibility
		if text, ok := parts[0]["text"].(string); ok {
			return text
		}
	}

	return parts
}
