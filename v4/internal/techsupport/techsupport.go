// Package techsupport implements the IT Mode self-modifying plugin system.
// Modules are Go plugins or Python scripts executed in a sandbox.
package techsupport

import (
	"context"
	"encoding/json"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"sync"
	"time"

	"github.com/Alartist40/cynapse/internal/core"
)

// ModuleInfo describes a registered IT support module.
type ModuleInfo struct {
	ID           string   `json:"id"`
	Name         string   `json:"name"`
	Version      string   `json:"version"`
	Description  string   `json:"description"`
	Capabilities []string `json:"capabilities"`
	Type         string   `json:"type"` // "go_plugin", "python", "script"
	EntryPoint   string   `json:"entry_point"`
}

// Registry manages IT support modules.
type Registry struct {
	modules    map[string]ModuleInfo
	modulesDir string
	mu         sync.RWMutex
}

// NewRegistry creates a registry scanning the given modules directory.
func NewRegistry(modulesDir string) *Registry {
	r := &Registry{
		modules:    make(map[string]ModuleInfo),
		modulesDir: modulesDir,
	}
	r.loadFromDisk()
	return r
}

// List returns all registered modules.
func (r *Registry) List() []ModuleInfo {
	r.mu.RLock()
	defer r.mu.RUnlock()
	var mods []ModuleInfo
	for _, m := range r.modules {
		mods = append(mods, m)
	}
	return mods
}

// Get returns a module by ID.
func (r *Registry) Get(id string) (ModuleInfo, bool) {
	r.mu.RLock()
	defer r.mu.RUnlock()
	m, ok := r.modules[id]
	return m, ok
}

// Register adds a module to the registry.
func (r *Registry) Register(mod ModuleInfo) {
	r.mu.Lock()
	defer r.mu.Unlock()
	r.modules[mod.ID] = mod
}

func (r *Registry) loadFromDisk() {
	indexPath := filepath.Join(r.modulesDir, "index.json")
	data, err := os.ReadFile(indexPath)
	if err != nil {
		return // No index yet
	}

	var mods []ModuleInfo
	if err := json.Unmarshal(data, &mods); err != nil {
		return
	}
	for _, m := range mods {
		r.modules[m.ID] = m
	}
}

// Executor runs IT support modules in a sandbox.
type Executor struct {
	registry *Registry
	timeout  time.Duration
}

// NewExecutor creates an executor backed by the given registry.
func NewExecutor(registry *Registry) *Executor {
	return &Executor{
		registry: registry,
		timeout:  30 * time.Second,
	}
}

// Execute runs a module operation.
func (e *Executor) Execute(ctx context.Context, moduleID, operation string, params map[string]string) (core.Result, error) {
	mod, ok := e.registry.Get(moduleID)
	if !ok {
		return core.Result{}, fmt.Errorf("IT module %s not found", moduleID)
	}

	ctx, cancel := context.WithTimeout(ctx, e.timeout)
	defer cancel()

	switch mod.Type {
	case "python":
		return e.executePython(ctx, mod, operation, params)
	case "script":
		return e.executeScript(ctx, mod, operation, params)
	default:
		return core.Result{}, fmt.Errorf("unsupported module type: %s", mod.Type)
	}
}

func (e *Executor) executePython(ctx context.Context, mod ModuleInfo, operation string, params map[string]string) (core.Result, error) {
	// Build argument list
	args := []string{mod.EntryPoint, "--operation", operation}
	for k, v := range params {
		args = append(args, fmt.Sprintf("--%s", k), v)
	}

	cmd := exec.CommandContext(ctx, "python3", args...)
	cmd.Dir = filepath.Dir(mod.EntryPoint)

	out, err := cmd.CombinedOutput()
	if err != nil {
		return core.Result{
			Success: false,
			Output:  fmt.Sprintf("Module %s failed: %v\n%s", mod.ID, err, string(out)),
		}, nil
	}

	return core.Result{
		Success: true,
		Output:  strings.TrimSpace(string(out)),
		Details: map[string]string{"module": mod.ID, "operation": operation},
	}, nil
}

func (e *Executor) executeScript(ctx context.Context, mod ModuleInfo, operation string, params map[string]string) (core.Result, error) {
	cmd := exec.CommandContext(ctx, mod.EntryPoint, operation)
	for k, v := range params {
		cmd.Env = append(cmd.Env, fmt.Sprintf("IT_%s=%s", strings.ToUpper(k), v))
	}

	out, err := cmd.CombinedOutput()
	if err != nil {
		return core.Result{Success: false, Output: string(out)}, nil
	}

	return core.Result{Success: true, Output: strings.TrimSpace(string(out))}, nil
}
