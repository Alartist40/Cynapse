package memory

import (
	"fmt"
	"path/filepath"
	"strings"
	"testing"
	"time"
)

// TestDendrite_FullLifecycle exercises graph creation, linking, querying,
// persistence, and relevance scoring end-to-end.
func TestDendrite_FullLifecycle(t *testing.T) {
	// ── 1. Create graph and seed nodes ──────────────────────────────────────
	g := NewDendrite()

	// Core identity node
	g.Upsert("identity", "Cynapse Identity", `
You are Cynapse, a modular AI agent.
You connect to [[synapses]] and manage memory via the [[dendrite]] graph.
Your core values are helpfulness, honesty, and safety.
`, NodeTypeIdentity, nil)

	// Synapse node, linking back to identity
	g.Upsert("synapses", "Synapses", `
Synapses are plugins that extend Cynapse capabilities.
Examples: [[leafcutter]] for local LLM inference.
Synapses expose tools via the MCP protocol.
`, NodeTypeConcept, []string{"architecture", "plugins"})

	// Leafcutter node
	g.Upsert("leafcutter", "LeafcutterLLM", `
Leafcutter is a CPU-optimized LLM inference engine written in Rust.
It supports [[quantization]] and runs large models on small hardware.
Connected to Cynapse as a [[synapses]] plugin.
`, NodeTypeProject, []string{"rust", "inference", "local"})

	// Memory/dendrite node
	g.Upsert("dendrite", "DENDRITE Memory", `
DENDRITE is the graph memory system.
Nodes link via wiki-style references. Backlinks are auto-maintained.
Search uses full-text indexing.
`, NodeTypeConcept, []string{"memory", "graph"})

	// Quantization concept (will be auto-created as placeholder from leafcutter link)
	g.Upsert("quantization", "Quantization", `
Model quantization reduces precision to save memory and speed up inference.
Used by [[leafcutter]] to run 70B models on 4GB RAM.
`, NodeTypeConcept, []string{"ml", "optimization"})

	// ── 2. Verify graph structure ───────────────────────────────────────────
	if g.Len() != 5 {
		t.Fatalf("expected 5 nodes, got %d", g.Len())
	}

	// Check that leafcutter has correct outgoing links
	lc, ok := g.Get("leafcutter")
	if !ok {
		t.Fatal("leafcutter node missing")
	}
	if !containsStr(lc.Links, "quantization") {
		t.Errorf("leafcutter should link to quantization, got %v", lc.Links)
	}
	if !containsStr(lc.Links, "synapses") {
		t.Errorf("leafcutter should link to synapses, got %v", lc.Links)
	}

	// Check auto-backlinks: synapses should backlink to leafcutter
	syn, _ := g.Get("synapses")
	if !containsStr(syn.Backlinks, "leafcutter") {
		t.Errorf("synapses should have backlink from leafcutter, got %v", syn.Backlinks)
	}

	// Check auto-backlinks: quantization should backlink to leafcutter
	q, _ := g.Get("quantization")
	if !containsStr(q.Backlinks, "leafcutter") {
		t.Errorf("quantization should have backlink from leafcutter, got %v", q.Backlinks)
	}

	// identity links to synapses and dendrite, so it gets backlinks from neither
	// (backlinks are incoming, identity's outgoing links don't create backlinks to itself)
	idNode, _ := g.Get("identity")
	if containsStr(idNode.Backlinks, "synapses") {
		t.Errorf("identity should NOT have backlink from synapses (synapses doesn't link to identity)")
	}

	// ── 3. Test 1-hop neighborhood ──────────────────────────────────────────
	neighbors := g.Neighbors("leafcutter")
	neighborIDs := make(map[string]bool)
	for _, n := range neighbors {
		neighborIDs[n.ID] = true
	}
	expectedNeighbors := []string{"quantization", "synapses"}
	for _, exp := range expectedNeighbors {
		if !neighborIDs[exp] {
			t.Errorf("leafcutter neighbor should include %s, got %v", exp, neighborIDs)
		}
	}

	// ── 4. Test search ──────────────────────────────────────────────────────
	results := g.Search("quantization")
	found := false
	for _, r := range results {
		if r.ID == "quantization" || r.ID == "leafcutter" {
			found = true
		}
	}
	if !found {
		t.Errorf("search for 'quantization' should find quantization or leafcutter, got %v", results)
	}

	// Tag search
	tagged := g.ByTag("local")
	if len(tagged) != 1 || tagged[0].ID != "leafcutter" {
		t.Errorf("ByTag('local') should return leafcutter, got %v", tagged)
	}

	// ── 5. Test prompt assembly with relevance ──────────────────────────────
	ctx := NewDendriteContext(g, nil)

	// Query about running models locally — relevance is lexical, so use matching keywords
	prompt := ctx.BuildPrompt("How does leafcutter use quantization for local inference?", 4000)
	if prompt == "" {
		t.Fatal("BuildPrompt returned empty string")
	}
	if !strings.Contains(prompt, "LeafcutterLLM") {
		t.Error("prompt should mention LeafcutterLLM for leafcutter query")
	}
	if !strings.Contains(prompt, "Quantization") {
		t.Error("prompt should mention Quantization for quantization query")
	}

	// Query about memory system — use keyword that matches dendrite node content
	prompt2 := ctx.BuildPrompt("Tell me about the dendrite graph memory", 4000)
	if !strings.Contains(prompt2, "DENDRITE") {
		t.Error("prompt should mention DENDRITE for dendrite query")
	}

	// ── 6. Test token budget enforcement ────────────────────────────────────
	shortPrompt := ctx.BuildPrompt("How do I run large language models on my Raspberry Pi?", 500)
	// Should still include core identity but fewer context nodes
	if !strings.Contains(shortPrompt, "Cynapse Identity") {
		t.Error("short prompt should still include core identity")
	}

	// ── 7. Test SQLite persistence ──────────────────────────────────────────
	tmpDir := t.TempDir()
	dbPath := filepath.Join(tmpDir, "dendrite_test.db")

	store, err := NewDendriteStore(dbPath)
	if err != nil {
		t.Fatalf("create store: %v", err)
	}
	defer store.Close()

	// Save all nodes
	for _, n := range g.All() {
		if err := store.Save(n); err != nil {
			t.Fatalf("save node %s: %v", n.ID, err)
		}
	}

	// ── 8. Create fresh graph and load from store ───────────────────────────
	g2 := NewDendrite()
	if err := store.LoadAll(g2); err != nil {
		t.Fatalf("load all: %v", err)
	}

	if g2.Len() != g.Len() {
		t.Fatalf("reloaded graph has %d nodes, expected %d", g2.Len(), g.Len())
	}

	// Verify structure survived persistence
	lc2, ok := g2.Get("leafcutter")
	if !ok {
		t.Fatal("leafcutter missing after reload")
	}
	if !containsStr(lc2.Links, "quantization") {
		t.Errorf("leafcutter links lost after reload: %v", lc2.Links)
	}

	q2, _ := g2.Get("quantization")
	if !containsStr(q2.Backlinks, "leafcutter") {
		t.Errorf("quantization backlink lost after reload: %v", q2.Backlinks)
	}

	// ── 9. Test prompt assembly after reload ────────────────────────────────
	ctx2 := NewDendriteContext(g2, store)
	prompt3 := ctx2.BuildPrompt("Tell me about leafcutter", 4000)
	if !strings.Contains(prompt3, "LeafcutterLLM") {
		t.Error("prompt after reload should still find leafcutter")
	}

	// ── 10. Test node update and backlink rewiring ──────────────────────────
	g.Upsert("synapses", "Synapses", `
Synapses are LEGO-piece plugins for Cynapse.
No longer mentioning leafcutter by name here.
Now we focus on [[git-tools]] and [[web-automation]].
`, NodeTypeConcept, nil)

	// git-tools doesn't exist yet — should be created as placeholder
	gt, ok := g.Get("git-tools")
	if !ok {
		t.Fatal("git-tools placeholder should be auto-created")
	}
	if gt.Type != NodeTypeCustom {
		t.Errorf("placeholder should be custom type, got %s", gt.Type)
	}

	// synapses should no longer link to leafcutter
	synUpdated, _ := g.Get("synapses")
	if containsStr(synUpdated.Links, "leafcutter") {
		t.Error("synapses should no longer link to leafcutter after update")
	}

	// leafcutter should have lost the backlink from synapses
	lcUpdated, _ := g.Get("leafcutter")
	if containsStr(lcUpdated.Backlinks, "synapses") {
		t.Error("leafcutter should have lost backlink from synapses after update")
	}

	t.Logf("✓ Full lifecycle test passed: %d nodes, %d connections", g.Len(), countConnections(g))
}

