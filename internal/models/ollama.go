package models

import (
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
)

// OllamaImporter handles importing downloaded GGUFs into Ollama.
type OllamaImporter struct {
	ollamaPath string
}

// NewOllamaImporter creates an importer, finding the ollama binary.
func NewOllamaImporter() *OllamaImporter {
	path, _ := exec.LookPath("ollama")
	return &OllamaImporter{ollamaPath: path}
}

// Available returns true if ollama is installed.
func (o *OllamaImporter) Available() bool {
	return o.ollamaPath != ""
}

// Import creates an Ollama model from a GGUF file.
// modelName is the desired Ollama model name (e.g. "cynapse-local-qwen").
func (o *OllamaImporter) Import(modelName, ggufPath string, modelType ModelType) error {
	if !o.Available() {
		return fmt.Errorf("ollama not found in PATH")
	}

	// Build a Modelfile
	modelfile := fmt.Sprintf("FROM %s\n", ggufPath)

	// Add vision projection if available for vision models
	if modelType == ModelTypeVision {
		// Look for mmproj in same directory
		dir := filepath.Dir(ggufPath)
		entries, err := os.ReadDir(dir)
		if err == nil {
			for _, entry := range entries {
				name := strings.ToLower(entry.Name())
				if strings.Contains(name, "mmproj") && strings.HasSuffix(name, ".gguf") {
					modelfile += fmt.Sprintf("\nFROM %s\nPARAMETER projector %s\n",
						filepath.Join(dir, entry.Name()),
						filepath.Join(dir, entry.Name()))
					break
				}
			}
		}
	}

	modelfile += `
PARAMETER temperature 0.7
PARAMETER top_p 0.9
PARAMETER top_k 40
`

	// Write Modelfile to temp location
	tmpDir := filepath.Dir(ggufPath)
	modelfilePath := filepath.Join(tmpDir, "Modelfile")
	if err := os.WriteFile(modelfilePath, []byte(modelfile), 0644); err != nil {
		return fmt.Errorf("writing Modelfile: %w", err)
	}

	// Run ollama create
	cmd := exec.Command(o.ollamaPath, "create", modelName, "-f", modelfilePath)
	cmd.Stdout = os.Stdout
	cmd.Stderr = os.Stderr
	if err := cmd.Run(); err != nil {
		return fmt.Errorf("ollama create: %w", err)
	}

	return nil
}

// Remove deletes an Ollama model.
func (o *OllamaImporter) Remove(modelName string) error {
	if !o.Available() {
		return fmt.Errorf("ollama not found in PATH")
	}
	cmd := exec.Command(o.ollamaPath, "rm", modelName)
	cmd.Stdout = os.Stdout
	cmd.Stderr = os.Stderr
	return cmd.Run()
}

// List returns all Ollama models.
func (o *OllamaImporter) List() ([]string, error) {
	if !o.Available() {
		return nil, fmt.Errorf("ollama not found in PATH")
	}
	cmd := exec.Command(o.ollamaPath, "list")
	out, err := cmd.Output()
	if err != nil {
		return nil, fmt.Errorf("ollama list: %w", err)
	}
	var names []string
	lines := strings.Split(string(out), "\n")
	for i, line := range lines {
		if i == 0 || strings.TrimSpace(line) == "" {
			continue // skip header
		}
		fields := strings.Fields(line)
		if len(fields) > 0 {
			names = append(names, fields[0])
		}
	}
	return names, nil
}

// SuggestOllamaName creates a safe Ollama model name from an HF model ID.
func SuggestOllamaName(hfModelID, quant string) string {
	name := strings.ReplaceAll(hfModelID, "/", "-")
	name = strings.ToLower(name)
	if quant != "" {
		name = name + "-" + strings.ToLower(quant)
	}
	// Ollama names should be simple
	name = strings.ReplaceAll(name, "_", "-")
	// Prefix with cynapse to avoid collisions
	return "cynapse-" + name
}
