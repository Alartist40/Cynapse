package models

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"time"
)

// Manager handles the local model registry and storage.
type Manager struct {
	modelsDir string
	registryPath string
}

// NewManager creates a model manager rooted at the given directory.
func NewManager(modelsDir string) *Manager {
	return &Manager{
		modelsDir:    modelsDir,
		registryPath: filepath.Join(modelsDir, "registry.json"),
	}
}

// EnsureDirs creates the models directory tree.
func (m *Manager) EnsureDirs() error {
	return os.MkdirAll(m.modelsDir, 0755)
}

// ModelsDir returns the root models directory.
func (m *Manager) ModelsDir() string {
	return m.modelsDir
}

// Load reads the registry from disk.
func (m *Manager) Load() (*Registry, error) {
	data, err := os.ReadFile(m.registryPath)
	if err != nil {
		if os.IsNotExist(err) {
			return &Registry{Models: []LocalModel{}}, nil
		}
		return nil, fmt.Errorf("reading registry: %w", err)
	}
	var reg Registry
	if err := json.Unmarshal(data, &reg); err != nil {
		return nil, fmt.Errorf("parsing registry: %w", err)
	}
	return &reg, nil
}

// Save writes the registry to disk.
func (m *Manager) Save(reg *Registry) error {
	data, err := json.MarshalIndent(reg, "", "  ")
	if err != nil {
		return fmt.Errorf("marshaling registry: %w", err)
	}
	if err := os.WriteFile(m.registryPath, data, 0644); err != nil {
		return fmt.Errorf("writing registry: %w", err)
	}
	return nil
}

// Add appends a model to the registry (replacing existing by ID).
func (m *Manager) Add(reg *Registry, model LocalModel) {
	for i, existing := range reg.Models {
		if existing.ID == model.ID {
			reg.Models[i] = model
			return
		}
	}
	reg.Models = append(reg.Models, model)
}

// Remove deletes a model from the registry and optionally its files.
func (m *Manager) Remove(reg *Registry, id string, deleteFiles bool) error {
	var found *LocalModel
	filtered := reg.Models[:0]
	for _, model := range reg.Models {
		if model.ID == id {
			found = &model
			continue
		}
		filtered = append(filtered, model)
	}
	reg.Models = filtered

	if found == nil {
		return fmt.Errorf("model %q not found", id)
	}

	if deleteFiles && found.Path != "" {
		_ = os.Remove(found.Path)
		if found.VisionProj != "" {
			_ = os.Remove(found.VisionProj)
		}
	}
	return nil
}

// Get returns a model by ID.
func (m *Manager) Get(reg *Registry, id string) (*LocalModel, error) {
	for i := range reg.Models {
		if reg.Models[i].ID == id {
			return &reg.Models[i], nil
		}
	}
	return nil, fmt.Errorf("model %q not found", id)
}

// PathFor returns the filesystem path where a downloaded HF file should live.
func (m *Manager) PathFor(hfModelID, filename string) string {
	safe := strings.ReplaceAll(hfModelID, "/", "_")
	return filepath.Join(m.modelsDir, safe, filename)
}

// GenerateID creates a stable local ID from HF model info.
func GenerateID(hfModelID, filename string) string {
	return fmt.Sprintf("hf:%s/%s", hfModelID, filename)
}

// ParseSize converts human-readable size strings like "4.5GB" or "7B" to bytes or param count.
func ParseSize(s string) int64 {
	s = strings.ToLower(strings.TrimSpace(s))
	var mult int64 = 1
	switch {
	case strings.HasSuffix(s, "gb"):
		mult = 1024 * 1024 * 1024
		s = strings.TrimSuffix(s, "gb")
	case strings.HasSuffix(s, "mb"):
		mult = 1024 * 1024
		s = strings.TrimSuffix(s, "mb")
	case strings.HasSuffix(s, "kb"):
		mult = 1024
		s = strings.TrimSuffix(s, "kb")
	}
	s = strings.TrimSpace(s)
	var v float64
	fmt.Sscanf(s, "%f", &v)
	return int64(v * float64(mult))
}

// DetectType guesses model capabilities from tags/filename.
func DetectType(tags []string, filename string) ModelType {
	lowerFile := strings.ToLower(filename)
	for _, tag := range tags {
		lt := strings.ToLower(tag)
		if strings.Contains(lt, "vision") || strings.Contains(lt, "vl") || strings.Contains(lt, "mmproj") {
			return ModelTypeVision
		}
	}
	if strings.Contains(lowerFile, "vision") || strings.Contains(lowerFile, "mmproj") {
		return ModelTypeVision
	}
	return ModelTypeChat
}

// DetectQuant extracts quantization from filename (e.g. Q4_K_M).
func DetectQuant(filename string) string {
	lower := strings.ToLower(filename)
	parts := strings.Split(lower, "-")
	for _, p := range parts {
		p = strings.TrimSuffix(p, ".gguf")
		if strings.HasPrefix(p, "q") || strings.HasPrefix(p, "iq") {
			return strings.ToUpper(p)
		}
	}
	return ""
}

// DetectParams extracts parameter count from model name (e.g. "7b", "13b").
func DetectParams(modelName string) string {
	lower := strings.ToLower(modelName)
	for _, suffix := range []string{"70b", "34b", "32b", "27b", "20b", "14b", "13b", "12b", "9b", "8b", "7b", "4b", "3b", "2b", "1b"} {
		if strings.Contains(lower, suffix) {
			return strings.ToUpper(suffix)
		}
	}
	return ""
}

// LocalModelFromHF creates a LocalModel record from HuggingFace search data.
func LocalModelFromHF(hfModelID string, file ModelFile, modelsDir string) LocalModel {
	filename := file.RFilename
	id := GenerateID(hfModelID, filename)
	path := filepath.Join(modelsDir, strings.ReplaceAll(hfModelID, "/", "_"), filename)

	return LocalModel{
		ID:           id,
		Name:         fmt.Sprintf("%s (%s)", hfModelID, filename),
		Origin:       OriginHuggingFace,
		Type:         DetectType(nil, filename),
		Path:         path,
		Size:         file.Size,
		Params:       DetectParams(hfModelID),
		Quant:        DetectQuant(filename),
		HFModelID:    hfModelID,
		HFFile:       filename,
		DownloadedAt: time.Time{},
	}
}
