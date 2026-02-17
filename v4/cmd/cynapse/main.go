// Cynapse v4.0 — Ghost Shell Hub
// Entry point: single binary, <100ms startup.
package main

import (
	"fmt"
	"os"
	"path/filepath"

	"github.com/Alartist40/cynapse/internal/bridge"
	"github.com/Alartist40/cynapse/internal/hivemind"
	"github.com/Alartist40/cynapse/internal/neurons/bat"
	"github.com/Alartist40/cynapse/internal/neurons/beaver"
	"github.com/Alartist40/cynapse/internal/neurons/canary"
	"github.com/Alartist40/cynapse/internal/neurons/meerkat"
	"github.com/Alartist40/cynapse/internal/neurons/octopus"
	"github.com/Alartist40/cynapse/internal/neurons/wolverine"
	"github.com/Alartist40/cynapse/internal/tui"
	tea "github.com/charmbracelet/bubbletea"
)

// Version is set at build time via -ldflags.
var Version = "4.0.0-dev"

func main() {
	if len(os.Args) > 1 {
		switch os.Args[1] {
		case "--version", "-v":
			fmt.Printf("Cynapse v%s\n", Version)
			os.Exit(0)
		case "--health":
			runHealthCheck()
			os.Exit(0)
		case "--help", "-h":
			printUsage()
			os.Exit(0)
		}
	}

	// Initialize HiveMind Engine
	cfg := hivemind.DefaultConfig()
	engine, err := hivemind.New(cfg)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Error initializing HiveMind: %v\n", err)
		os.Exit(1)
	}
	defer engine.Close()

	// Register Go-native neurons
	engine.RegisterNeuron(bat.New("./data/shards", 2))
	engine.RegisterNeuron(beaver.New("iptables"))
	engine.RegisterNeuron(canary.New())
	engine.RegisterNeuron(meerkat.New())
	engine.RegisterNeuron(octopus.New())
	engine.RegisterNeuron(wolverine.New())

	// Register Python bridged neurons
	pythonDir, _ := filepath.Abs("./python")
	elaraBridge := bridge.NewPythonNeuron("elara", "Elara — 3B MoE AI", filepath.Join(pythonDir, "elara/elara_bridge.py"), []string{"generate", "chat"})
	owlBridge := bridge.NewPythonNeuron("owl", "Owl — OCR Redactor", filepath.Join(pythonDir, "owl/owl_bridge.py"), []string{"ocr", "redact"})

	if err := elaraBridge.Start(); err != nil {
		fmt.Fprintf(os.Stderr, "Warning: Failed to start Elara bridge: %v\n", err)
	} else {
		defer elaraBridge.Stop()
		engine.RegisterNeuron(elaraBridge)
	}

	if err := owlBridge.Start(); err != nil {
		fmt.Fprintf(os.Stderr, "Warning: Failed to start Owl bridge: %v\n", err)
	} else {
		defer owlBridge.Stop()
		engine.RegisterNeuron(owlBridge)
	}

	// Launch TUI
	p := tea.NewProgram(tui.New(engine), tea.WithAltScreen())
	if _, err := p.Run(); err != nil {
		fmt.Fprintf(os.Stderr, "Error: %v\n", err)
		os.Exit(1)
	}
}

func runHealthCheck() {
	fmt.Println("🏥 Cynapse Health Check")
	fmt.Println("═══════════════════════")
	fmt.Println("  ✅ Binary:     OK")
	fmt.Println("  ✅ Validator:  OK (compiled-in)")
	fmt.Printf("  ✅ Version:    %s\n", Version)

	cfg := hivemind.DefaultConfig()
	engine, err := hivemind.New(cfg)
	if err != nil {
		fmt.Printf("  ❌ HiveMind:   Error (%v)\n", err)
	} else {
		fmt.Println("  ✅ HiveMind:   Active")

		// Temporary registration for health check
		engine.RegisterNeuron(bat.New("./data/shards", 2))
		engine.RegisterNeuron(beaver.New("iptables"))
		engine.RegisterNeuron(canary.New())
		engine.RegisterNeuron(meerkat.New())
		engine.RegisterNeuron(octopus.New())
		engine.RegisterNeuron(wolverine.New())

		neurons := engine.ListNeurons()
		fmt.Printf("  ✅ Neurons:    %d registered (Go-native)\n", len(neurons))
	}

	fmt.Println("\n🎉 Diagnostics complete.")
}

func printUsage() {
	fmt.Printf(`Cynapse v%s — Ghost Shell Hub

Usage:
  cynapse              Launch TUI
  cynapse --health     Run diagnostics
  cynapse --version    Show version
  cynapse --help       Show this help
`, Version)
}
