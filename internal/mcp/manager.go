package mcp

import (
	"bufio"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"os/exec"
	"sync"
	"sync/atomic"

	"github.com/yourusername/cynapse/internal/config"
	"github.com/yourusername/cynapse/internal/llm"
)

// ─── JSON-RPC 2.0 types ───────────────────────────────────────────────────────

type rpcReq struct {
	JSONRPC string `json:"jsonrpc"`
	ID      int64  `json:"id"`
	Method  string `json:"method"`
	Params  any    `json:"params,omitempty"`
}

type rpcResp struct {
	JSONRPC string          `json:"jsonrpc"`
	ID      int64           `json:"id"`
	Result  json.RawMessage `json:"result,omitempty"`
	Error   *rpcError       `json:"error,omitempty"`
}

type rpcError struct {
	Code    int    `json:"code"`
	Message string `json:"message"`
}

// ─── MCP Server connection ────────────────────────────────────────────────────

type Server struct {
	name    string
	cmd     *exec.Cmd
	stdin   io.WriteCloser
	scanner *bufio.Scanner
	mu      sync.Mutex
	idSeq   atomic.Int64
	pending map[int64]chan rpcResp
}

func startServer(cfg config.MCPServer) (*Server, error) {
	if cfg.Command == "" {
		return nil, fmt.Errorf("MCP server %q has no command", cfg.Name)
	}

	cmd := exec.Command(cfg.Command, cfg.Args...)
	for k, v := range cfg.Env {
		cmd.Env = append(cmd.Env, k+"="+v)
	}

	stdin, err := cmd.StdinPipe()
	if err != nil {
		return nil, err
	}
	stdout, err := cmd.StdoutPipe()
	if err != nil {
		return nil, err
	}

	if err := cmd.Start(); err != nil {
		return nil, fmt.Errorf("starting MCP server %q: %w", cfg.Name, err)
	}

	s := &Server{
		name:    cfg.Name,
		cmd:     cmd,
		stdin:   stdin,
		scanner: bufio.NewScanner(stdout),
		pending: make(map[int64]chan rpcResp),
	}

	// Read responses in background
	go s.readLoop()

	// Initialise MCP session
	if err := s.initialize(); err != nil {
		s.Close()
		return nil, fmt.Errorf("initialising MCP server %q: %w", cfg.Name, err)
	}

	return s, nil
}

func (s *Server) initialize() error {
	params := map[string]any{
		"protocolVersion": "2024-11-05",
		"clientInfo":      map[string]any{"name": "cynapse", "version": "1.0.0"},
		"capabilities":    map[string]any{"tools": map[string]any{}},
	}
	_, err := s.call("initialize", params)
	if err != nil {
		return err
	}
	// Send initialized notification
	s.notify("notifications/initialized", nil)
	return nil
}

func (s *Server) call(method string, params any) (json.RawMessage, error) {
	id := s.idSeq.Add(1)
	ch := make(chan rpcResp, 1)

	s.mu.Lock()
	s.pending[id] = ch
	s.mu.Unlock()

	req := rpcReq{JSONRPC: "2.0", ID: id, Method: method, Params: params}
	data, err := json.Marshal(req)
	if err != nil {
		return nil, err
	}
	data = append(data, '\n')

	s.mu.Lock()
	_, err = s.stdin.Write(data)
	s.mu.Unlock()
	if err != nil {
		return nil, err
	}

	resp := <-ch
	if resp.Error != nil {
		return nil, fmt.Errorf("MCP error %d: %s", resp.Error.Code, resp.Error.Message)
	}
	return resp.Result, nil
}

func (s *Server) notify(method string, params any) {
	req := rpcReq{JSONRPC: "2.0", Method: method, Params: params}
	data, _ := json.Marshal(req)
	data = append(data, '\n')
	s.mu.Lock()
	s.stdin.Write(data)
	s.mu.Unlock()
}

func (s *Server) readLoop() {
	for s.scanner.Scan() {
		var resp rpcResp
		if err := json.Unmarshal(s.scanner.Bytes(), &resp); err != nil {
			continue
		}
		if resp.ID == 0 {
			continue // notification
		}
		s.mu.Lock()
		ch, ok := s.pending[resp.ID]
		if ok {
			delete(s.pending, resp.ID)
		}
		s.mu.Unlock()
		if ok {
			ch <- resp
		}
	}
}

