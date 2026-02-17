// Package bridge implements the Go↔Python communication layer.
// AI neurons (Elara, Owl) remain in Python; Go orchestrates them via subprocess/stdin-stdout.
package bridge

import (
	"bufio"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"os/exec"
	"sync"

	"github.com/Alartist40/cynapse/internal/core"
)

// PythonNeuron wraps a Python neuron process, communicating via JSON over stdin/stdout.
type PythonNeuron struct {
	id         string
	name       string
	caps       []string
	scriptPath string
	cmd        *exec.Cmd
	stdin      io.WriteCloser
	stdout     *bufio.Scanner
	mu         sync.Mutex
	running    bool
}

// bridgeRequest is the JSON sent to the Python process.
type bridgeRequest struct {
	Operation string            `json:"operation"`
	Params    map[string]string `json:"params"`
	Payload   string            `json:"payload,omitempty"`
}

// bridgeResponse is the JSON returned from the Python process.
type bridgeResponse struct {
	Success    bool              `json:"success"`
	Output     string            `json:"output"`
	Confidence float64           `json:"confidence,omitempty"`
	Details    map[string]string `json:"details,omitempty"`
	Error      string            `json:"error,omitempty"`
}

// NewPythonNeuron creates a bridge neuron backed by a Python script.
func NewPythonNeuron(id, name, scriptPath string, capabilities []string) *PythonNeuron {
	return &PythonNeuron{
		id:         id,
		name:       name,
		caps:       capabilities,
		scriptPath: scriptPath,
	}
}

func (p *PythonNeuron) ID() string             { return p.id }
func (p *PythonNeuron) Name() string           { return p.name }
func (p *PythonNeuron) Capabilities() []string { return p.caps }

// Start launches the Python subprocess. Call this once before Execute.
func (p *PythonNeuron) Start() error {
	p.mu.Lock()
	defer p.mu.Unlock()

	p.cmd = exec.Command("python3", p.scriptPath, "--bridge")
	var err error
	p.stdin, err = p.cmd.StdinPipe()
	if err != nil {
		return fmt.Errorf("bridge stdin: %w", err)
	}

	stdoutPipe, err := p.cmd.StdoutPipe()
	if err != nil {
		return fmt.Errorf("bridge stdout: %w", err)
	}
	p.stdout = bufio.NewScanner(stdoutPipe)
	p.stdout.Buffer(make([]byte, 1<<20), 1<<20) // 1MB buffer

	if err := p.cmd.Start(); err != nil {
		return fmt.Errorf("bridge start: %w", err)
	}

	p.running = true
	return nil
}

// Execute sends a task to the Python process and waits for a response.
func (p *PythonNeuron) Execute(ctx context.Context, task core.Task) (core.Result, error) {
	p.mu.Lock()
	defer p.mu.Unlock()

	if !p.running {
		return core.Result{}, fmt.Errorf("bridge %s: not running (call Start first)", p.id)
	}

	req := bridgeRequest{
		Operation: task.Operation,
		Params:    task.Params,
		Payload:   string(task.Payload),
	}

	reqJSON, err := json.Marshal(req)
	if err != nil {
		return core.Result{}, fmt.Errorf("bridge marshal: %w", err)
	}

	// Send request
	if _, err := fmt.Fprintf(p.stdin, "%s\n", reqJSON); err != nil {
		return core.Result{}, fmt.Errorf("bridge write: %w", err)
	}

	// Read response
	if !p.stdout.Scan() {
		return core.Result{}, fmt.Errorf("bridge %s: no response", p.id)
	}

	var resp bridgeResponse
	if err := json.Unmarshal(p.stdout.Bytes(), &resp); err != nil {
		return core.Result{}, fmt.Errorf("bridge unmarshal: %w", err)
	}

	if resp.Error != "" {
		return core.Result{Success: false, Output: resp.Error}, nil
	}

	return core.Result{
		Success:    resp.Success,
		Output:     resp.Output,
		Confidence: resp.Confidence,
		Details:    resp.Details,
	}, nil
}

// Stop terminates the Python subprocess.
func (p *PythonNeuron) Stop() error {
	p.mu.Lock()
	defer p.mu.Unlock()

	if !p.running {
		return nil
	}
	p.running = false
	p.stdin.Close()
	return p.cmd.Wait()
}
