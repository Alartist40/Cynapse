package memory

import (
	"strings"
	"testing"
	"time"
)

func TestDendriteContext_PromptAssembly(t *testing.T) {
	d := NewDendrite()
	d.Upsert("identity", "Identity", "I am CYNAPSE.", NodeTypeIdentity, nil)
	d.Upsert("test_node", "Project Alpha", "Focus on scaling.", NodeTypeProject, []string{"scaling"})

	ctx := NewDendriteContext(d, nil)

	// Test general prompt (cached)
	p1 := ctx.BuildPrompt("", 1000)
	if !strings.Contains(p1, "Identity") {
		t.Error("expected identity in general prompt")
	}

	// Test message-specific prompt
	p2 := ctx.BuildPrompt("scaling Alpha", 1000)
	if !strings.Contains(p2, "Project Alpha") {
		t.Error("expected Project Alpha in message-specific prompt")
	}

	// Test cache invalidation
	d.Upsert("new_node", "New Info", "Something fresh.", NodeTypeConcept, nil)
	time.Sleep(10 * time.Millisecond) // Allow callback to run

	p3 := ctx.BuildPrompt("", 1000)
	if !strings.Contains(p3, "New Info") {
		t.Error("expected new info in prompt after invalidation")
	}
}

func TestDendriteContext_TokenBudget(t *testing.T) {
	d := NewDendrite()
	d.Upsert("identity", "Identity", "Long identity content...", NodeTypeIdentity, nil)
	d.Upsert("node1", "Node 1", "Content 1", NodeTypeConcept, nil)
	d.Upsert("node2", "Node 2", "Content 2", NodeTypeConcept, nil)

	ctx := NewDendriteContext(d, nil)

	// Very small budget should only include core
	p := ctx.BuildPrompt("", 50)
	if !strings.Contains(p, "Identity") {
		t.Error("expected identity even with small budget")
	}
}
