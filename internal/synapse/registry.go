package synapse

import (
	"crypto/sha256"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"time"

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

// manifestEntry is the on-disk format for synapse metadata
type manifestEntry struct {
	Synapse   Synapse `json:"synapse"`
	Installed int64   `json:"installed_at"`
	Source    string  `json:"source"`
}

// NewRegistry creates a new synapse registry
func NewRegistry() *Registry {
	return &Registry{
		synapses: make(map[string]*Synapse),
	}
}

// manifestPath returns the path to the synapses.json manifest
func manifestPath(dir string) string {
	return filepath.Join(dir, "synapses.json")
}

// loadManifest reads the synapses.json manifest if it exists
func loadManifest(dir string) (map[string]manifestEntry, error) {
	path := manifestPath(dir)
	data, err := os.ReadFile(path)
	if err != nil {
		if os.IsNotExist(err) {
			return make(map[string]manifestEntry), nil
		}
		return nil, err
	}
	var entries []manifestEntry
	if err := json.Unmarshal(data, &entries); err != nil {
		return nil, fmt.Errorf("parsing manifest: %w", err)
	}
	result := make(map[string]manifestEntry, len(entries))
	for _, e := range entries {
		result[e.Synapse.Name] = e
	}
	return result, nil
}

// saveManifest writes the synapses.json manifest
func saveManifest(dir string, entries map[string]manifestEntry) error {
	path := manifestPath(dir)
	var list []manifestEntry
	for _, e := range entries {
		list = append(list, e)
	}
	data, err := json.MarshalIndent(list, "", "  ")
	if err != nil {
		return err
	}
	return os.WriteFile(path, data, 0644)
}

// Discover scans a directory for synapse binaries
func (r *Registry) Discover(dir string) error {
	if _, err := os.Stat(dir); os.IsNotExist(err) {
		return nil // Directory doesn't exist yet, that's fine
	}

	// First, load the manifest
	manifest, err := loadManifest(dir)
	if err != nil {
		return fmt.Errorf("loading manifest: %w", err)
	}

	// Track which manifest entries were found on disk
	found := make(map[string]bool)

	entries, err := os.ReadDir(dir)
	if err != nil {
		return fmt.Errorf("reading synapse directory: %w", err)
	}

	for _, entry := range entries {
		if entry.IsDir() {
			continue
		}
		name := entry.Name()
		if name == "synapses.json" {
			continue
		}

		info, err := entry.Info()
		if err != nil {
			continue
		}

		// Skip non-executable files on Unix
		if runtime.GOOS != "windows" && info.Mode()&0111 == 0 {
			continue
		}

		synapsePath := filepath.Join(dir, name)

		// Check manifest first
		if m, ok := manifest[name]; ok {
			syn := m.Synapse
			syn.Command = synapsePath
			r.synapses[syn.Name] = &syn
			found[name] = true
			fmt.Printf("✓ Loaded synapse: %s v%s (manifest)\n", syn.Name, syn.Version)
			continue
		}

		// Fall back to --meta discovery
		meta, err := loadSynapseMetadata(synapsePath)
		if err != nil {
			continue // Not a valid synapse, skip
		}

		meta.Command = synapsePath
		r.synapses[meta.Name] = meta
		found[name] = true
		fmt.Printf("✓ Loaded synapse: %s v%s (discovered)\n", meta.Name, meta.Version)
	}

	// Clean up manifest entries for binaries that no longer exist
	changed := false
	for name := range manifest {
		if !found[name] {
			delete(manifest, name)
			changed = true
		}
	}
	if changed {
		_ = saveManifest(dir, manifest)
	}

	return nil
}

// List prints all installed synapses
func (r *Registry) List() {
	if len(r.synapses) == 0 {
		fmt.Println("No synapses installed.")
		fmt.Println()
		fmt.Println("Install synapses with:")
		fmt.Println("  cynapse synapse add <name> --path <binary>")
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

// Install downloads and installs a synapse from the registry.
// For local installation, use InstallFromPath instead.
func (r *Registry) Install(name, dir string) error {
	// Look up in known synapses
	known := getKnownSynapses()
	var target *Synapse
	for i := range known {
		if known[i].Name == name {
			target = &known[i]
			break
		}
	}
	if target == nil {
		return fmt.Errorf("unknown synapse: %s (run 'cynapse synapse search' to see available)", name)
	}

	return fmt.Errorf("synapse %q has no remote installer yet. Use:\n  cynapse synapse add %s --path <path-to-binary>\nOr build from source and register manually.", name, name)
}

// InstallFromPath installs a synapse from a local binary path.
// It copies the binary, makes it executable, verifies it responds to --meta,
// and records it in the manifest.
func (r *Registry) InstallFromPath(name, dir, sourcePath string) error {
	if _, err := os.Stat(sourcePath); os.IsNotExist(err) {
		return fmt.Errorf("source binary not found: %s", sourcePath)
	}

	// Ensure synapse directory exists
	if err := os.MkdirAll(dir, 0755); err != nil {
		return fmt.Errorf("creating synapse directory: %w", err)
	}

	destPath := filepath.Join(dir, name)

	// Copy binary
	src, err := os.Open(sourcePath)
	if err != nil {
		return fmt.Errorf("opening source: %w", err)
	}
	defer src.Close()

	// Remove existing if present
	_ = os.Remove(destPath)

	dst, err := os.OpenFile(destPath, os.O_CREATE|os.O_WRONLY|os.O_TRUNC, 0755)
	if err != nil {
		return fmt.Errorf("creating destination: %w", err)
	}
	defer dst.Close()

	if _, err := io.Copy(dst, src); err != nil {
		return fmt.Errorf("copying binary: %w", err)
	}
	if err := dst.Close(); err != nil {
		return fmt.Errorf("closing destination: %w", err)
	}
	if err := src.Close(); err != nil {
		return fmt.Errorf("closing source: %w", err)
	}

	// Try to load metadata from the copied binary
	meta, err := loadSynapseMetadata(destPath)
	if err != nil {
		// Binary doesn't support --meta; use known synapse metadata or generic
		known := getKnownSynapses()
		for _, k := range known {
			if k.Name == name {
				meta = &k
				break
			}
		}
		if meta == nil {
			meta = &Synapse{
				Name:        name,
				Version:     "unknown",
				Description: "Custom synapse",
				Author:      "user",
				Capabilities: []string{},
			}
		}
	}

	meta.Command = destPath
	r.synapses[meta.Name] = meta

	// Update manifest
	manifest, _ := loadManifest(dir)
	if manifest == nil {
		manifest = make(map[string]manifestEntry)
	}
	manifest[name] = manifestEntry{
		Synapse:   *meta,
		Installed: time.Now().Unix(),
		Source:    sourcePath,
	}
	if err := saveManifest(dir, manifest); err != nil {
		return fmt.Errorf("saving manifest: %w", err)
	}

	fmt.Printf("✓ Installed synapse: %s v%s\n", meta.Name, meta.Version)
	fmt.Printf("  Command: %s\n", destPath)
	return nil
}

// InstallFromURL downloads and installs a synapse from a remote URL with SHA-256 verification.
func (r *Registry) InstallFromURL(name, dir, url, expectedHash string) error {
	if err := os.MkdirAll(dir, 0755); err != nil {
		return fmt.Errorf("creating synapse directory: %w", err)
	}

	tmpPath := filepath.Join(dir, "."+name+".tmp")
	destPath := filepath.Join(dir, name)

	// Download
	resp, err := http.Get(url)
	if err != nil {
		return fmt.Errorf("downloading: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return fmt.Errorf("download failed: HTTP %d", resp.StatusCode)
	}

	out, err := os.Create(tmpPath)
	if err != nil {
		return fmt.Errorf("creating temp file: %w", err)
	}
	_, err = io.Copy(out, resp.Body)
	out.Close()
	if err != nil {
		_ = os.Remove(tmpPath)
		return fmt.Errorf("writing download: %w", err)
	}

	// Verify hash if provided
	if expectedHash != "" {
		if err := VerifyBinary(tmpPath, expectedHash); err != nil {
			_ = os.Remove(tmpPath)
			return err
		}
	}

	_ = os.Remove(destPath)
	if err := os.Rename(tmpPath, destPath); err != nil {
		_ = os.Remove(tmpPath)
		return fmt.Errorf("installing binary: %w", err)
	}
	_ = os.Chmod(destPath, 0755)

	// Discover metadata
	meta, err := loadSynapseMetadata(destPath)
	if err != nil {
		meta = &Synapse{
			Name:        name,
			Version:     "unknown",
			Description: "Downloaded synapse",
			Author:      "unknown",
		}
	}
	meta.Command = destPath
	r.synapses[meta.Name] = meta

	// Update manifest
	manifest, _ := loadManifest(dir)
	if manifest == nil {
		manifest = make(map[string]manifestEntry)
	}
	manifest[name] = manifestEntry{
		Synapse:   *meta,
		Installed: time.Now().Unix(),
		Source:    url,
	}
	_ = saveManifest(dir, manifest)

	fmt.Printf("✓ Installed synapse: %s v%s\n", meta.Name, meta.Version)
	return nil
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
		// Check if it's only in manifest
		manifest, _ := loadManifest(dir)
		if manifest != nil {
			if _, ok := manifest[name]; ok {
				delete(manifest, name)
				_ = saveManifest(dir, manifest)
			}
		}
		delete(r.synapses, name)
		fmt.Printf("✓ Removed synapse: %s\n", name)
		return nil
	}

	if err := os.Remove(path); err != nil {
		return fmt.Errorf("removing synapse: %w", err)
	}

	// Remove from manifest
	manifest, _ := loadManifest(dir)
	if manifest != nil {
		delete(manifest, name)
		_ = saveManifest(dir, manifest)
	}

	delete(r.synapses, name)
	fmt.Printf("✓ Removed synapse: %s\n", name)
	return nil
}

// Search queries the synapse registry
func (r *Registry) Search(query string) {
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
			fmt.Printf("     Install: cynapse synapse add %s --path <binary>\n", syn.Name)
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
			Version:     "0.8.0",
			Description: "CPU-optimized LLM inference engine for resource-constrained hardware",
			Author:      "Alartist40",
			Capabilities: []string{
				"llm_inference",
				"model_loading",
				"quantization",
				"speculative_decoding",
				"cpu_optimized",
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
