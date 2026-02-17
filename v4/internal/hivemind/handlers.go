package hivemind

import (
	"context"
	"fmt"
	"os"
	"strings"

	"github.com/Alartist40/cynapse/internal/core"
)

// OutputHandler prints outputs (equivalent to Python's OutputNode).
type OutputHandler struct{}

func (h *OutputHandler) Execute(ctx context.Context, inputs map[string]interface{}, config map[string]interface{}) (map[string]interface{}, error) {
	content := ""
	if v, ok := inputs["content"]; ok {
		content = fmt.Sprintf("%v", v)
	} else {
		content = fmt.Sprintf("%v", inputs)
	}

	format, _ := config["format"].(string)
	switch format {
	case "json":
		content = fmt.Sprintf("```json\n%s\n```", content)
	case "markdown":
		content = fmt.Sprintf("```\n%s\n```", content)
	}

	return map[string]interface{}{"output": content}, nil
}

// FileReaderHandler reads a file from disk (equivalent to Python's FileReaderNode).
type FileReaderHandler struct{}

func (h *FileReaderHandler) Execute(ctx context.Context, inputs map[string]interface{}, config map[string]interface{}) (map[string]interface{}, error) {
	path := ""
	if p, ok := config["path"].(string); ok {
		path = p
	} else if p, ok := inputs["path"].(string); ok {
		path = p
	}
	if path == "" {
		return nil, fmt.Errorf("file_reader: no path provided")
	}

	data, err := os.ReadFile(path)
	if err != nil {
		return nil, fmt.Errorf("file_reader: %w", err)
	}

	return map[string]interface{}{
		"content": string(data),
		"path":    path,
		"size":    len(data),
	}, nil
}

// TextChunkerHandler splits text into overlapping chunks (equivalent to Python's TextChunkerNode).
type TextChunkerHandler struct{}

func (h *TextChunkerHandler) Execute(ctx context.Context, inputs map[string]interface{}, config map[string]interface{}) (map[string]interface{}, error) {
	text := ""
	if t, ok := inputs["text"].(string); ok {
		text = t
	}

	chunkSize := 512
	if cs, ok := config["chunk_size"].(float64); ok {
		chunkSize = int(cs)
	}
	overlap := 50
	if ov, ok := config["overlap"].(float64); ok {
		overlap = int(ov)
	}

	var chunks []string
	runes := []rune(text)
	start := 0
	for start < len(runes) {
		end := start + chunkSize
		if end > len(runes) {
			end = len(runes)
		}
		chunks = append(chunks, string(runes[start:end]))
		start = end - overlap
		if start < 0 {
			start = 0
		}
	}

	return map[string]interface{}{
		"chunks": chunks,
		"count":  len(chunks),
	}, nil
}

// NeuronHandler dispatches tasks to registered neurons.
type NeuronHandler struct {
	engine *Engine
}

func (h *NeuronHandler) Execute(ctx context.Context, inputs map[string]interface{}, config map[string]interface{}) (map[string]interface{}, error) {
	neuronID, _ := config["neuron_id"].(string)
	operation, _ := config["operation"].(string)

	h.engine.mu.RLock()
	neuron, ok := h.engine.neurons[neuronID]
	h.engine.mu.RUnlock()

	if !ok {
		return nil, fmt.Errorf("neuron %s not registered", neuronID)
	}

	// Build params
	params := make(map[string]string)
	for k, v := range inputs {
		params[k] = fmt.Sprintf("%v", v)
	}

	task := core.Task{
		NeuronID:  neuronID,
		Operation: operation,
		Params:    params,
	}

	result, err := neuron.Execute(ctx, task)
	if err != nil {
		return nil, err
	}

	return map[string]interface{}{
		"output":     result.Output,
		"success":    result.Success,
		"confidence": result.Confidence,
	}, nil
}

// LLMHandler processes LLM requests (mock or via bridge).
type LLMHandler struct{}

func (h *LLMHandler) Execute(ctx context.Context, inputs map[string]interface{}, config map[string]interface{}) (map[string]interface{}, error) {
	prompt := ""
	if p, ok := inputs["prompt"].(string); ok {
		prompt = p
	}
	model, _ := config["model"].(string)
	if model == "" {
		model = "elara"
	}

	// TODO: Connect to Elara via gRPC bridge
	// For now, return a mock response
	_ = strings.TrimSpace(prompt)
	return map[string]interface{}{
		"text":  fmt.Sprintf("(LLM Mock — %s) Processed: %s", model, prompt),
		"model": model,
	}, nil
}
