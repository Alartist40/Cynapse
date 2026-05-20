package llm

import (
	"bufio"
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"strings"
	"time"

	"github.com/Alartist40/cynapse/internal/config"
)

// ─── Types ───────────────────────────────────────────────────────────────────

type Role string

const (
	RoleSystem    Role = "system"
	RoleUser      Role = "user"
	RoleAssistant Role = "assistant"
	RoleTool      Role = "tool"
)

type Message struct {
	Role       Role        `json:"role"`
	Content    string      `json:"content"`
	ToolCallID string      `json:"tool_call_id,omitempty"`
	ToolCalls  []ToolCall  `json:"tool_calls,omitempty"`
	// Images contains base64-encoded images for multimodal models (Ollama format).
	Images []string `json:"images,omitempty"`
	// Attachments contains file attachments that should be included with this message.
	Attachments []Attachment `json:"attachments,omitempty"`
}

// Attachment represents a file attached to a message.
type Attachment struct {
	Type     string `json:"type"`     // image | text | pdf | binary
	Filename string `json:"filename"`
	MIME     string `json:"mime"`
	Content  string `json:"content"`  // text or base64
}

type ToolCall struct {
	ID        string          `json:"id"`
	Name      string          `json:"name"`
	Arguments json.RawMessage `json:"arguments"`
}

type ToolSchema struct {
	Name        string         `json:"name"`
	Description string         `json:"description"`
	Parameters  map[string]any `json:"parameters"`
}

type Request struct {
	SystemPrompt string
	Messages     []Message
	Tools        []ToolSchema
	MaxTokens    int
	Temperature  float64
}

type Response struct {
	Content   string
	ToolCalls []ToolCall
	Usage     Usage
}

type Usage struct {
	InputTokens  int
	OutputTokens int
}

// ─── Interface ───────────────────────────────────────────────────────────────

type Client interface {
	Chat(ctx context.Context, req *Request) (*Response, error)
	ChatStream(ctx context.Context, req *Request) (<-chan string, <-chan error)
	Provider() string
	Close() error
}

// ─── Model Discovery ─────────────────────────────────────────────────────────

// ListOllamaModels returns all available models from a running Ollama instance
func ListOllamaModels(baseURL string) ([]string, error) {
	if baseURL == "" {
		baseURL = "http://localhost:11434"
	}

	// Create HTTP client with timeout
	client := &http.Client{Timeout: 30 * time.Second}
	
	url := strings.TrimRight(baseURL, "/") + "/api/tags"
	resp, err := client.Get(url)
	if err != nil {
		return nil, fmt.Errorf("connecting to ollama: %w", err)
	}
	defer resp.Body.Close()

	var result struct {
		Models []struct {
			Name string `json:"name"`
		} `json:"models"`
	}
	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
		return nil, fmt.Errorf("parsing ollama response: %w", err)
	}

	var names []string
	for _, m := range result.Models {
		names = append(names, m.Name)
	}
	return names, nil
}

// ─── Factory ─────────────────────────────────────────────────────────────────

func New(cfg *config.LLMConfig) (Client, error) {
	base := &baseClient{
		http:       &http.Client{Timeout: 300 * time.Second},
		maxRetries: cfg.MaxRetries,
	}

	switch strings.ToLower(cfg.Provider) {
	case "anthropic":
		if cfg.AnthropicKey == "" {
			return nil, fmt.Errorf("ANTHROPIC_API_KEY not set")
		}
		return &anthropicClient{baseClient: base, apiKey: cfg.AnthropicKey, model: cfg.Model}, nil

	case "openai":
		if cfg.OpenAIKey == "" {
			return nil, fmt.Errorf("OPENAI_API_KEY not set")
		}
		return &openaiClient{baseClient: base, apiKey: cfg.OpenAIKey, model: cfg.Model}, nil

	case "gemini":
		if cfg.GeminiKey == "" {
			return nil, fmt.Errorf("GEMINI_API_KEY not set")
		}
		return &geminiClient{baseClient: base, apiKey: cfg.GeminiKey, model: cfg.Model}, nil

	case "ollama":
		baseURL := cfg.OllamaBaseURL
		if baseURL == "" {
			baseURL = "http://localhost:11434"
		}
		return &ollamaClient{baseClient: base, baseURL: baseURL, model: cfg.Model}, nil

	case "local":
		return newLocalClient(base, cfg, cfg.ModelsDir)

	default:
		return nil, fmt.Errorf("unknown LLM provider: %q (use ollama|anthropic|openai|gemini|local)", cfg.Provider)
	}
}

