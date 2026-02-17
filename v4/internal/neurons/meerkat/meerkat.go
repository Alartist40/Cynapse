// Package meerkat implements network and port scanning capabilities.
package meerkat

import (
	"context"
	"fmt"
	"net"
	"strings"
	"sync"
	"time"

	"github.com/Alartist40/cynapse/internal/core"
)

// ScanResult holds the result for a single port.
type ScanResult struct {
	Port   int    `json:"port"`
	State  string `json:"state"` // "open", "closed", "filtered"
	Banner string `json:"banner,omitempty"`
}

// Neuron implements the Meerkat network scanner neuron.
type Neuron struct {
	timeout time.Duration
	workers int
}

func New() *Neuron {
	return &Neuron{timeout: 2 * time.Second, workers: 100}
}

func (n *Neuron) ID() string             { return "meerkat" }
func (n *Neuron) Name() string           { return "Meerkat — Network Scanner" }
func (n *Neuron) Capabilities() []string { return []string{"port_scan", "service_detect", "quick_scan"} }

func (n *Neuron) Execute(ctx context.Context, task core.Task) (core.Result, error) {
	switch task.Operation {
	case "port_scan":
		target := task.Params["target"]
		if target == "" {
			target = "127.0.0.1"
		}
		startPort, endPort := 1, 1024
		fmt.Sscanf(task.Params["start_port"], "%d", &startPort)
		fmt.Sscanf(task.Params["end_port"], "%d", &endPort)

		results := n.scanPorts(ctx, target, startPort, endPort)

		var lines []string
		openCount := 0
		for _, r := range results {
			if r.State == "open" {
				openCount++
				line := fmt.Sprintf("  %d/tcp  OPEN", r.Port)
				if r.Banner != "" {
					line += "  " + r.Banner
				}
				lines = append(lines, line)
			}
		}

		output := fmt.Sprintf("🔍 Scan of %s (%d-%d):\n  %d open ports found\n\n%s",
			target, startPort, endPort, openCount, strings.Join(lines, "\n"))

		return core.Result{
			Success: true,
			Output:  output,
			Details: map[string]string{
				"target":     target,
				"open_count": fmt.Sprintf("%d", openCount),
			},
		}, nil

	case "quick_scan":
		target := task.Params["target"]
		if target == "" {
			target = "127.0.0.1"
		}
		commonPorts := []int{21, 22, 23, 25, 53, 80, 110, 135, 139, 143, 443, 445, 993, 995, 3306, 3389, 5432, 8080, 8443}
		results := n.scanSpecificPorts(ctx, target, commonPorts)

		var lines []string
		for _, r := range results {
			if r.State == "open" {
				lines = append(lines, fmt.Sprintf("  %d/tcp  OPEN", r.Port))
			}
		}

		return core.Result{
			Success: true,
			Output:  fmt.Sprintf("⚡ Quick scan of %s:\n%s", target, strings.Join(lines, "\n")),
		}, nil

	default:
		return core.Result{}, fmt.Errorf("meerkat: unknown operation %s", task.Operation)
	}
}

func (n *Neuron) scanPorts(ctx context.Context, target string, start, end int) []ScanResult {
	var results []ScanResult
	var mu sync.Mutex
	var wg sync.WaitGroup

	sem := make(chan struct{}, n.workers)

	for port := start; port <= end; port++ {
		select {
		case <-ctx.Done():
			return results
		default:
		}

		sem <- struct{}{}
		wg.Add(1)
		go func(p int) {
			defer wg.Done()
			defer func() { <-sem }()

			r := n.probePort(target, p)
			mu.Lock()
			results = append(results, r)
			mu.Unlock()
		}(port)
	}

	wg.Wait()
	return results
}

func (n *Neuron) scanSpecificPorts(ctx context.Context, target string, ports []int) []ScanResult {
	var results []ScanResult
	var mu sync.Mutex
	var wg sync.WaitGroup

	for _, port := range ports {
		wg.Add(1)
		go func(p int) {
			defer wg.Done()
			r := n.probePort(target, p)
			mu.Lock()
			results = append(results, r)
			mu.Unlock()
		}(port)
	}

	wg.Wait()
	return results
}

func (n *Neuron) probePort(target string, port int) ScanResult {
	addr := fmt.Sprintf("%s:%d", target, port)
	conn, err := net.DialTimeout("tcp", addr, n.timeout)
	if err != nil {
		return ScanResult{Port: port, State: "closed"}
	}
	defer conn.Close()

	// Try to grab banner
	banner := ""
	conn.SetReadDeadline(time.Now().Add(500 * time.Millisecond))
	buf := make([]byte, 256)
	n2, err := conn.Read(buf)
	if err == nil && n2 > 0 {
		banner = strings.TrimSpace(string(buf[:n2]))
	}

	return ScanResult{Port: port, State: "open", Banner: banner}
}
