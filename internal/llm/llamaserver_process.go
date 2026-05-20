package llm

import (
	"fmt"
	"net"
	"net/http"
	"os"
	"os/exec"
	"path/filepath"
	"strconv"
	"time"
)

// llamaProcess manages a llama-server subprocess.
type llamaProcess struct {
	cmd     *exec.Cmd
	port    int
	baseURL string
	model   string
}

// newLlamaProcess creates a process manager for the given model.
func newLlamaProcess(modelPath string) *llamaProcess {
	return &llamaProcess{
		model: modelPath,
	}
}

// findLlamaServer looks for the llama-server binary in PATH or common locations.
func findLlamaServer() (string, error) {
	// Try PATH first
	if path, err := exec.LookPath("llama-server"); err == nil {
		return path, nil
	}
	// Common fallback locations
	candidates := []string{
		"/usr/local/bin/llama-server",
		"/usr/bin/llama-server",
		"./llama-server",
		"./llama.cpp/llama-server",
		"../llama.cpp/llama-server",
		"~/bin/llama-server",
	}
	for _, c := range candidates {
		if path, err := filepath.Abs(os.ExpandEnv(c)); err == nil {
			if _, err := os.Stat(path); err == nil {
				return path, nil
			}
		}
	}
	return "", fmt.Errorf("llama-server not found in PATH or common locations. Install llama.cpp or set llama_server_path in config")
}

// Start spawns llama-server with the model and waits for it to be healthy.
func (p *llamaProcess) Start(binaryPath string, gpuLayers, ctxSize, threads int, mmproj string) error {
	if binaryPath == "" {
		var err error
		binaryPath, err = findLlamaServer()
		if err != nil {
			return err
		}
	}

	port, err := findFreePort(11435)
	if err != nil {
		return fmt.Errorf("finding free port: %w", err)
	}
	p.port = port
	p.baseURL = fmt.Sprintf("http://127.0.0.1:%d", port)

	args := []string{
		"--model", p.model,
		"--port", strconv.Itoa(port),
		"--host", "127.0.0.1",
	}

	if gpuLayers > 0 {
		args = append(args, "--gpu-layers", strconv.Itoa(gpuLayers))
	}
	if ctxSize > 0 {
		args = append(args, "--ctx-size", strconv.Itoa(ctxSize))
	} else {
		args = append(args, "--ctx-size", "4096")
	}
	if threads > 0 {
		args = append(args, "--threads", strconv.Itoa(threads))
	}
	if mmproj != "" {
		args = append(args, "--mmproj", mmproj)
	}

	p.cmd = exec.Command(binaryPath, args...)
	p.cmd.Stdout = os.Stdout
	p.cmd.Stderr = os.Stderr

	if err := p.cmd.Start(); err != nil {
		return fmt.Errorf("starting llama-server: %w", err)
	}

	// Wait for health check
	if err := p.waitHealthy(60 * time.Second); err != nil {
		_ = p.Stop()
		return fmt.Errorf("llama-server failed to become ready: %w", err)
	}

	return nil
}

// Stop kills the llama-server process.
func (p *llamaProcess) Stop() error {
	if p.cmd == nil || p.cmd.Process == nil {
		return nil
	}
	if err := p.cmd.Process.Kill(); err != nil {
		return fmt.Errorf("killing llama-server: %w", err)
	}
	_, _ = p.cmd.Process.Wait()
	p.cmd = nil
	return nil
}

// BaseURL returns the HTTP endpoint for the running server.
func (p *llamaProcess) BaseURL() string {
	return p.baseURL
}

// waitHealthy polls the /health endpoint until success or timeout.
func (p *llamaProcess) waitHealthy(timeout time.Duration) error {
	client := &http.Client{Timeout: 2 * time.Second}
	deadline := time.Now().Add(timeout)

	for time.Now().Before(deadline) {
		resp, err := client.Get(p.baseURL + "/health")
		if err == nil {
			resp.Body.Close()
			if resp.StatusCode == http.StatusOK {
				return nil
			}
		}
		time.Sleep(500 * time.Millisecond)
	}
	return fmt.Errorf("timed out after %v", timeout)
}

// findFreePort finds an available TCP port starting from the given port.
func findFreePort(start int) (int, error) {
	for port := start; port < start+1000; port++ {
		addr := fmt.Sprintf("127.0.0.1:%d", port)
		l, err := net.Listen("tcp", addr)
		if err == nil {
			_ = l.Close()
			return port, nil
		}
	}
	return 0, fmt.Errorf("no free port found in range %d-%d", start, start+1000)
}
