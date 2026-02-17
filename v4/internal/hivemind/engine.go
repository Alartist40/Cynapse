// Package hivemind implements the workflow orchestration engine.
// It replaces the Python HiveMind class with goroutine-based concurrency.
package hivemind

import (
	"context"
	"database/sql"
	"encoding/json"
	"fmt"
	"log"
	"sync"
	"time"

	_ "github.com/mattn/go-sqlite3"

	"github.com/Alartist40/cynapse/internal/core"
	"github.com/Alartist40/cynapse/internal/core/validator"
	"github.com/Alartist40/cynapse/internal/techsupport"
)

// Config holds HiveMind runtime settings.
type Config struct {
	HiveName          string `json:"hive_name" yaml:"hive_name"`
	MaxConcurrentBees int    `json:"max_concurrent_bees" yaml:"max_concurrent_bees"`
	DBPath            string `json:"db_path" yaml:"db_path"`
	DocumentPath      string `json:"document_path" yaml:"document_path"`
	WorkflowPath      string `json:"workflow_path" yaml:"workflow_path"`
	SandboxEnabled    bool   `json:"sandbox_enabled" yaml:"sandbox_enabled"`
	AutoApprove       bool   `json:"auto_approve" yaml:"auto_approve"`
}

// DefaultConfig returns sensible defaults.
func DefaultConfig() Config {
	return Config{
		HiveName:          "cynapse_hive",
		MaxConcurrentBees: 5,
		DBPath:            "./hivemind.db",
		DocumentPath:      "./data/documents",
		WorkflowPath:      "./workflows",
		SandboxEnabled:    true,
		AutoApprove:       false,
	}
}

// EventBus broadcasts execution events to subscribers (e.g. the TUI).
type EventBus struct {
	mu   sync.RWMutex
	subs []chan Event
}

// Event is a message broadcast during workflow execution.
type Event struct {
	Type    string      `json:"type"` // "node_started", "node_completed", "node_failed", "bee_completed"
	NodeID  string      `json:"node_id,omitempty"`
	BeeID   string      `json:"bee_id,omitempty"`
	Payload interface{} `json:"payload,omitempty"`
}

// Subscribe returns a channel that receives events.
func (eb *EventBus) Subscribe() chan Event {
	eb.mu.Lock()
	defer eb.mu.Unlock()
	ch := make(chan Event, 64)
	eb.subs = append(eb.subs, ch)
	return ch
}

// Publish sends an event to all subscribers (non-blocking).
func (eb *EventBus) Publish(e Event) {
	eb.mu.RLock()
	defer eb.mu.RUnlock()
	for _, ch := range eb.subs {
		select {
		case ch <- e:
		default:
			// Drop if subscriber is slow
		}
	}
}

// Engine is the HiveMind orchestration engine.
type Engine struct {
	config    Config
	db        *sql.DB
	handlers  map[string]core.NodeHandler
	neurons   map[string]core.Neuron
	itMode    *techsupport.Executor
	validator *validator.Validator
	bus       *EventBus
	running   map[string]context.CancelFunc
	mu        sync.RWMutex
}

// New creates a new HiveMind engine.
func New(cfg Config) (*Engine, error) {
	db, err := sql.Open("sqlite3", cfg.DBPath)
	if err != nil {
		return nil, fmt.Errorf("failed to open database: %w", err)
	}

	reg := techsupport.NewRegistry("./data/techsupport")
	e := &Engine{
		config:    cfg,
		db:        db,
		handlers:  make(map[string]core.NodeHandler),
		neurons:   make(map[string]core.Neuron),
		itMode:    techsupport.NewExecutor(reg),
		validator: validator.New(),
		bus:       &EventBus{},
		running:   make(map[string]context.CancelFunc),
	}

	if err := e.initDB(); err != nil {
		return nil, err
	}

	e.registerDefaultHandlers()
	return e, nil
}

// Bus returns the event bus for TUI subscription.
func (e *Engine) Bus() *EventBus {
	return e.bus
}

// RegisterNeuron adds a neuron to the engine.
func (e *Engine) RegisterNeuron(n core.Neuron) {
	e.mu.Lock()
	defer e.mu.Unlock()
	e.neurons[n.ID()] = n
}

// RegisterHandler adds a node handler.
func (e *Engine) RegisterHandler(nodeType string, handler core.NodeHandler) {
	e.mu.Lock()
	defer e.mu.Unlock()
	e.handlers[nodeType] = handler
}

// ListNeurons returns the IDs of all registered neurons.
// ITMode returns the IT Support executor.
func (e *Engine) ITMode() *techsupport.Executor {
	return e.itMode
}

func (e *Engine) ListNeurons() []string {
	e.mu.RLock()
	defer e.mu.RUnlock()
	var ids []string
	for id := range e.neurons {
		ids = append(ids, id)
	}
	return ids
}

// ExecuteTask executes a single task on a registered neuron.
func (e *Engine) ExecuteTask(ctx context.Context, task core.Task) (core.Result, error) {
	e.mu.RLock()
	neuron, ok := e.neurons[task.NeuronID]
	e.mu.RUnlock()

	if !ok {
		return core.Result{}, fmt.Errorf("neuron %s not found", task.NeuronID)
	}

	return neuron.Execute(ctx, task)
}

