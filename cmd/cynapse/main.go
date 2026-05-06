package main

import (
	"fmt"
	"os"
	"path/filepath"

	tea "github.com/charmbracelet/bubbletea"
	"github.com/Alartist40/cynapse/internal/agent"
	"github.com/Alartist40/cynapse/internal/config"
	"github.com/Alartist40/cynapse/internal/llm"
	"github.com/Alartist40/cynapse/internal/mcp"
	"github.com/Alartist40/cynapse/internal/memory"
	"github.com/Alartist40/cynapse/internal/session"
	"github.com/Alartist40/cynapse/internal/synapse"
	"github.com/Alartist40/cynapse/internal/tui"
)

const version = "1.0.0"

func main() {
	// Ensure home directory exists
	homeDir := getHomeDir()
	ensureDir(homeDir)
	ensureDir(filepath.Join(homeDir, "synapses"))
	ensureDir(filepath.Join(homeDir, "data"))
	ensureDir(filepath.Join(homeDir, "logs"))

	// Parse command
	if len(os.Args) < 2 {
		// No args = run interactive chat
		runChat()
		return
	}

	command := os.Args[1]
	args := os.Args[2:]

	switch command {
	case "synapse":
		handleSynapseCommand(args)
	case "config":
		handleConfigCommand(args)
	case "version":
		fmt.Printf("CYNAPSE v%s\n", version)
	case "help":
		printHelp()
	default:
		// Unknown command, default to chat
		runChat()
	}
}

func runChat() {
	// Load configuration
	cfg, err := config.Load(getConfigPath())
	if err != nil {
		fmt.Fprintf(os.Stderr, "Error loading config: %v\n", err)
		fmt.Fprintf(os.Stderr, "Run 'cynapse config init' to create default config\n")
		os.Exit(1)
	}

	// Initialize LLM client
	llmClient, err := llm.New(&config.LLMConfig{
		Provider:       cfg.LLM.Provider,
		Model:          cfg.LLM.Model,
		OllamaBaseURL:  cfg.LLM.OllamaBaseURL,
		AnthropicKey:   cfg.LLM.AnthropicKey,
		OpenAIKey:      cfg.LLM.OpenAIKey,
		GeminiKey:      cfg.LLM.GeminiKey,
		MaxTokens:      cfg.LLM.MaxTokens,
		Temperature:    cfg.LLM.Temperature,
		MaxRetries:     cfg.LLM.MaxRetries,
	})
	if err != nil {
		fmt.Fprintf(os.Stderr, "Error initializing LLM: %v\n", err)
		os.Exit(1)
	}

	// Initialize memory store
	store, err := memory.NewStore(cfg.Memory.DBPath)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Error opening memory store: %v\n", err)
		os.Exit(1)
	}
	defer store.Close()

	// Load persona
	persona, err := memory.NewPersona("default_device", cfg.Memory.PersonaPath, cfg.Memory.DefaultsPath)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Error loading persona: %v\n", err)
		os.Exit(1)
	}

	// Initialize session manager
	sessions := session.NewManager(cfg.Memory.SessionsPath)

	// Initialize MCP manager
	var mcpMgr *mcp.Manager
	if cfg.MCP.Enabled {
		mcpMgr, err = mcp.New(cfg.MCP.Servers)
		if err != nil {
			fmt.Fprintf(os.Stderr, "Warning: MCP initialization failed: %v\n", err)
		}
		defer func() {
			if mcpMgr != nil {
				mcpMgr.Shutdown()
			}
		}()
	}

	// Load synapses
	registry := synapse.NewRegistry()
	synapseDir := filepath.Join(getHomeDir(), "synapses")
	if err := registry.Discover(synapseDir); err != nil {
		fmt.Fprintf(os.Stderr, "Warning: Failed to discover synapses: %v\n", err)
	}

	// Add discovered synapses to MCP servers
	if mcpMgr != nil {
		for _, syn := range registry.GetAll() {
			// Convert synapse to MCP server config and add
			mcpMgr.AddServer(syn.ToMCPConfig())
		}
	}

	// Initialize agent
	deviceID := "cynapse_tui_01"
	agentInstance := agent.New(
		deviceID,
		llmClient,
		persona,
		store,
		sessions,
		mcpMgr,
		cfg,
	)

	// Create and run TUI
	model := tui.NewModel(agentInstance, cfg, llmClient)
	p := tea.NewProgram(model, tea.WithAltScreen())

	if _, err := p.Run(); err != nil {
		fmt.Fprintf(os.Stderr, "Error running TUI: %v\n", err)
		os.Exit(1)
	}
}