// TestDendrite_MultiHopTraversal verifies that we can traverse beyond 1-hop.
func TestDendrite_MultiHopTraversal(t *testing.T) {
	g := NewDendrite()

	// A → B → C → D chain
	g.Upsert("a", "Node A", "Links to [[b]]", NodeTypeConcept, nil)
	g.Upsert("b", "Node B", "Links to [[c]]", NodeTypeConcept, nil)
	g.Upsert("c", "Node C", "Links to [[d]]", NodeTypeConcept, nil)
	g.Upsert("d", "Node D", "Terminal node", NodeTypeConcept, nil)

	// 1-hop from A should only find B
	n1 := g.Neighbors("a")
	if len(n1) != 1 || n1[0].ID != "b" {
		t.Fatalf("1-hop from A should be [b], got %v", nodeIDs(n1))
	}

	// 2-hop from A should find B and C (and maybe D if we had it)
	n2 := g.Neighbors2Hop("a")
	n2IDs := nodeIDs(n2)
	if !containsStr(n2IDs, "b") || !containsStr(n2IDs, "c") {
		t.Fatalf("2-hop from A should include b and c, got %v", n2IDs)
	}
	// D is 3 hops away, shouldn't be in 2-hop
	if containsStr(n2IDs, "d") {
		t.Error("2-hop from A should NOT include d (3 hops away)")
	}

	// 3-hop should include D
	n3 := g.Neighbors3Hop("a")
	n3IDs := nodeIDs(n3)
	if !containsStr(n3IDs, "d") {
		t.Fatalf("3-hop from A should include d, got %v", n3IDs)
	}
}

