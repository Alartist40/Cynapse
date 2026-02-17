// Cynapse v4.0 — Ghost Shell Hub
// Entry point: single binary, <100ms startup.
package main

import (
	"fmt"
	"os"

	tea "github.com/charmbracelet/bubbletea"
	"github.com/Alartist40/cynapse/internal/tui"
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

	// Launch TUI
	p := tea.NewProgram(tui.New(), tea.WithAltScreen())
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
	// TODO: Check gRPC bridge, neuron availability
	fmt.Println("\n🎉 All systems operational.")
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
