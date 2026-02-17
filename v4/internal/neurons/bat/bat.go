// Package bat implements USB-based hardware authentication (Shamir Secret Sharing).
package bat

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"os"
	"path/filepath"
	"strings"

	"github.com/Alartist40/cynapse/internal/core"
)

// Neuron implements the Bat USB authentication neuron.
type Neuron struct {
	shardsDir string
	threshold int
}

// New creates a Bat neuron with the given shard directory and threshold.
func New(shardsDir string, threshold int) *Neuron {
	if threshold <= 0 {
		threshold = 2
	}
	return &Neuron{shardsDir: shardsDir, threshold: threshold}
}

func (n *Neuron) ID() string           { return "bat" }
func (n *Neuron) Name() string         { return "Bat — USB Hardware Auth" }
func (n *Neuron) Capabilities() []string { return []string{"usb_auth", "shard_verify", "list_devices"} }

func (n *Neuron) Execute(ctx context.Context, task core.Task) (core.Result, error) {
	switch task.Operation {
	case "authenticate":
		devices := strings.Split(task.Params["devices"], ",")
		authenticated, err := n.authenticate(devices)
		if err != nil {
			return core.Result{Success: false, Output: err.Error()}, nil
		}
		return core.Result{Success: authenticated, Output: fmt.Sprintf("Auth result: %v", authenticated)}, nil

	case "list_devices":
		entries, err := os.ReadDir(n.shardsDir)
		if err != nil {
			return core.Result{Success: false, Output: fmt.Sprintf("Cannot read shards dir: %v", err)}, nil
		}
		var devices []string
		for _, e := range entries {
			if strings.HasSuffix(e.Name(), ".shard") {
				devices = append(devices, strings.TrimSuffix(e.Name(), ".shard"))
			}
		}
		return core.Result{Success: true, Output: fmt.Sprintf("Devices: %s", strings.Join(devices, ", "))}, nil

	default:
		return core.Result{}, fmt.Errorf("bat: unknown operation %s", task.Operation)
	}
}

func (n *Neuron) authenticate(devices []string) (bool, error) {
	var shards [][]byte

	for _, dev := range devices {
		path := filepath.Join(n.shardsDir, dev+".shard")
		data, err := os.ReadFile(path)
		if err != nil {
			continue // Device not present
		}
		shards = append(shards, data)
	}

	if len(shards) < n.threshold {
		return false, fmt.Errorf("only %d of %d shards present", len(shards), n.threshold)
	}

	// Simplified: XOR-combine shards (production would use Shamir SSS)
	combined := make([]byte, len(shards[0]))
	copy(combined, shards[0])
	for _, s := range shards[1:] {
		for i := range combined {
			if i < len(s) {
				combined[i] ^= s[i]
			}
		}
	}

	hash := sha256.Sum256(combined)
	expected, err := os.ReadFile(filepath.Join(n.shardsDir, "master.hash"))
	if err != nil {
		return false, fmt.Errorf("cannot read master hash: %w", err)
	}

	return hex.EncodeToString(hash[:]) == strings.TrimSpace(string(expected)), nil
}