func handleSynapseCommand(args []string) {
	if len(args) == 0 {
		printSynapseHelp()
		return
	}

	cmd := args[0]
	subargs := args[1:]

	registry := synapse.NewRegistry()
	synapseDir := filepath.Join(getHomeDir(), "synapses")

	switch cmd {
	case "list":
		if err := registry.Discover(synapseDir); err != nil {
			fmt.Fprintf(os.Stderr, "Error: %v\n", err)
			os.Exit(1)
		}
		registry.List()

	case "add", "install":
		if len(subargs) == 0 {
			fmt.Println("Usage: cynapse synapse add <name>")
			os.Exit(1)
		}
		if err := registry.Install(subargs[0], synapseDir); err != nil {
			fmt.Fprintf(os.Stderr, "Error: %v\n", err)
			os.Exit(1)
		}

	case "remove", "uninstall":
		if len(subargs) == 0 {
			fmt.Println("Usage: cynapse synapse remove <name>")
			os.Exit(1)
		}
		if err := registry.Uninstall(subargs[0], synapseDir); err != nil {
			fmt.Fprintf(os.Stderr, "Error: %v\n", err)
			os.Exit(1)
		}

	case "search":
		if len(subargs) == 0 {
			registry.SearchAll()
		} else {
			registry.Search(subargs[0])
		}

	default:
		fmt.Printf("Unknown synapse command: %s\n", cmd)
		printSynapseHelp()
		os.Exit(1)
	}
}

func handleConfigCommand(args []string) {
	if len(args) == 0 {
		// Show current config location
		fmt.Printf("Config location: %s\n", getConfigPath())
		return
	}

	cmd := args[0]

	switch cmd {
	case "init":
		// Create default config
		if err := config.CreateDefault(getConfigPath()); err != nil {
			fmt.Fprintf(os.Stderr, "Error creating config: %v\n", err)
			os.Exit(1)
		}
		fmt.Printf("Created default config at: %s\n", getConfigPath())

	case "edit":
		// Open config in editor
		editor := os.Getenv("EDITOR")
		if editor == "" {
			editor = "nano"
		}
		// TODO: exec editor with config file

	default:
		fmt.Printf("Unknown config command: %s\n", cmd)
		fmt.Println("Available commands: init, edit")
		os.Exit(1)
	}
}

func printHelp() {
	fmt.Print(`
🧠 CYNAPSE - Modular AI Agent

USAGE:
  cynapse                 Start interactive chat
  cynapse synapse <cmd>   Manage synapses
  cynapse config <cmd>    Manage configuration
  cynapse version         Show version
  cynapse help            Show this help

SYNAPSE COMMANDS:
  list                    List installed synapses
  add <name>              Install a synapse
  remove <name>           Remove a synapse
  search [query]          Search available synapses

CONFIG COMMANDS:
  init                    Create default config
  edit                    Edit configuration file

EXAMPLES:
  cynapse                          # Run interactive chat
  cynapse synapse add leafcutter   # Install LeafcutterLLM synapse
  cynapse synapse list             # See installed synapses
  cynapse config init              # Create default config

For more information, visit: https://github.com/Alartist40/cynapse
`)
}

func printSynapseHelp() {
	fmt.Print(`
Synapse commands:
  list                 List installed synapses
  add <name>           Install a synapse from registry
  remove <name>        Remove an installed synapse
  search [query]       Search available synapses

Examples:
  cynapse synapse list
  cynapse synapse add leafcutter
  cynapse synapse remove git-tools
  cynapse synapse search inference
`)
}

func getHomeDir() string {
	home := os.Getenv("HOME")
	if home == "" {
		home = os.Getenv("USERPROFILE") // Windows
	}
	return filepath.Join(home, ".cynapse")
}

func getConfigPath() string {
	return filepath.Join(getHomeDir(), "config.yaml")
}

func ensureDir(path string) {
	if err := os.MkdirAll(path, 0755); err != nil {
		fmt.Fprintf(os.Stderr, "Warning: Failed to create directory %s: %v\n", path, err)
	}
}
