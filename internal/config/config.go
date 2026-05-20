package config

import (
	"fmt"
	"os"
	"path/filepath"
	"strings"

	"gopkg.in/yaml.v3"
)

// ─── Root Config ─────────────────────────────────────────────────────────────

type Config struct {
	Gateway GatewayConfig `yaml:"gateway"`
	LLM     LLMConfig     `yaml:"llm"`
	Memory  MemoryConfig  `yaml:"memory"`
	Tools   ToolsConfig   `yaml:"tools"`
	MCP     MCPConfig     `yaml:"mcp"`
	Models  ModelsConfig  `yaml:"models"`
}

// ─── Gateway ─────────────────────────────────────────────────────────────────

type GatewayConfig struct {
	Address   string `yaml:"address"`    // e.g. "0.0.0.0:8080"
	AuthToken string `yaml:"auth_token"` // optional Bearer token for security
}

// ─── LLM ─────────────────────────────────────────────────────────────────────

type LLMConfig struct {
	// Provider: "ollama" | "anthropic" | "openai" | "gemini" | "local"
	Provider string `yaml:"provider"`

	// Model name — provider-specific
	//   ollama:    "qwen2.5", "llama3.2", "mistral", etc.
	//   anthropic: "claude-sonnet-4-20250514"
	//   openai:    "gpt-4o", "gpt-4o-mini"
	//   gemini:    "gemini-2.0-flash", "gemini-pro"
	//   local:     path to GGUF or local model ID
	Model string `yaml:"model"`

	// API keys (can also be set via env vars)
	AnthropicKey string `yaml:"anthropic_key"` // or ANTHROPIC_API_KEY
	OpenAIKey    string `yaml:"openai_key"`    // or OPENAI_API_KEY
	GeminiKey    string `yaml:"gemini_key"`    // or GEMINI_API_KEY

	// Ollama base URL (default: http://localhost:11434)
	OllamaBaseURL string `yaml:"ollama_base_url"`

	// Local model settings (provider: "local" | "leafcutter")
	LlamaServerPath  string `yaml:"llama_server_path"`  // path to llama-server binary
	LeafcutterPath   string `yaml:"leafcutter_path"`    // path to leafcutter binary (auto-detected if empty)
	LocalGPULayers   int    `yaml:"local_gpu_layers"`   // -ngl (default: 0)
	LocalContextSize int    `yaml:"local_context_size"` // -c (default: 4096)
	LocalThreads     int    `yaml:"local_threads"`      // -t (default: auto)
	ModelsDir        string `yaml:"models_dir"`         // for resolving local model IDs

	// Generation params
	MaxTokens   int     `yaml:"max_tokens"`   // default 4096
	Temperature float64 `yaml:"temperature"`  // default 0.7
	MaxRetries  int     `yaml:"max_retries"`  // default 3
}

// ─── Memory ──────────────────────────────────────────────────────────────────

type MemoryConfig struct {
	// Where to store persona markdown files per device
	PersonaPath string `yaml:"persona_path"` // default: "./data/persona"

	// Where to store JSONL session logs
	SessionsPath string `yaml:"sessions_path"` // default: "./data/sessions"

	// SQLite database for searchable memory
	DBPath string `yaml:"db_path"` // default: "./data/memory.db"

	// SQLite database for knowledge graph
	DendriteDBPath string `yaml:"dendrite_db_path"` // default: "./data/dendrite.db"

	// Path to default persona templates (copied when a new device connects)
	DefaultsPath string `yaml:"defaults_path"` // default: "./persona/defaults"

	// How long before triggering heartbeat curator (hours)
	HeartbeatIntervalHours int `yaml:"heartbeat_interval_hours"` // default: 6

	// Max session messages before compaction
	MaxSessionMessages int `yaml:"max_session_messages"` // default: 100
}

// ─── Local Models ────────────────────────────────────────────────────────────

type ModelsConfig struct {
	// Directory to store downloaded GGUF models
	ModelsDir string `yaml:"models_dir"` // default: "./models"

	// Whether to use Ollama for running local models (requires ollama installed)
	UseOllama bool `yaml:"use_ollama"` // default: true

	// Whether to search for llama-server binary for direct inference
	UseLlamaServer bool `yaml:"use_llama_server"` // default: false

	// HuggingFace API token for gated/private models
	// Can also be set via HF_TOKEN environment variable
	HFToken string `yaml:"hf_token"`
}

// ─── Tools ───────────────────────────────────────────────────────────────────

