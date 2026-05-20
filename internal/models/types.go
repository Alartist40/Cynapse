package models

import "time"

// ModelOrigin describes where a model came from.
type ModelOrigin string

const (
	OriginHuggingFace ModelOrigin = "huggingface"
	OriginLocal       ModelOrigin = "local"
	OriginOllama      ModelOrigin = "ollama"
)

// ModelType describes the capabilities of a model.
type ModelType string

const (
	ModelTypeText   ModelType = "text"
	ModelTypeVision ModelType = "vision"
	ModelTypeChat   ModelType = "chat"
)

// LocalModel is a record of a downloaded or imported model.
type LocalModel struct {
	ID        string      `json:"id"`         // Unique ID (e.g., "hf:Qwen/Qwen2.5-7B-Instruct-GGUF/qwen2.5-7b-instruct-q4_0.gguf")
	Name      string      `json:"name"`       // Display name
	Origin    ModelOrigin `json:"origin"`     // Where it came from
	Type      ModelType   `json:"type"`       // text | vision | chat
	Path      string      `json:"path"`       // Local filesystem path to the GGUF
	Size      int64       `json:"size"`       // Size in bytes
	Params    string      `json:"params"`     // e.g. "7B"
	Quant     string      `json:"quant"`      // e.g. "Q4_0"
	HFModelID string      `json:"hf_model_id,omitempty"` // Original HF model ID
	HFFile    string      `json:"hf_file,omitempty"`     // Original HF filename
	OllamaName string     `json:"ollama_name,omitempty"` // Ollama model name if imported
	VisionProj string     `json:"vision_proj,omitempty"` // Path to mmproj.gguf for vision models
	DownloadedAt time.Time `json:"downloaded_at"`
}

// Registry is the on-disk collection of local models.
type Registry struct {
	Models []LocalModel `json:"models"`
}