// ─── Base client (shared HTTP + retry logic) ─────────────────────────────────

type baseClient struct {
	http       *http.Client
	maxRetries int
}

func (b *baseClient) do(ctx context.Context, method, url string, headers map[string]string, body any) ([]byte, error) {
	var bodyReader io.Reader
	if body != nil {
		data, err := json.Marshal(body)
		if err != nil {
			return nil, err
		}
		bodyReader = bytes.NewReader(data)
	}

	var lastErr error
	for attempt := 0; attempt <= b.maxRetries; attempt++ {
		if attempt > 0 {
			select {
			case <-ctx.Done():
				return nil, ctx.Err()
			case <-time.After(time.Duration(attempt) * 2 * time.Second):
			}
		}

		req, err := http.NewRequestWithContext(ctx, method, url, bodyReader)
		if err != nil {
			return nil, err
		}

		req.Header.Set("Content-Type", "application/json")
		for k, v := range headers {
			req.Header.Set(k, v)
		}

		resp, err := b.http.Do(req)
		if err != nil {
			lastErr = err
			continue
		}
		defer resp.Body.Close()

		data, err := io.ReadAll(resp.Body)
		if err != nil {
			lastErr = err
			continue
		}

		if resp.StatusCode == 429 || resp.StatusCode >= 500 {
			lastErr = fmt.Errorf("HTTP %d: %s", resp.StatusCode, truncate(string(data), 200))
			// Reset body for retry
			if body != nil {
				b2, _ := json.Marshal(body)
				bodyReader = bytes.NewReader(b2)
			}
			continue
		}

		if resp.StatusCode >= 400 {
			return nil, fmt.Errorf("HTTP %d: %s", resp.StatusCode, truncate(string(data), 300))
		}

		return data, nil
	}

	return nil, fmt.Errorf("after %d retries: %w", b.maxRetries, lastErr)
}

// ─── Anthropic ───────────────────────────────────────────────────────────────

type anthropicClient struct {
	*baseClient
	apiKey string
	model  string
}

func (c *anthropicClient) Provider() string { return "anthropic" }
func (c *anthropicClient) Close() error   { return nil }

