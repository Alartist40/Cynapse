package synapse

import (
	"crypto/sha256"
	"encoding/json"
	"fmt"
	"io"
	"os"
	"os/exec"
	"path/filepath"

	"github.com/Alartist40/cynapse/internal/config"
)

// Registry manages synapse discovery and installation
type Registry struct {
	synapses map[string]*Synapse
}

// Synapse represents a CYNAPSE extension
type Synapse struct {
	Name         string            `json:"name"`
	Version      string            `json:"version"`
	Description  string            `json:"description"`
	Author       string            `json:"author"`
	Capabilities []string          `json:"capabilities"`
	Command      string            `json:"command"`
	Args         []string          `json:"args"`
	Env          map[string]string `json:"env"`
}

// NewRegistry creates a new synapse registry
func NewRegistry() *Registry {
	return &Registry{
		synapses: make(map[string]*Synapse),
	}
}

// Discover scans a directory for synapse binaries
func (r *Registry) Discover(dir string) error {
	if _, err := os.Stat(dir); os.IsNotExist(err) {
		return nil // Directory doesn't exist yet, that's fine
	}

	entries, err := os.ReadDir(dir)
	if err != nil {
		return fmt.Errorf("reading synapse directory: %w", err)
	}

	for _, entry := range entries {
		if entry.IsDir() {
			continue
		}

		// Check if executable
		info, err := entry.Info()
		if err != nil {
			continue
		}

		if info.Mode()&0111 == 0 {
			continue // Not executable
		}

		// Try to load synapse metadata
		synapsePath := filepath.Join(dir, entry.Name())
		meta, err := loadSynapseMetadata(synapsePath)
		if err != nil {
			// Not a valid synapse, skip
			continue
		}

		meta.Command = synapsePath
		r.synapses[meta.Name] = meta
		fmt.Printf("✓ Loaded synapse: %s v%s\n", meta.Name, meta.Version)
	}

	return nil
}

// List prints all installed synapses
func (r *Registry) List() {
	if len(r.synapses) == 0 {
		fmt.Println("No synapses installed.")
		fmt.Println()
		fmt.Println("Install synapses with:")
		fmt.Println("  cynapse synapse add <name>")
		fmt.Println()
		fmt.Println("Search available synapses:")
		fmt.Println("  cynapse synapse search")
		return
	}

	fmt.Println("Installed Synapses:")
	fmt.Println()
	for name, syn := range r.synapses {
		fmt.Printf("  📦 %s (v%s)\n", name, syn.Version)
		fmt.Printf("     %s\n", syn.Description)
		if len(syn.Capabilities) > 0 {
			fmt.Printf("     Capabilities: %v\n", syn.Capabilities)
		}
		fmt.Println()
	}
}

// Install downloads and installs a synapse
func (r *Registry) Install(name, dir string) error {
	// TODO: Implement proper synapse registry lookup
	// For now, prevent installation without verification
	return fmt.Errorf("synapse installation requires SHA-256 verification (not yet implemented)")
}

// VerifyBinary verifies SHA-256 checksum of a binary file
func VerifyBinary(filePath, expectedHash string) error {
	file, err := os.Open(filePath)
	if err != nil {
		return fmt.Errorf("opening binary: %w", err)
	}
	defer file.Close()

	hash := sha256.New()
	if _, err := io.Copy(hash, file); err != nil {
		return fmt.Errorf("hashing binary: %w", err)
	}

	computed := fmt.Sprintf("%x", hash.Sum(nil))
	if computed != expectedHash {
		return fmt.Errorf("checksum mismatch: expected %s, got %s", expectedHash, computed)
	}

	return nil
}

// Uninstall removes a synapse
func (r *Registry) Uninstall(name, dir string) error {
	path := filepath.Join(dir, name)

	if _, err := os.Stat(path); os.IsNotExist(err) {
		return fmt.Errorf("synapse not found: %s", name)
	}

	if err := os.Remove(path); err != nil {
		return fmt.Errorf("removing synapse: %w", err)
	}

	delete(r.synapses, name)
	fmt.Printf("✓ Removed synapse: %s\n", name)
	return nil
}

