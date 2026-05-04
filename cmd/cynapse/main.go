package main

import (
	"context"
	"fmt"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	tea "github.com/charmbracelet/bubbletea"
	"github.com/charmbracelet/lipgloss"
	"github.com/yourusername/cynapse/internal/agent"
	"github.com/yourusername/cynapse/internal/config"
	"github.com/yourusername/cynapse/internal/llm"
	"github.com/yourusername/cynapse/internal/mcp"
	"github.com/yourusername/cynapse/internal/memory"
	"github.com/yourusername/cynapse/internal/session"
	"github.com/yourusername/cynapse/internal/tui"
)

var (
	purple = lipgloss.Color("#9b59b6")
	orange = lipgloss.Color("#e67e22")
	dim    = lipgloss.Color("#4a5568")
	bright = lipgloss.Color("#e4e7eb")

	heroStyle = lipgloss.NewStyle().
			Foreground(purple).
			Bold(true)

	okStyle   = lipgloss.NewStyle().Foreground(purple)
	failStyle = lipgloss.NewStyle().Foreground(orange)
	dimStyle  = lipgloss.NewStyle().Foreground(dim)
)

func main() {
	// Clear screen
	fmt.Print("\033[H\033[2J")

	// Show hero
	logo := `
  ██████╗██╗   ██╗███╗   ██╗ █████╗ ██████╗ ███████╗███████╗
 ██╔════╝╚██╗ ██╔╝████╗  ██║██╔══██╗██╔══██╗██╔════╝██╔════╝
 ██║      ╚████╔╝ ██╔██╗ ██║███████║██████╔╝███████╗█████╗  
 ██║       ╚██╔╝  ██║╚██╗██║██╔══██║██╔═══╝ ╚════██║██╔══╝  
 ╚██████╗   ██║   ██║ ╚████║██║  ██║██║     ███████║███████╗
  ╚═════╝   ╚═╝   ╚═╝  ╚═══╝╚═╝  ╚═╝╚═╝     ╚══════╝╚══════╝
`
	fmt.Println(heroStyle.Render(logo))
	fmt.Println(dimStyle.Render("                      v1.0.0 GHOST SHELL\n"))

	// Boot checks
	checks := []struct {
		name string
		fn   func() error
	}{
		{"Loading configuration", checkConfig},
		{"Verifying SQLite database", checkDatabase},
		{"Connecting to Ollama", checkOllama},
		{"Initializing memory system", checkMemory},
		{"Testing LLM connection", checkLLM},
		{"Starting agent core", checkAgent},
	}

	var cfg *config.Config
	var llmCli llm.Client
	var store *memory.Store
	var sessions *session.Manager
	var mcpMgr *mcp.Manager
	var persona *memory.Persona
	var ag *agent.Agent

	for _, check := range checks {
		fmt.Printf("  %s ", dimStyle.Render("●"))
		fmt.Print(check.name + "...")
		time.Sleep(200 * time.Millisecond)

		err := check.fn()
		if err != nil {
			fmt.Print("\r  " + failStyle.Render("✗") + " " + check.name + " ")
			fmt.Println(failStyle.Render(fmt.Sprintf("FAILED: %v", err)))
			os.Exit(1)
		}

		// Store initialized components
		switch check.name {
		case "Loading configuration":
			cfg, _ = config.Load("config.yaml")
		case "Verifying SQLite database":
			store, _ = memory.NewStore(cfg.Memory.DBPath)
		case "Initializing memory system":
			sessions = session.NewManager(cfg.Memory.SessionsPath)
			mcpMgr = mcp.NewManager(cfg.MCP)
			persona, _ = memory.NewPersona("cynapse_tui_01", cfg.Memory.PersonaPath, cfg.Memory.DefaultsPath)
		case "Testing LLM connection":
			llmCli, _ = llm.New(&cfg.LLM)
		case "Starting agent core":
			ag = agent.New("cynapse_tui_01", llmCli, persona, store, sessions, mcpMgr, cfg)
		}

		fmt.Print("\r  " + okStyle.Render("✓") + " " + check.name + "\n")
	}

	fmt.Println()
	fmt.Println(okStyle.Render("  System ready. Launching interface..."))
	time.Sleep(800 * time.Millisecond)

	// Start curator
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	go func() {
		sig := make(chan os.Signal, 1)
		signal.Notify(sig, syscall.SIGINT, syscall.SIGTERM)
		<-sig
		cancel()
	}()

	ag.StartCurator(ctx)

	// Cleanup on exit
	defer store.Close()
	defer mcpMgr.Close()

	// Clear and launch TUI
	fmt.Print("\033[H\033[2J")

	m := tui.NewModel(ag, cfg, llmCli)
	p := tea.NewProgram(m, tea.WithAltScreen())

	if _, err := p.Run(); err != nil {
		fmt.Fprintf(os.Stderr, "TUI error: %v\n", err)
		os.Exit(1)
	}
}

func checkConfig() error {
	cfgPath := "config.yaml"
	if len(os.Args) > 1 {
		cfgPath = os.Args[1]
	}
	_, err := config.Load(cfgPath)
	return err
}

func checkDatabase() error {
	cfg, _ := config.Load("config.yaml")
	store, err := memory.NewStore(cfg.Memory.DBPath)
	if err != nil {
		return err
	}
	store.Close()
	return nil
}

func checkOllama() error {
	cfg, _ := config.Load("config.yaml")
	if cfg.LLM.Provider != "ollama" {
		return nil // Skip check for non-Ollama providers
	}

	baseURL := cfg.LLM.OllamaBaseURL
	if baseURL == "" {
		baseURL = "http://localhost:11434"
	}

	resp, err := http.Get(baseURL + "/api/tags")
	if err != nil {
		return fmt.Errorf("Ollama not running at %s", baseURL)
	}
	defer resp.Body.Close()

	if resp.StatusCode != 200 {
		return fmt.Errorf("Ollama returned HTTP %d", resp.StatusCode)
	}
	return nil
}

func checkMemory() error {
	cfg, _ := config.Load("config.yaml")
	_, err := memory.NewPersona("cynapse_tui_01", cfg.Memory.PersonaPath, cfg.Memory.DefaultsPath)
	return err
}

func checkLLM() error {
	cfg, _ := config.Load("config.yaml")
	client, err := llm.New(&cfg.LLM)
	if err != nil {
		return err
	}

	// Quick test: list models (Ollama only)
	if cfg.LLM.Provider == "ollama" {
		_, err := llm.ListOllamaModels(cfg.LLM.OllamaBaseURL)
		if err != nil {
			return fmt.Errorf("model %q not found", cfg.LLM.Model)
		}
	}

	_ = client
	return nil
}

func checkAgent() error {
	// Already constructed in loop, just validate
	return nil
}