// ListTools returns the tools advertised by this MCP server.
func (s *Server) ListTools() ([]llm.ToolSchema, error) {
	result, err := s.call("tools/list", nil)
	if err != nil {
		return nil, err
	}

	var resp struct {
		Tools []struct {
			Name        string         `json:"name"`
			Description string         `json:"description"`
			InputSchema map[string]any `json:"inputSchema"`
		} `json:"tools"`
	}
	if err := json.Unmarshal(result, &resp); err != nil {
		return nil, err
	}

	schemas := make([]llm.ToolSchema, 0, len(resp.Tools))
	for _, t := range resp.Tools {
		schemas = append(schemas, llm.ToolSchema{
			Name:        s.name + "__" + t.Name, // prefix with server name
			Description: fmt.Sprintf("[%s] %s", s.name, t.Description),
			Parameters:  t.InputSchema,
		})
	}
	return schemas, nil
}

// CallTool calls a tool on this MCP server.
func (s *Server) CallTool(name string, arguments json.RawMessage) (string, error) {
	// Strip server prefix
	toolName := name
	if len(s.name) > 0 && len(name) > len(s.name)+2 {
		toolName = name[len(s.name)+2:]
	}

	var args map[string]any
	json.Unmarshal(arguments, &args)

	params := map[string]any{
		"name":      toolName,
		"arguments": args,
	}

	result, err := s.call("tools/call", params)
	if err != nil {
		return "", err
	}

	var resp struct {
		Content []struct {
			Type string `json:"type"`
			Text string `json:"text"`
		} `json:"content"`
		IsError bool `json:"isError"`
	}
	if err := json.Unmarshal(result, &resp); err != nil {
		return string(result), nil
	}

	var parts []string
	for _, c := range resp.Content {
		if c.Type == "text" {
			parts = append(parts, c.Text)
		}
	}
	output := ""
	for _, p := range parts {
		output += p
	}
	if resp.IsError {
		return "", fmt.Errorf("MCP tool error: %s", output)
	}
	return output, nil
}

func (s *Server) Close() {
	s.stdin.Close()
	s.cmd.Wait()
}

// ─── Manager ─────────────────────────────────────────────────────────────────

type Manager struct {
	servers []*Server
}

func NewManager(cfg config.MCPConfig) *Manager {
	m := &Manager{}
	if !cfg.Enabled {
		return m
	}
	for _, sc := range cfg.Servers {
		srv, err := startServer(sc)
		if err != nil {
			log.Printf("[MCP] Failed to start server %q: %v", sc.Name, err)
			continue
		}
		m.servers = append(m.servers, srv)
		log.Printf("[MCP] Started server: %s", sc.Name)
	}
	return m
}

// New creates a new MCP manager from server configs (backward compatibility)
func New(servers []config.MCPServer) (*Manager, error) {
	cfg := config.MCPConfig{
		Enabled: true,
		Servers: servers,
	}
	return NewManager(cfg), nil
}

// AddServer dynamically adds a new MCP server to the manager
func (m *Manager) AddServer(cfg config.MCPServer) error {
	srv, err := startServer(cfg)
	if err != nil {
		return fmt.Errorf("starting MCP server %s: %w", cfg.Name, err)
	}
	
	m.servers = append(m.servers, srv)
	log.Printf("[MCP] Dynamically added server: %s", cfg.Name)
	return nil
}

// Shutdown closes all MCP servers (alias for Close for compatibility)
func (m *Manager) Shutdown() {
	m.Close()
}

// AllTools collects tool schemas from all connected MCP servers.
func (m *Manager) AllTools() []llm.ToolSchema {
	var all []llm.ToolSchema
	for _, s := range m.servers {
		tools, err := s.ListTools()
		if err != nil {
			log.Printf("[MCP] listing tools from %s: %v", s.name, err)
			continue
		}
		all = append(all, tools...)
	}
	return all
}

// Execute routes a tool call to the correct MCP server.
func (m *Manager) Execute(ctx context.Context, name string, arguments json.RawMessage) (string, bool, error) {
	for _, s := range m.servers {
		prefix := s.name + "__"
		if len(name) > len(prefix) && name[:len(prefix)] == prefix {
			result, err := s.CallTool(name, arguments)
			return result, true, err
		}
	}
	return "", false, nil // not an MCP tool
}

func (m *Manager) Close() {
	for _, s := range m.servers {
		s.Close()
	}
}