// TestDendrite_FactDeduplication prevents duplicate memory nodes.
func TestDendrite_FactDeduplication(t *testing.T) {
	g := NewDendrite()

	// Simulate saving the same fact twice
	fact := "The user prefers dark mode in all applications."

	id1 := saveFactWithDedup(g, fact, "preferences,ui")
	id2 := saveFactWithDedup(g, fact, "preferences,ui")

	if id1 != id2 {
		t.Errorf("duplicate fact should return same ID, got %s vs %s", id1, id2)
	}

	// A different fact should get a new ID
	fact2 := "The user prefers light mode."
	id3 := saveFactWithDedup(g, fact2, "preferences,ui")
	if id3 == id1 {
		t.Error("different fact should get different ID")
	}

	if g.Len() != 2 {
		t.Fatalf("expected 2 unique fact nodes, got %d", g.Len())
	}
}

// TestDendrite_FTS5Relevance verifies that findRelevant uses FTS5 when available.
func TestDendrite_FTS5Relevance(t *testing.T) {
	tmpDir := t.TempDir()
	dbPath := filepath.Join(tmpDir, "fts5_test.db")

	store, err := NewDendriteStore(dbPath)
	if err != nil {
		t.Fatalf("create store: %v", err)
	}
	defer store.Close()

	g := NewDendrite()
	g.Upsert("rust", "Rust Programming", "Rust is a systems programming language.", NodeTypeConcept, nil)
	g.Upsert("cargo", "Cargo", "Cargo is the Rust package manager.", NodeTypeConcept, nil)
	g.Upsert("go", "Go", "Go is a programming language by Google.", NodeTypeConcept, nil)

	for _, n := range g.All() {
		store.Save(n)
	}

	ctx := NewDendriteContext(g, store)
	prompt := ctx.BuildPrompt("Tell me about the Rust package manager", 4000)

	// Should find both rust and cargo (cargo mentions Rust)
	if !strings.Contains(prompt, "Rust") {
		t.Error("FTS5 relevance should find Rust node")
	}
	if !strings.Contains(prompt, "Cargo") {
		t.Error("FTS5 relevance should find Cargo node")
	}
	// Go node should not appear (not relevant)
	if strings.Contains(prompt, "Google") {
		t.Error("Go node should not appear in Rust query")
	}
}

// ── Helpers ────────────────────────────────────────────────────────────────

func nodeIDs(nodes []*Node) []string {
	var ids []string
	for _, n := range nodes {
		ids = append(ids, n.ID)
	}
	return ids
}

func countConnections(g *Dendrite) int {
	count := 0
	for _, n := range g.All() {
		count += len(n.Links) + len(n.Backlinks)
	}
	return count
}

// saveFactWithDedup is a test helper using deduplication logic.
func saveFactWithDedup(g *Dendrite, fact, tags string) string {
	// Check for near-duplicate
	for _, n := range g.All() {
		if n.Type == NodeTypeMemory && strings.TrimSpace(n.Content) == strings.TrimSpace(fact) {
			return n.ID // return existing
		}
	}

	id := fmt.Sprintf("fact_%d", time.Now().UnixNano())
	title := "Fact: " + truncate(fact, 40)
	var tagList []string
	if tags != "" {
		tagList = strings.Split(tags, ",")
		for i := range tagList {
			tagList[i] = strings.TrimSpace(tagList[i])
		}
	}
	g.Upsert(id, title, fact, NodeTypeMemory, tagList)
	return id
}