// Execute runs a workflow, dispatching nodes concurrently where possible.
func (e *Engine) Execute(ctx context.Context, wf core.Workflow, initialInputs map[string]interface{}) (core.Result, error) {
	ctx, cancel := context.WithCancel(ctx)
	instanceID := fmt.Sprintf("%s_%d", wf.ID, time.Now().UnixMilli())

	e.mu.Lock()
	e.running[instanceID] = cancel
	e.mu.Unlock()

	defer func() {
		e.mu.Lock()
		delete(e.running, instanceID)
		e.mu.Unlock()
		cancel()
	}()

	e.bus.Publish(Event{Type: "bee_started", BeeID: instanceID})

	results := &sync.Map{}
	// Load initial inputs
	for k, v := range initialInputs {
		results.Store(k, v)
	}

	var executeErr error

	for _, node := range wf.Nodes {
		select {
		case <-ctx.Done():
			return core.Result{}, ctx.Err()
		default:
		}

		e.bus.Publish(Event{Type: "node_started", BeeID: instanceID, NodeID: node.ID})

		// Gather inputs from previous node outputs
		inputs := make(map[string]interface{})
		for key, ref := range node.Inputs {
			if val, ok := results.Load(ref); ok {
				inputs[key] = val
			}
		}

		// Get handler
		e.mu.RLock()
		handler, ok := e.handlers[node.Type]
		e.mu.RUnlock()

		if !ok {
			executeErr = fmt.Errorf("unknown node type: %s", node.Type)
			e.bus.Publish(Event{Type: "node_failed", BeeID: instanceID, NodeID: node.ID, Payload: executeErr.Error()})
			break
		}

		// Execute node with timeout
		nodeCtx, nodeCancel := context.WithTimeout(ctx, 30*time.Second)
		output, err := handler.Execute(nodeCtx, inputs, node.Config)
		nodeCancel()

		if err != nil {
			executeErr = fmt.Errorf("node %s failed: %w", node.ID, err)
			e.bus.Publish(Event{Type: "node_failed", BeeID: instanceID, NodeID: node.ID, Payload: err.Error()})
			break
		}

		// Store outputs
		for k, v := range output {
			results.Store(fmt.Sprintf("%s.%s", node.ID, k), v)
		}

		e.bus.Publish(Event{Type: "node_completed", BeeID: instanceID, NodeID: node.ID})
	}

	if executeErr != nil {
		e.bus.Publish(Event{Type: "bee_failed", BeeID: instanceID, Payload: executeErr.Error()})
		return core.Result{Success: false, Output: executeErr.Error()}, executeErr
	}

	e.bus.Publish(Event{Type: "bee_completed", BeeID: instanceID})

	// Try to extract final output
	var finalOutput string
	if wf.OutputNode != "" {
		if val, ok := results.Load(wf.OutputNode + ".output"); ok {
			finalOutput = fmt.Sprintf("%v", val)
		}
	}

	return core.Result{Success: true, Output: finalOutput}, nil
}

// Kill cancels a running workflow instance.
func (e *Engine) Kill(instanceID string) {
	e.mu.RLock()
	cancel, ok := e.running[instanceID]
	e.mu.RUnlock()
	if ok {
		cancel()
		log.Printf("[HiveMind] Cancelled %s", instanceID)
	}
}

// Close shuts down the engine gracefully.
func (e *Engine) Close() error {
	return e.db.Close()
}

func (e *Engine) initDB() error {
	schema := `
	CREATE TABLE IF NOT EXISTS workflows (
		id TEXT PRIMARY KEY,
		name TEXT,
		definition TEXT,
		created_at REAL
	);
	CREATE TABLE IF NOT EXISTS instances (
		instance_id TEXT PRIMARY KEY,
		workflow_id TEXT,
		state TEXT,
		context TEXT,
		current_node TEXT,
		start_time REAL,
		end_time REAL,
		logs TEXT
	);
	CREATE TABLE IF NOT EXISTS memory (
		id INTEGER PRIMARY KEY AUTOINCREMENT,
		query TEXT,
		response TEXT,
		correction TEXT,
		timestamp REAL,
		workflow_id TEXT
	);`
	_, err := e.db.Exec(schema)
	return err
}

// SaveWorkflow persists a workflow definition.
func (e *Engine) SaveWorkflow(wf core.Workflow) error {
	data, err := json.Marshal(wf)
	if err != nil {
		return err
	}
	_, err = e.db.Exec(
		"INSERT OR REPLACE INTO workflows (id, name, definition, created_at) VALUES (?, ?, ?, ?)",
		wf.ID, wf.Name, string(data), float64(time.Now().Unix()),
	)
	return err
}

// LoadWorkflow retrieves a workflow by ID.
func (e *Engine) LoadWorkflow(id string) (*core.Workflow, error) {
	var defJSON string
	err := e.db.QueryRow("SELECT definition FROM workflows WHERE id = ?", id).Scan(&defJSON)
	if err != nil {
		return nil, err
	}
	var wf core.Workflow
	if err := json.Unmarshal([]byte(defJSON), &wf); err != nil {
		return nil, err
	}
	return &wf, nil
}

func (e *Engine) registerDefaultHandlers() {
	e.handlers["output"] = &OutputHandler{}
	e.handlers["file_reader"] = &FileReaderHandler{}
	e.handlers["text_chunker"] = &TextChunkerHandler{}
	e.handlers["neuron"] = &NeuronHandler{engine: e}
	e.handlers["llm"] = &LLMHandler{}
	e.handlers["agent"] = &AgentHandler{}
}