func (c *anthropicClient) Chat(ctx context.Context, req *Request) (*Response, error) {
	type aContent struct {
		Type      string `json:"type"`
		Text      string `json:"text,omitempty"`
		ID        string `json:"id,omitempty"`
		Name      string `json:"name,omitempty"`
		Input     any    `json:"input,omitempty"`
		ToolUseID string `json:"tool_use_id,omitempty"`
		Content   string `json:"content,omitempty"`
	}
	type aMsg struct {
		Role    string     `json:"role"`
		Content []aContent `json:"content"`
	}
	type aTool struct {
		Name        string         `json:"name"`
		Description string         `json:"description"`
		InputSchema map[string]any `json:"input_schema"`
	}
	type aReq struct {
		Model     string  `json:"model"`
		MaxTokens int     `json:"max_tokens"`
		System    string  `json:"system,omitempty"`
		Messages  []aMsg  `json:"messages"`
		Tools     []aTool `json:"tools,omitempty"`
	}

	apiReq := aReq{
		Model:     c.model,
		MaxTokens: req.MaxTokens,
		System:    req.SystemPrompt,
	}

	for _, m := range req.Messages {
		role := string(m.Role)
		var contents []aContent

		if m.Role == RoleTool {
			role = "user"
			contents = append(contents, aContent{
				Type:      "tool_result",
				ToolUseID: m.ToolCallID,
				Content:   m.Content,
			})
		} else if len(m.ToolCalls) > 0 {
			for _, tc := range m.ToolCalls {
				contents = append(contents, aContent{
					Type:  "tool_use",
					ID:    tc.ID,
					Name:  tc.Name,
					Input: tc.Arguments,
				})
			}
			if m.Content != "" {
				contents = append(contents, aContent{Type: "text", Text: m.Content})
			}
		} else {
			contents = append(contents, aContent{Type: "text", Text: m.Content})
		}

		apiReq.Messages = append(apiReq.Messages, aMsg{
			Role:    role,
			Content: contents,
		})
	}
	for _, t := range req.Tools {
		apiReq.Tools = append(apiReq.Tools, aTool{
			Name: t.Name, Description: t.Description, InputSchema: t.Parameters,
		})
	}

	headers := map[string]string{
		"x-api-key":         c.apiKey,
		"anthropic-version": "2023-06-01",
	}
	data, err := c.do(ctx, "POST", "https://api.anthropic.com/v1/messages", headers, apiReq)
	if err != nil {
		return nil, err
	}

	var aResp struct {
		Content []struct {
			Type  string          `json:"type"`
			Text  string          `json:"text"`
			ID    string          `json:"id"`
			Name  string          `json:"name"`
			Input json.RawMessage `json:"input"`
		} `json:"content"`
		Usage struct {
			InputTokens  int `json:"input_tokens"`
			OutputTokens int `json:"output_tokens"`
		} `json:"usage"`
	}
	if err := json.Unmarshal(data, &aResp); err != nil {
		return nil, err
	}

	result := &Response{Usage: Usage{InputTokens: aResp.Usage.InputTokens, OutputTokens: aResp.Usage.OutputTokens}}
	for _, c := range aResp.Content {
		if c.Type == "text" {
			result.Content += c.Text
		} else if c.Type == "tool_use" {
			result.ToolCalls = append(result.ToolCalls, ToolCall{ID: c.ID, Name: c.Name, Arguments: c.Input})
		}
	}
	return result, nil
}

// ─── OpenAI ──────────────────────────────────────────────────────────────────

type openaiClient struct {
	*baseClient
	apiKey string
	model  string
}

