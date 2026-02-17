// Package canary implements network deception and honeypot capabilities.
package canary

import (
	"context"
	"fmt"
	"math/rand"
	"net"
	"strings"
	"sync"
	"time"

	"github.com/Alartist40/cynapse/internal/core"
)

// Trap represents a deception endpoint.
type Trap struct {
	Port     int       `json:"port"`
	Protocol string    `json:"protocol"`
	Active   bool      `json:"active"`
	Hits     int       `json:"hits"`
	LastHit  time.Time `json:"last_hit,omitempty"`
}

// Neuron implements the Canary deception neuron.
type Neuron struct {
	traps    map[int]*Trap
	mu       sync.RWMutex
	stopChan chan struct{}
}

func New() *Neuron {
	return &Neuron{
		traps:    make(map[int]*Trap),
		stopChan: make(chan struct{}),
	}
}

func (n *Neuron) ID() string             { return "canary" }
func (n *Neuron) Name() string           { return "Canary — Network Deception" }
func (n *Neuron) Capabilities() []string { return []string{"deploy_trap", "list_traps", "generate_decoy", "status"} }

func (n *Neuron) Execute(ctx context.Context, task core.Task) (core.Result, error) {
	switch task.Operation {
	case "deploy_trap":
		port := 0
		fmt.Sscanf(task.Params["port"], "%d", &port)
		if port == 0 {
			port = 4444 + rand.Intn(1000)
		}
		trap := &Trap{Port: port, Protocol: "tcp", Active: true}
		n.mu.Lock()
		n.traps[port] = trap
		n.mu.Unlock()

		// Start listener in background
		go n.listenTrap(ctx, trap)

		return core.Result{
			Success: true,
			Output:  fmt.Sprintf("🐦 Canary trap deployed on port %d", port),
			Details: map[string]string{"port": fmt.Sprintf("%d", port)},
		}, nil

	case "list_traps":
		n.mu.RLock()
		defer n.mu.RUnlock()
		var lines []string
		for _, t := range n.traps {
			status := "ACTIVE"
			if !t.Active {
				status = "INACTIVE"
			}
			lines = append(lines, fmt.Sprintf("  Port %d [%s] — %d hits", t.Port, status, t.Hits))
		}
		if len(lines) == 0 {
			return core.Result{Success: true, Output: "No active traps."}, nil
		}
		return core.Result{Success: true, Output: "🐦 Active Traps:\n" + strings.Join(lines, "\n")}, nil

	case "generate_decoy":
		decoy := n.generateDecoyResponse()
		return core.Result{Success: true, Output: decoy}, nil

	default:
		return core.Result{}, fmt.Errorf("canary: unknown operation %s", task.Operation)
	}
}

func (n *Neuron) listenTrap(ctx context.Context, trap *Trap) {
	ln, err := net.Listen("tcp", fmt.Sprintf(":%d", trap.Port))
	if err != nil {
		trap.Active = false
		return
	}
	defer ln.Close()

	go func() {
		<-ctx.Done()
		ln.Close()
	}()

	for {
		conn, err := ln.Accept()
		if err != nil {
			break
		}
		n.mu.Lock()
		trap.Hits++
		trap.LastHit = time.Now()
		n.mu.Unlock()

		// Send fake response and close
		conn.Write([]byte(n.generateDecoyResponse()))
		conn.Close()
	}
	trap.Active = false
}

func (n *Neuron) generateDecoyResponse() string {
	responses := []string{
		"SSH-2.0-OpenSSH_8.2p1 Ubuntu-4ubuntu0.5\n",
		"220 mail.internal.corp ESMTP Postfix\n",
		"HTTP/1.1 401 Unauthorized\r\nWWW-Authenticate: Basic realm=\"Admin\"\r\n\r\n",
		"MySQL 8.0.28\n\xff\x00\x00",
	}
	return responses[rand.Intn(len(responses))]
}