type ToolsConfig struct {
	// "minimal" | "standard" | "full"
	Profile string `yaml:"profile"`

	// Additional tools to allow beyond profile
	Allow []string `yaml:"allow"`

	// Tools to deny regardless of profile
	Deny []string `yaml:"deny"`

	// Working directory for bash tool
	WorkDir string `yaml:"work_dir"` // default: "./workspace"

	// Timeout for tool execution (seconds)
	TimeoutSeconds int `yaml:"timeout_seconds"` // default: 30
}

// ─── MCP ─────────────────────────────────────────────────────────────────────

type MCPConfig struct {
	Enabled bool        `yaml:"enabled"`
	Servers []MCPServer `yaml:"servers"`
}

type MCPServer struct {
	Name    string `yaml:"name"`
	Command string `yaml:"command"` // e.g. "npx -y @modelcontextprotocol/server-filesystem"
	Args    []string `yaml:"args"`
	Env     map[string]string `yaml:"env"`
}

// ─── Load ─────────────────────────────────────────────────────────────────────

// CreateDefault creates a default configuration file at the given path
func CreateDefault(path string) error {
	cfg := defaults()

	data, err := yaml.Marshal(cfg)
	if err != nil {
		return fmt.Errorf("marshaling config: %w", err)
	}

	// Ensure directory exists
	dir := filepath.Dir(path)
	if err := os.MkdirAll(dir, 0755); err != nil {
		return fmt.Errorf("creating directory: %w", err)
	}

	// Write to file
	if err := os.WriteFile(path, data, 0644); err != nil {
		return fmt.Errorf("writing config: %w", err)
	}

	return nil
}

func Load(path string) (*Config, error) {
	cfg := defaults()

	data, err := os.ReadFile(path)
	if err != nil {
		if os.IsNotExist(err) {
			// No config file — use defaults + env vars
			applyEnv(cfg)
			return cfg, nil
		}
		return nil, fmt.Errorf("reading config: %w", err)
	}

	if err := yaml.Unmarshal(data, cfg); err != nil {
		return nil, fmt.Errorf("parsing config: %w", err)
	}

	// Environment variables override file values
	applyEnv(cfg)

	return cfg, nil
}

func defaults() *Config {
	return &Config{
		Gateway: GatewayConfig{
			Address: "0.0.0.0:8080",
		},
		LLM: LLMConfig{
			Provider:      "ollama",
			Model:         "qwen2.5",
			OllamaBaseURL: "http://localhost:11434",
			MaxTokens:     4096,
			Temperature:   0.7,
			MaxRetries:    3,
		},
		Memory: MemoryConfig{
			PersonaPath:            "./data/persona",
			SessionsPath:           "./data/sessions",
			DBPath:                 "./data/memory.db",
			DendriteDBPath:            "./data/dendrite.db",
			DefaultsPath:           "./persona/defaults",
			HeartbeatIntervalHours: 6,
			MaxSessionMessages:     100,
		},
		Tools: ToolsConfig{
			Profile:        "standard",
			WorkDir:        "./workspace",
			TimeoutSeconds: 30,
		},
		MCP: MCPConfig{
			Enabled: true,
		},
		Models: ModelsConfig{
			ModelsDir:      "./models",
			UseOllama:      true,
			UseLlamaServer: false,
		},
	}
}

func applyEnv(cfg *Config) {
	if v := os.Getenv("ANTHROPIC_API_KEY"); v != "" {
		cfg.LLM.AnthropicKey = v
	}
	if v := os.Getenv("OPENAI_API_KEY"); v != "" {
		cfg.LLM.OpenAIKey = v
	}
	if v := os.Getenv("GEMINI_API_KEY"); v != "" {
		cfg.LLM.GeminiKey = v
	}
	if v := os.Getenv("OLLAMA_BASE_URL"); v != "" {
		cfg.LLM.OllamaBaseURL = v
	}
	if v := os.Getenv("CYNAPSE_PROVIDER"); v != "" {
		cfg.LLM.Provider = strings.ToLower(v)
	}
	if v := os.Getenv("CYNAPSE_MODEL"); v != "" {
		cfg.LLM.Model = v
	}
	if v := os.Getenv("CYNAPSE_ADDRESS"); v != "" {
		cfg.Gateway.Address = v
	}
	if v := os.Getenv("CYNAPSE_AUTH_TOKEN"); v != "" {
		cfg.Gateway.AuthToken = v
	}
	if v := os.Getenv("HF_TOKEN"); v != "" {
		cfg.Models.HFToken = v
	}
}