func (c *anthropicClient) ChatStream(ctx context.Context, req *Request) (<-chan string, <-chan error) {
	chunks := make(chan string, 10)
	errors := make(chan error, 1)

	go func() {
		defer close(chunks)
		defer close(errors)

		type aContent struct {
			Type      string `json:"type"`
			Text      string `json:"text,omitempty"`
			ID        string `json:"id,omitempty"`
			Name      string `json:"name,omitempty"`
			Input     any    `json:"input,omitempty"`
			ToolUseID string `json:"tool_use_id,omitempty"`
			Content   string `json:"content,omitempty"`
			PartialJSON string `json:"partial_json,omitempty"`
		}
		type aMsg struct {
			Role    string     `json:"role"`
			Content []aContent `json:"content"`
		}
		type aTool struct {
			Name        string         `json:"name"`
			Description string         `json:"description"`
			InputSchema map[string]any `json:"input_schema"`
		}
		type aReq struct {
			Model     string  `json:"model"`
			MaxTokens int     `json:"max_tokens"`
			System    string  `json:"system,omitempty"`
			Messages  []aMsg  `json:"messages"`
			Tools     []aTool `json:"tools,omitempty"`
			Stream    bool    `json:"stream"`
		}

		apiReq := aReq{
			Model:     c.model,
			MaxTokens: req.MaxTokens,
			System:    req.SystemPrompt,
			Stream:    true,
		}

		for _, m := range req.Messages {
			role := string(m.Role)
			var contents []aContent

			if m.Role == RoleTool {
				role = "user"
				contents = append(contents, aContent{
					Type:      "tool_result",
					ToolUseID: m.ToolCallID,
					Content:   m.Content,
				})
			} else if len(m.ToolCalls) > 0 {
				for _, tc := range m.ToolCalls {
					contents = append(contents, aContent{
						Type:  "tool_use",
						ID:    tc.ID,
						Name:  tc.Name,
						Input: tc.Arguments,
					})
				}
				if m.Content != "" {
					contents = append(contents, aContent{Type: "text", Text: m.Content})
				}
			} else {
				contents = append(contents, aContent{Type: "text", Text: m.Content})
			}

			apiReq.Messages = append(apiReq.Messages, aMsg{
				Role:    role,
				Content: contents,
			})
		}
		for _, t := range req.Tools {
			apiReq.Tools = append(apiReq.Tools, aTool{
				Name: t.Name, Description: t.Description, InputSchema: t.Parameters,
			})
		}

		body, err := json.Marshal(apiReq)
		if err != nil {
			errors <- fmt.Errorf("marshaling request: %w", err)
			return
		}

		httpReq, err := http.NewRequestWithContext(ctx, "POST", "https://api.anthropic.com/v1/messages", bytes.NewReader(body))
		if err != nil {
			errors <- fmt.Errorf("creating request: %w", err)
			return
		}
		httpReq.Header.Set("Content-Type", "application/json")
		httpReq.Header.Set("x-api-key", c.apiKey)
		httpReq.Header.Set("anthropic-version", "2023-06-01")
		httpReq.Header.Set("Accept", "text/event-stream")

		resp, err := c.http.Do(httpReq)
		if err != nil {
			errors <- fmt.Errorf("anthropic request failed: %w", err)
			return
		}
		defer resp.Body.Close()

		if resp.StatusCode != http.StatusOK {
			bodyBytes, _ := io.ReadAll(resp.Body)
			errors <- fmt.Errorf("anthropic HTTP %d: %s", resp.StatusCode, string(bodyBytes))
			return
		}

		// Read SSE stream line by line
		scanner := bufio.NewScanner(resp.Body)
		var toolCallBuffers []struct {
			ID   string
			Name string
			Args string
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

			var event struct {
				Type    string `json:"type"`
				Index   int    `json:"index"`
				ContentBlock *struct {
					Type string `json:"type"`
					ID   string `json:"id"`
					Name string `json:"name"`
				} `json:"content_block,omitempty"`
				Delta *struct {
					Text        string `json:"text,omitempty"`
					PartialJSON string `json:"partial_json,omitempty"`
					StopReason  string `json:"stop_reason,omitempty"`
				} `json:"delta,omitempty"`
			}

			if err := json.Unmarshal([]byte(data), &event); err != nil {
				continue
			}

			switch event.Type {
			case "content_block_delta":
				if event.Delta != nil {
					if event.Delta.Text != "" {
						select {
						case chunks <- event.Delta.Text:
						case <-ctx.Done():
							errors <- ctx.Err()
							return
						}
					}
					if event.Delta.PartialJSON != "" {
						hasToolCalls = true
						for len(toolCallBuffers) <= event.Index {
							toolCallBuffers = append(toolCallBuffers, struct {
								ID   string
								Name string
								Args string
							}{})
						}
						toolCallBuffers[event.Index].Args += event.Delta.PartialJSON
					}
				}
			case "content_block_start":
				if event.ContentBlock != nil && event.ContentBlock.Type == "tool_use" {
					hasToolCalls = true
					for len(toolCallBuffers) <= event.Index {
						toolCallBuffers = append(toolCallBuffers, struct {
							ID   string
							Name string
							Args string
						}{})
					}
					toolCallBuffers[event.Index].ID = event.ContentBlock.ID
					toolCallBuffers[event.Index].Name = event.ContentBlock.Name
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

func (c *openaiClient) Provider() string { return "openai" }
func (c *openaiClient) Close() error   { return nil }

func (c *openaiClient) Chat(ctx context.Context, req *Request) (*Response, error) {
	type oMsg struct {
		Role       string `json:"role"`
		Content    string `json:"content,omitempty"`
		ToolCallID string `json:"tool_call_id,omitempty"`
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
		MaxTokens   int     `json:"max_tokens"`
		Temperature float64 `json:"temperature"`
		Messages    []oMsg  `json:"messages"`
		Tools       []oTool `json:"tools,omitempty"`
	}

	apiReq := oReq{Model: c.model, MaxTokens: req.MaxTokens, Temperature: req.Temperature}

	if req.SystemPrompt != "" {
		apiReq.Messages = append(apiReq.Messages, oMsg{Role: "system", Content: req.SystemPrompt})
	}
	for _, m := range req.Messages {
		om := oMsg{Role: string(m.Role), Content: m.Content}
		if m.Role == RoleTool {
			om.ToolCallID = m.ToolCallID
		}
		apiReq.Messages = append(apiReq.Messages, om)
	}
	for _, t := range req.Tools {
		ot := oTool{Type: "function"}
		ot.Function.Name = t.Name
		ot.Function.Description = t.Description
		ot.Function.Parameters = t.Parameters
		apiReq.Tools = append(apiReq.Tools, ot)
	}

	headers := map[string]string{"Authorization": "Bearer " + c.apiKey}
	data, err := c.do(ctx, "POST", "https://api.openai.com/v1/chat/completions", headers, apiReq)
	if err != nil {
		return nil, err
	}

	var oResp struct {
		Choices []struct {
			Message struct {
				Content   string `json:"content"`
				ToolCalls []struct {
					ID       string `json:"id"`
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
	if err := json.Unmarshal(data, &oResp); err != nil {
		return nil, err
	}

	result := &Response{Usage: Usage{InputTokens: oResp.Usage.PromptTokens, OutputTokens: oResp.Usage.CompletionTokens}}
	if len(oResp.Choices) > 0 {
		msg := oResp.Choices[0].Message
		result.Content = msg.Content
		for _, tc := range msg.ToolCalls {
			result.ToolCalls = append(result.ToolCalls, ToolCall{
				ID: tc.ID, Name: tc.Function.Name, Arguments: tc.Function.Arguments,
			})
		}
	}
	return result, nil
}

// ─── Gemini ──────────────────────────────────────────────────────────────────

type geminiClient struct {
	*baseClient
	apiKey string
	model  string
}

func (c *geminiClient) Provider() string { return "gemini" }
func (c *geminiClient) Close() error   { return nil }

func (c *geminiClient) Chat(ctx context.Context, req *Request) (*Response, error) {
	type gPart struct {
		Text     string `json:"text,omitempty"`
		ToolCall *struct {
			Name string          `json:"name"`
			Args json.RawMessage `json:"args"`
		} `json:"functionCall,omitempty"`
		ToolResponse *struct {
			Name     string `json:"name"`
			Response any    `json:"response"`
		} `json:"functionResponse,omitempty"`
	}
	type gContent struct {
		Role  string  `json:"role"`
		Parts []gPart `json:"parts"`
	}
	type gTool struct {
		FunctionDeclarations []struct {
			Name        string         `json:"name"`
			Description string         `json:"description"`
			Parameters  map[string]any `json:"parameters"`
		} `json:"function_declarations"`
	}
	type gReq struct {
		SystemInstruction *gContent  `json:"systemInstruction,omitempty"`
		Contents          []gContent `json:"contents"`
		Tools             []gTool    `json:"tools,omitempty"`
	}

	apiReq := gReq{}
	if req.SystemPrompt != "" {
		apiReq.SystemInstruction = &gContent{Parts: []gPart{{Text: req.SystemPrompt}}}
	}
	for _, m := range req.Messages {
		role := string(m.Role)
		if role == "assistant" {
			role = "model"
		}
		parts := []gPart{}
		if m.Role == RoleTool {
			role = "function"
			parts = append(parts, gPart{ToolResponse: &struct {
				Name     string `json:"name"`
				Response any    `json:"response"`
			}{Name: m.ToolCallID, Response: map[string]any{"result": m.Content}}})
		} else if len(m.ToolCalls) > 0 {
			for _, tc := range m.ToolCalls {
				parts = append(parts, gPart{ToolCall: &struct {
					Name string          `json:"name"`
					Args json.RawMessage `json:"args"`
				}{Name: tc.Name, Args: tc.Arguments}})
			}
		} else {
			parts = append(parts, gPart{Text: m.Content})
		}
		apiReq.Contents = append(apiReq.Contents, gContent{Role: role, Parts: parts})
	}

	if len(req.Tools) > 0 {
		tool := gTool{}
		for _, t := range req.Tools {
			tool.FunctionDeclarations = append(tool.FunctionDeclarations, struct {
				Name        string         `json:"name"`
				Description string         `json:"description"`
				Parameters  map[string]any `json:"parameters"`
			}{Name: t.Name, Description: t.Description, Parameters: t.Parameters})
		}
		apiReq.Tools = append(apiReq.Tools, tool)
	}

	url := fmt.Sprintf("https://generativelanguage.googleapis.com/v1beta/models/%s:generateContent?key=%s", c.model, c.apiKey)
	data, err := c.do(ctx, "POST", url, nil, apiReq)
	if err != nil {
		return nil, err
	}

	var gResp struct {
		Candidates []struct {
			Content struct {
				Parts []struct {
					Text         string `json:"text"`
					FunctionCall *struct {
						Name string          `json:"name"`
						Args json.RawMessage `json:"args"`
					} `json:"functionCall"`
				} `json:"parts"`
			} `json:"content"`
		} `json:"candidates"`
	}
	if err := json.Unmarshal(data, &gResp); err != nil {
		return nil, err
	}

	result := &Response{}
	if len(gResp.Candidates) > 0 {
		for _, p := range gResp.Candidates[0].Content.Parts {
			if p.FunctionCall != nil {
				result.ToolCalls = append(result.ToolCalls, ToolCall{
					Name: p.FunctionCall.Name, Arguments: p.FunctionCall.Args,
				})
			} else {
				result.Content += p.Text
			}
		}
	}
	return result, nil
}

func (c *openaiClient) ChatStream(ctx context.Context, req *Request) (<-chan string, <-chan error) {
	chunks := make(chan string, 10)
	errors := make(chan error, 1)

	go func() {
		defer close(chunks)
		defer close(errors)

		type oMsg struct {
			Role       string `json:"role"`
			Content    string `json:"content,omitempty"`
			ToolCallID string `json:"tool_call_id,omitempty"`
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
			MaxTokens   int      `json:"max_tokens"`
			Temperature float64  `json:"temperature"`
			Messages    []oMsg   `json:"messages"`
			Tools       []oTool  `json:"tools,omitempty"`
			Stream      bool     `json:"stream"`
		}

		apiReq := oReq{Model: c.model, MaxTokens: req.MaxTokens, Temperature: req.Temperature, Stream: true}

		if req.SystemPrompt != "" {
			apiReq.Messages = append(apiReq.Messages, oMsg{Role: "system", Content: req.SystemPrompt})
		}
		for _, m := range req.Messages {
			om := oMsg{Role: string(m.Role), Content: m.Content}
			if m.Role == RoleTool {
				om.ToolCallID = m.ToolCallID
			}
			apiReq.Messages = append(apiReq.Messages, om)
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

		httpReq, err := http.NewRequestWithContext(ctx, "POST", "https://api.openai.com/v1/chat/completions", bytes.NewReader(body))
		if err != nil {
			errors <- fmt.Errorf("creating request: %w", err)
			return
		}
		httpReq.Header.Set("Content-Type", "application/json")
		httpReq.Header.Set("Authorization", "Bearer "+c.apiKey)
		httpReq.Header.Set("Accept", "text/event-stream")

		resp, err := c.http.Do(httpReq)
		if err != nil {
			errors <- fmt.Errorf("openai request failed: %w", err)
			return
		}
		defer resp.Body.Close()

		if resp.StatusCode != http.StatusOK {
			bodyBytes, _ := io.ReadAll(resp.Body)
			errors <- fmt.Errorf("openai HTTP %d: %s", resp.StatusCode, string(bodyBytes))
			return
		}

		// Read SSE stream line by line
		scanner := bufio.NewScanner(resp.Body)
		var toolCallBuffers []struct {
			ID       string
			Name     string
			Args     string
			Index    int
		}
		var hasToolCalls bool

		for scanner.Scan() {
			line := scanner.Text()

			// SSE format: "data: {...}" or "data: [DONE]"
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

			// Accumulate tool calls
			if len(delta.ToolCalls) > 0 {
				hasToolCalls = true
				for _, tc := range delta.ToolCalls {
					// Grow buffer if needed
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

		// If we accumulated tool calls, emit them as a JSON chunk (agent-compatible)
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

func (c *geminiClient) ChatStream(ctx context.Context, req *Request) (<-chan string, <-chan error) {
	chunks := make(chan string)
	errors := make(chan error, 1)
	close(chunks)
	errors <- fmt.Errorf("streaming not implemented for gemini")
	return chunks, errors
}

// ─── Ollama ──────────────────────────────────────────────────────────────────

type ollamaClient struct {
	*baseClient
	baseURL string
	model   string
}

func (c *ollamaClient) Provider() string { return "ollama" }
func (c *ollamaClient) Close() error   { return nil }

func (c *ollamaClient) Chat(ctx context.Context, req *Request) (*Response, error) {
	type oMsg struct {
		Role    string   `json:"role"`
		Content string   `json:"content"`
		Images  []string `json:"images,omitempty"`
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
		Model    string  `json:"model"`
		Messages []oMsg  `json:"messages"`
		Tools    []oTool `json:"tools,omitempty"`
		Stream   bool    `json:"stream"`
		Options  struct {
			NumPredict  int     `json:"num_predict,omitempty"`
			Temperature float64 `json:"temperature,omitempty"`
		} `json:"options"`
	}

	apiReq := oReq{Model: c.model, Stream: false}
	apiReq.Options.NumPredict = req.MaxTokens
	apiReq.Options.Temperature = req.Temperature

	if req.SystemPrompt != "" {
		apiReq.Messages = append(apiReq.Messages, oMsg{Role: "system", Content: req.SystemPrompt})
	}
	for _, m := range req.Messages {
		content := m.Content
		var images []string
		// Collect image attachments
		for _, att := range m.Attachments {
			if att.Type == "image" {
				images = append(images, att.Content)
			} else if att.Type == "text" || att.Type == "pdf" {
				content += "\n\n[Attachment: " + att.Filename + "]\n" + att.Content
			}
		}
		// Collect inline images
		images = append(images, m.Images...)
		apiReq.Messages = append(apiReq.Messages, oMsg{Role: string(m.Role), Content: content, Images: images})
	}
	for _, t := range req.Tools {
		ot := oTool{Type: "function"}
		ot.Function.Name = t.Name
		ot.Function.Description = t.Description
		ot.Function.Parameters = t.Parameters
		apiReq.Tools = append(apiReq.Tools, ot)
	}

	url := strings.TrimRight(c.baseURL, "/") + "/api/chat"
	data, err := c.do(ctx, "POST", url, nil, apiReq)
	if err != nil {
		return nil, err
	}

	var oResp struct {
		Message struct {
			Content   string `json:"content"`
			ToolCalls []struct {
				Function struct {
					Name      string          `json:"name"`
					Arguments json.RawMessage `json:"arguments"`
				} `json:"function"`
			} `json:"tool_calls"`
		} `json:"message"`
		PromptEvalCount int `json:"prompt_eval_count"`
		EvalCount       int `json:"eval_count"`
	}
	if err := json.Unmarshal(data, &oResp); err != nil {
		return nil, err
	}

	result := &Response{
		Content: oResp.Message.Content,
		Usage:   Usage{InputTokens: oResp.PromptEvalCount, OutputTokens: oResp.EvalCount},
	}
	for _, tc := range oResp.Message.ToolCalls {
		result.ToolCalls = append(result.ToolCalls, ToolCall{
			Name: tc.Function.Name, Arguments: tc.Function.Arguments,
		})
	}
	return result, nil
}

func (c *ollamaClient) ChatStream(ctx context.Context, req *Request) (<-chan string, <-chan error) {
	chunks := make(chan string, 10)
	errors := make(chan error, 1)

	go func() {
		defer close(chunks)
		defer close(errors)

		type oMsg struct {
			Role    string   `json:"role"`
			Content string   `json:"content"`
			Images  []string `json:"images,omitempty"`
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
			Model    string  `json:"model"`
			Messages []oMsg  `json:"messages"`
			Tools    []oTool `json:"tools,omitempty"`
			Stream   bool    `json:"stream"`
			Options  struct {
				NumPredict  int     `json:"num_predict,omitempty"`
				Temperature float64 `json:"temperature,omitempty"`
			} `json:"options"`
		}

		apiReq := oReq{Model: c.model, Stream: true}
		apiReq.Options.NumPredict = req.MaxTokens
		apiReq.Options.Temperature = req.Temperature

		if req.SystemPrompt != "" {
			apiReq.Messages = append(apiReq.Messages, oMsg{Role: "system", Content: req.SystemPrompt})
		}
		for _, m := range req.Messages {
			content := m.Content
			var images []string
			for _, att := range m.Attachments {
				if att.Type == "image" {
					images = append(images, att.Content)
				} else if att.Type == "text" || att.Type == "pdf" {
					content += "\n\n[Attachment: " + att.Filename + "]\n" + att.Content
				}
			}
			images = append(images, m.Images...)
			apiReq.Messages = append(apiReq.Messages, oMsg{Role: string(m.Role), Content: content, Images: images})
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

		httpReq, err := http.NewRequestWithContext(ctx, "POST", c.baseURL+"/api/chat", bytes.NewReader(body))
		if err != nil {
			errors <- fmt.Errorf("creating request: %w", err)
			return
		}
		httpReq.Header.Set("Content-Type", "application/json")

		resp, err := c.http.Do(httpReq)
		if err != nil {
			errors <- fmt.Errorf("ollama request failed: %w", err)
			return
		}
		defer resp.Body.Close()

		if resp.StatusCode != http.StatusOK {
			bodyBytes, _ := io.ReadAll(resp.Body)
			errors <- fmt.Errorf("ollama HTTP %d: %s", resp.StatusCode, string(bodyBytes))
			return
		}

		// Read streaming response line by line (NDJSON)
		scanner := bufio.NewScanner(resp.Body)
		var toolCalls []ToolCall

		for scanner.Scan() {
			line := scanner.Bytes()

			var streamResp struct {
				Message struct {
					Content   string `json:"content"`
					ToolCalls []struct {
						Function struct {
							Name      string          `json:"name"`
							Arguments json.RawMessage `json:"arguments"`
						} `json:"function"`
					} `json:"tool_calls"`
				} `json:"message"`
				Done bool `json:"done"`
			}

			if err := json.Unmarshal(line, &streamResp); err != nil {
				continue // Skip malformed lines
			}

			if len(streamResp.Message.ToolCalls) > 0 {
				for _, tc := range streamResp.Message.ToolCalls {
					toolCalls = append(toolCalls, ToolCall{
						Name: tc.Function.Name, Arguments: tc.Function.Arguments,
					})
				}
			}

			if streamResp.Message.Content != "" {
				select {
				case chunks <- streamResp.Message.Content:
				case <-ctx.Done():
					errors <- ctx.Err()
					return
				}
			}

			if streamResp.Done {
				if len(toolCalls) > 0 {
					data, _ := json.Marshal(toolCalls)
					chunks <- string(data)
				}
				return
			}
		}

		if err := scanner.Err(); err != nil {
			errors <- fmt.Errorf("reading stream: %w", err)
		}
	}()

	return chunks, errors
}

// ─── Helpers ─────────────────────────────────────────────────────────────────

func truncate(s string, n int) string {
	if len(s) <= n {
		return s
	}
	return s[:n] + "…"
}