// Search queries the synapse registry
func (r *Registry) Search(query string) {
	// TODO: Fetch from online registry
	fmt.Printf("Searching for: %s\n", query)
	fmt.Println()
	fmt.Println("Available synapses:")
	fmt.Println()

	registry := getKnownSynapses()
	for _, syn := range registry {
		if query == "" || containsIgnoreCase(syn.Name, query) || containsIgnoreCase(syn.Description, query) {
			fmt.Printf("  📦 %s\n", syn.Name)
			fmt.Printf("     %s\n", syn.Description)
			if len(syn.Capabilities) > 0 {
				fmt.Printf("     Capabilities: %v\n", syn.Capabilities)
			}
			fmt.Printf("     Install: cynapse synapse add %s\n", syn.Name)
			fmt.Println()
		}
	}
}

// SearchAll lists all available synapses
func (r *Registry) SearchAll() {
	r.Search("")
}

// GetAll returns all loaded synapses
func (r *Registry) GetAll() []*Synapse {
	result := make([]*Synapse, 0, len(r.synapses))
	for _, syn := range r.synapses {
		result = append(result, syn)
	}
	return result
}

// ToMCPConfig converts synapse to MCP server config
func (s *Synapse) ToMCPConfig() config.MCPServer {
	return config.MCPServer{
		Name:    s.Name,
		Command: s.Command,
		Args:    s.Args,
		Env:     s.Env,
	}
}

// loadSynapseMetadata queries a synapse binary for its metadata
func loadSynapseMetadata(path string) (*Synapse, error) {
	// Execute with --meta flag
	cmd := exec.Command(path, "--meta")
	output, err := cmd.Output()
	if err != nil {
		return nil, fmt.Errorf("failed to query metadata: %w", err)
	}

	var syn Synapse
	if err := json.Unmarshal(output, &syn); err != nil {
		return nil, fmt.Errorf("invalid metadata format: %w", err)
	}

	return &syn, nil
}

// getKnownSynapses returns the list of officially supported synapses
func getKnownSynapses() []Synapse {
	return []Synapse{
		{
			Name:        "leafcutter",
			Version:     "2.0.0-beta",
			Description: "CPU-optimized LLM inference engine for resource-constrained hardware",
			Author:      "Alartist40",
			Capabilities: []string{
				"llm_inference",
				"model_loading",
				"quantization",
				"speculative_decoding",
			},
		},
		{
			Name:        "git-tools",
			Version:     "2.0.0-beta",
			Description: "Git repository management and analysis tools",
			Author:      "Alartist40",
			Capabilities: []string{
				"git_operations",
				"repo_analysis",
				"commit_history",
			},
		},
		{
			Name:        "web-automation",
			Version:     "2.0.0-beta",
			Description: "Browser automation and web scraping capabilities",
			Author:      "Alartist40",
			Capabilities: []string{
				"browser_control",
				"web_scraping",
				"screenshot",
			},
		},
		{
			Name:        "speedtest",
			Version:     "2.0.0-beta",
			Description: "LLM performance benchmarking and speed testing",
			Author:      "Alartist40",
			Capabilities: []string{
				"benchmarking",
				"performance_testing",
				"metrics",
			},
		},
	}
}

func containsIgnoreCase(s, substr string) bool {
	s = toLower(s)
	substr = toLower(substr)
	return contains(s, substr)
}

func toLower(s string) string {
	result := make([]byte, len(s))
	for i := 0; i < len(s); i++ {
		c := s[i]
		if c >= 'A' && c <= 'Z' {
			c = c + 32
		}
		result[i] = c
	}
	return string(result)
}

func contains(s, substr string) bool {
	return len(s) >= len(substr) && indexOf(s, substr) >= 0
}

func indexOf(s, substr string) int {
	for i := 0; i <= len(s)-len(substr); i++ {
		if s[i:i+len(substr)] == substr {
			return i
		}
	}
	return -1
}
