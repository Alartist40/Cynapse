// Package core defines shared types and interfaces for Cynapse v4.
package core

import "context"

// Result is the standard output from any neuron or node execution.
type Result struct {
	Success    bool              `json:"success"`
	Output     string            `json:"output"`
	Data       []byte            `json:"data,omitempty"`
	Confidence float64           `json:"confidence,omitempty"`
	Details    map[string]string `json:"details,omitempty"`
}

// Task represents a unit of work dispatched to a neuron.
type Task struct {
	NeuronID  string            `json:"neuron_id"`
	Operation string            `json:"operation"`
	Payload   []byte            `json:"payload,omitempty"`
	Params    map[string]string `json:"params,omitempty"`
}

// Neuron is the interface that all neurons (Go-native or bridged) must implement.
type Neuron interface {
	ID() string
	Name() string
	Capabilities() []string
	Execute(ctx context.Context, task Task) (Result, error)
}

// Node represents a single step in a HiveMind workflow.
type Node struct {
	ID        string                 `json:"id" yaml:"id"`
	Type      string                 `json:"type" yaml:"type"`
	Config    map[string]interface{} `json:"config,omitempty" yaml:"config,omitempty"`
	Inputs    map[string]string      `json:"inputs,omitempty" yaml:"inputs,omitempty"`
	Condition string                 `json:"condition,omitempty" yaml:"condition,omitempty"`
	Next      []string               `json:"next,omitempty" yaml:"next,omitempty"`
}

// Workflow is a collection of nodes forming an execution graph.
type Workflow struct {
	ID         string `json:"id" yaml:"id"`
	Name       string `json:"name" yaml:"name"`
	Nodes      []Node `json:"nodes" yaml:"nodes"`
	OutputNode string `json:"output_node" yaml:"output_node"`
}

// BeeState enumerates the lifecycle states of a workflow instance.
type BeeState string

const (
	BeeStateQueued    BeeState = "queued"
	BeeStateRunning   BeeState = "running"
	BeeStatePaused    BeeState = "paused"
	BeeStateCompleted BeeState = "completed"
	BeeStateFailed    BeeState = "failed"
	BeeStateCancelled BeeState = "cancelled"
)

// BeeInstance is a running instance of a workflow.
type BeeInstance struct {
	InstanceID  string                 `json:"instance_id"`
	WorkflowID  string                 `json:"workflow_id"`
	State       BeeState               `json:"state"`
	Context     map[string]interface{} `json:"context,omitempty"`
	CurrentNode string                 `json:"current_node,omitempty"`
	StartTime   int64                  `json:"start_time"`
	EndTime     int64                  `json:"end_time,omitempty"`
	Logs        []string               `json:"logs,omitempty"`
}

// NodeHandler is the interface for execution logic of a single node type.
type NodeHandler interface {
	Execute(ctx context.Context, inputs map[string]interface{}, config map[string]interface{}) (map[string]interface{}, error)
}

// ValidationResult holds the outcome of a constitutional validation check.
type ValidationResult struct {
	Passed             bool     `json:"passed"`
	Violations         []string `json:"violations,omitempty"`
	CorrectedOutput    string   `json:"corrected_output,omitempty"`
	EscalationRequired bool     `json:"escalation_required,omitempty"`
}
