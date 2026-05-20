package main

import (
	"context"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"time"

	tea "github.com/charmbracelet/bubbletea"
	"github.com/Alartist40/cynapse/internal/agent"
	"github.com/Alartist40/cynapse/internal/config"
	"github.com/Alartist40/cynapse/internal/llm"
	"github.com/Alartist40/cynapse/internal/mcp"
	"github.com/Alartist40/cynapse/internal/memory"
	"github.com/Alartist40/cynapse/internal/models"
	"github.com/Alartist40/cynapse/internal/session"
	"github.com/Alartist40/cynapse/internal/synapse"
	"github.com/Alartist40/cynapse/internal/tui"
)

const version = "2.0.0-beta"

func main() {
	// Ensure home directory exists
	homeDir := getHomeDir()
	ensureDir(homeDir)
	ensureDir(filepath.Join(homeDir, "synapses"))
	ensureDir(filepath.Join(homeDir, "data"))
	ensureDir(filepath.Join(homeDir, "logs"))
	ensureDir(filepath.Join(homeDir, "models"))

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
	case "model":
		handleModelCommand(args)
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

	// Ensure workspace and models dirs exist
	ensureDir(cfg.Tools.WorkDir)
	ensureDir(cfg.Models.ModelsDir)

	// Pass models dir to LLM config for local model resolution
	if cfg.LLM.ModelsDir == "" {
		cfg.LLM.ModelsDir = cfg.Models.ModelsDir
	}

	// Initialize LLM client
	llmClient, err := llm.New(&cfg.LLM)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Error initializing LLM: %v\n", err)
		os.Exit(1)
	}
	defer func() {
		if llmClient != nil {
			_ = llmClient.Close()
		}
	}()

	// Load persona
	deviceID := "cynapse_tui_01"
	persona, err := memory.NewPersona(deviceID, cfg.Memory.PersonaPath, cfg.Memory.DefaultsPath, cfg.Memory.DendriteDBPath)
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
	agentInstance := agent.New(
		deviceID,
		llmClient,
		persona,
		sessions,
		mcpMgr,
		cfg,
	)

	// Start background curator (heartbeat mechanism)
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()
	go agentInstance.StartCurator(ctx)

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
			fmt.Println("Usage: cynapse synapse add <name> [--path <binary>]")
			os.Exit(1)
		}
		name := subargs[0]

		// Parse optional flags
		var sourcePath string
		for i := 1; i < len(subargs); i++ {
			if subargs[i] == "--path" && i+1 < len(subargs) {
				sourcePath = subargs[i+1]
				i++
			}
		}

		var err error
		if sourcePath != "" {
			err = registry.InstallFromPath(name, synapseDir, sourcePath)
		} else {
			err = registry.Install(name, synapseDir)
		}
		if err != nil {
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

func handleModelCommand(args []string) {
	if len(args) == 0 {
		printModelHelp()
		return
	}

	cmd := args[0]
	subargs, token := parseModelFlags(args[1:])

	// Resolve token priority: CLI flag > HF_TOKEN env > config
	if token == "" {
		token = os.Getenv("HF_TOKEN")
	}
	if token == "" {
		cfg, _ := config.Load(getConfigPath())
		if cfg != nil {
			token = cfg.Models.HFToken
		}
	}

	modelsDir := filepath.Join(getHomeDir(), "models")
	mgr := models.NewManager(modelsDir)
	_ = mgr.EnsureDirs()

	switch cmd {
	case "search":
		query := ""
		if len(subargs) > 0 {
			query = subargs[0]
		}
		searcher := models.NewHFSearcher()
		if token != "" {
			searcher.SetAuthToken(token)
		}
		results, err := searcher.Search(query, 20)
		if err != nil {
			fmt.Fprintf(os.Stderr, "Error searching: %v\n", err)
			os.Exit(1)
		}
		fmt.Printf("🔍 Found %d models\n\n", len(results))
		for _, m := range results {
			fmt.Printf("  📦 %s\n", m.ID)
			fmt.Printf("     Likes: %d | Downloads: %d | Tags: %v\n", m.Likes, m.Downloads, m.Tags)
			files, _ := searcher.ListFiles(m.ID)
			for _, f := range files {
				fmt.Printf("     └── 📄 %s (%s)\n", f.RFilename, models.FormatBytes(f.Size))
			}
			fmt.Println()
		}

	case "download":
		if len(subargs) < 1 {
			fmt.Println("Usage: cynapse model download <hf-model-id> [filename] [--token <token>]")
			fmt.Println("       HF_TOKEN env var or config hf_token can also be used")
			os.Exit(1)
		}
		hfModelID := subargs[0]
		var filename string
		if len(subargs) >= 2 {
			filename = subargs[1]
		}

		// If no filename specified, list available GGUFs
		if filename == "" {
			searcher := models.NewHFSearcher()
			if token != "" {
				searcher.SetAuthToken(token)
			}
			files, err := searcher.ListFiles(hfModelID)
			if err != nil || len(files) == 0 {
				fmt.Fprintf(os.Stderr, "No GGUF files found for %s\n", hfModelID)
				os.Exit(1)
			}
			fmt.Printf("Available GGUF files for %s:\n", hfModelID)
			for i, f := range files {
				fmt.Printf("  %d. %s (%s)\n", i+1, f.RFilename, models.FormatBytes(f.Size))
			}
			fmt.Println("Please specify a filename: cynapse model download <hf-id> <filename>")
			os.Exit(1)
		}

		dest := mgr.PathFor(hfModelID, filename)
		fmt.Printf("⬇️  Downloading %s/%s...\n", hfModelID, filename)
		fmt.Printf("   Destination: %s\n", dest)
		if token != "" {
			fmt.Println("   🔐 Using HF authentication token")
		}

		err := models.DownloadHF(hfModelID, filename, dest, func(downloaded, total int64, speedMBps float64) {
			fmt.Printf("\r   %s", models.FormatProgress(downloaded, total, speedMBps))
		}, token)
		fmt.Println()
		if err != nil {
			fmt.Fprintf(os.Stderr, "Download failed: %v\n", err)
			os.Exit(1)
		}

		// Add to registry
		reg, _ := mgr.Load()
		lm := models.LocalModelFromHF(hfModelID, models.ModelFile{RFilename: filename, Size: 0}, modelsDir)
		// Get actual file size
		if info, err := os.Stat(dest); err == nil {
			lm.Size = info.Size()
		}
		lm.DownloadedAt = time.Now()
		mgr.Add(reg, lm)
		if err := mgr.Save(reg); err != nil {
			fmt.Fprintf(os.Stderr, "Warning: failed to save registry: %v\n", err)
		}

		fmt.Printf("✅ Downloaded to %s\n", dest)
		fmt.Printf("💡 Import to Ollama: cynapse model import %s\n", lm.ID)

	case "list":
		reg, err := mgr.Load()
		if err != nil {
			fmt.Fprintf(os.Stderr, "Error loading registry: %v\n", err)
			os.Exit(1)
		}
		if len(reg.Models) == 0 {
			fmt.Println("No local models downloaded yet.")
			fmt.Println("Search: cynapse model search <query>")
			return
		}
		fmt.Printf("📦 Local Models (%d):\n\n", len(reg.Models))
		for _, m := range reg.Models {
			status := "📥 downloaded"
			if m.OllamaName != "" {
				status = fmt.Sprintf("🦙 Ollama: %s", m.OllamaName)
			}
			fmt.Printf("  %s\n", m.Name)
			fmt.Printf("     ID: %s | Size: %s | Quant: %s | %s\n", m.ID, models.FormatBytes(m.Size), m.Quant, status)
			fmt.Printf("     Path: %s\n", m.Path)
			fmt.Println()
		}

	case "import":
		if len(subargs) == 0 {
			fmt.Println("Usage: cynapse model import <local-model-id>")
			os.Exit(1)
		}
		id := subargs[0]
		reg, err := mgr.Load()
		if err != nil {
			fmt.Fprintf(os.Stderr, "Error loading registry: %v\n", err)
			os.Exit(1)
		}
		lm, err := mgr.Get(reg, id)
		if err != nil {
			fmt.Fprintf(os.Stderr, "Model not found: %v\n", err)
			os.Exit(1)
		}

		importer := models.NewOllamaImporter()
		if !importer.Available() {
			fmt.Fprintf(os.Stderr, "Ollama not found. Install it from https://ollama.com\n")
			os.Exit(1)
		}

		ollamaName := models.SuggestOllamaName(lm.HFModelID, lm.Quant)
		fmt.Printf("🦙 Importing %s into Ollama as %s...\n", lm.Name, ollamaName)
		if err := importer.Import(ollamaName, lm.Path, lm.Type); err != nil {
			fmt.Fprintf(os.Stderr, "Import failed: %v\n", err)
			os.Exit(1)
		}
		lm.OllamaName = ollamaName
		mgr.Add(reg, *lm)
		if err := mgr.Save(reg); err != nil {
			fmt.Fprintf(os.Stderr, "Warning: failed to save registry: %v\n", err)
		}
		fmt.Printf("✅ Imported! Use it with: cynapse (set model to %s)\n", ollamaName)

	case "remove":
		if len(subargs) == 0 {
			fmt.Println("Usage: cynapse model remove <local-model-id>")
			os.Exit(1)
		}
		id := subargs[0]
		reg, err := mgr.Load()
		if err != nil {
			fmt.Fprintf(os.Stderr, "Error loading registry: %v\n", err)
			os.Exit(1)
		}
		lm, err := mgr.Get(reg, id)
		if err != nil {
			fmt.Fprintf(os.Stderr, "Model not found: %v\n", err)
			os.Exit(1)
		}

		// Remove from Ollama if imported
		if lm.OllamaName != "" {
			importer := models.NewOllamaImporter()
			if importer.Available() {
				fmt.Printf("🦙 Removing Ollama model %s...\n", lm.OllamaName)
				_ = importer.Remove(lm.OllamaName)
			}
		}

		if err := mgr.Remove(reg, id, true); err != nil {
			fmt.Fprintf(os.Stderr, "Error removing: %v\n", err)
			os.Exit(1)
		}
		if err := mgr.Save(reg); err != nil {
			fmt.Fprintf(os.Stderr, "Warning: failed to save registry: %v\n", err)
		}
		fmt.Printf("✅ Removed %s\n", id)

	default:
		fmt.Printf("Unknown model command: %s\n", cmd)
		printModelHelp()
		os.Exit(1)
	}
}

func parseModelFlags(args []string) ([]string, string) {
	var out []string
	var token string
	for i := 0; i < len(args); i++ {
		if args[i] == "--token" && i+1 < len(args) {
			token = args[i+1]
			i++
			continue
		}
		out = append(out, args[i])
	}
	return out, token
}

func printModelHelp() {
	fmt.Print(`
Model commands:
  search <query> [--token <t>]     Search HuggingFace for GGUF models
  download <hf-id> [file] [--token <t>]  Download a model file
  list                             List downloaded local models
  import <local-id>                Import a downloaded model into Ollama
  remove <local-id>                Remove a downloaded model

Authentication:
  --token <token>     HF API token (or set HF_TOKEN env var / config hf_token)

Examples:
  cynapse model search qwen2.5
  cynapse model download meta-llama/Llama-3.2-1B-Instruct-GGUF Llama-3.2-1B-Instruct-Q4_0.gguf --token hf_xxx
  cynapse model list
  cynapse model import hf:Qwen/Qwen2.5-7B-Instruct-GGUF/qwen2.5-7b-instruct-q4_0.gguf
`)
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
		configPath := getConfigPath()
		editor := os.Getenv("EDITOR")
		if editor == "" {
			editor = "vi"
		}
		cmd := exec.Command(editor, configPath)
		cmd.Stdin = os.Stdin
		cmd.Stdout = os.Stdout
		cmd.Stderr = os.Stderr
		if err := cmd.Run(); err != nil {
			fmt.Fprintf(os.Stderr, "Error running editor: %v\n", err)
			os.Exit(1)
		}

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
  cynapse model <cmd>     Manage local AI models
  cynapse config <cmd>    Manage configuration
  cynapse version         Show version
  cynapse help            Show this help

SYNAPSE COMMANDS:
  list                              List installed synapses
  add <name> [--path <binary>]      Install a synapse
  remove <name>                     Remove a synapse
  search [query]                    Search available synapses

MODEL COMMANDS:
  search <query> [--token <t>]      Search HuggingFace for GGUF models
  download <hf-id> [filename] [--token <t>]  Download a model from HuggingFace
  list                              List downloaded local models
  import <local-id>                 Import a downloaded model into Ollama
  remove <local-id>                 Remove a downloaded model

CONFIG COMMANDS:
  init                    Create default config
  edit                    Edit configuration file

EXAMPLES:
  cynapse                          # Run interactive chat
  cynapse model search qwen2.5     # Search for qwen2.5 GGUF models
  cynapse model download Qwen/Qwen2.5-7B-Instruct-GGUF qwen2.5-7b-instruct-q4_0.gguf
  cynapse model list               # See downloaded models
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
  cynapse synapse add leafcutter --path ./leafcutter
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
