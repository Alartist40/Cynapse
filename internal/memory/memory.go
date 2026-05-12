package memory

import (
	"context"
	"fmt"
	"log"
	"os"
	"path/filepath"
	"strings"
	"sync"
	"time"

	_ "github.com/mattn/go-sqlite3"
	"github.com/Alartist40/cynapse/internal/llm"
)

// ─── Persona Manager ─────────────────────────────────────────────────────────
// Manages the markdown files that define a device's personality and memory.
// The agent itself can call tools to update these files, enabling self-improvement.

type Persona struct {
	deviceID     string
	basePath     string
	defaultsPath string
	mu           sync.RWMutex

	// NEW: graph-based memory
	graph          *Dendrite
	store          *DendriteStore
	contextBuilder *DendriteContext
}

func NewPersona(deviceID, basePath, defaultsPath, dbPath string) (*Persona, error) {
	path := filepath.Join(basePath, deviceID)
	if err := os.MkdirAll(path, 0755); err != nil {
		return nil, err
	}
	os.MkdirAll(filepath.Join(path, "logs", "daily"), 0755)
	os.MkdirAll(filepath.Join(path, "logs", "heartbeat"), 0755)
	os.MkdirAll(filepath.Join(path, "skills"), 0755)

	graph := NewDendrite()

	store, err := NewDendriteStore(dbPath)
	if err != nil {
		return nil, fmt.Errorf("graph store: %w", err)
	}

	// Load persisted nodes into graph
	if err := store.LoadAll(graph); err != nil {
		log.Printf("WARNING: could not load graph nodes: %v", err)
	}

	p := &Persona{
		deviceID:       deviceID,
		basePath:       path,
		defaultsPath:   defaultsPath,
		graph:          graph,
		store:          store,
		contextBuilder: NewDendriteContext(graph, store),
	}

	// If graph is empty, seed from default markdown files
	if graph.Len() == 0 {
		p.seedFromMarkdownFiles()
	}

	return p, nil
}

// seedFromMarkdownFiles converts the old flat .md files into initial graph nodes.
// This runs ONCE on first boot, then never again (graph is persisted).
func (p *Persona) seedFromMarkdownFiles() {
	seed := []struct {
		file     string
		id       string
		title    string
		nodeType NodeType
	}{
		{"IDENTITY.md", "identity", "Identity", NodeTypeIdentity},
		{"SOUL.md", "soul", "Soul", NodeTypeIdentity},
		{"AGENTS.md", "agents", "Agent Rules", NodeTypeConcept},
		{"USER.md", "user", "User Profile", NodeTypePerson},
		{"TOOLS.md", "tools", "Tools", NodeTypeConcept},
		{"MEMORY.md", "memory_notes", "Memory", NodeTypeMemory},
		{"HEARTBEAT.md", "heartbeat", "Heartbeat", NodeTypeConcept},
	}

	for _, s := range seed {
		path := filepath.Join(p.defaultsPath, s.file)
		data, err := os.ReadFile(path)
		if err != nil {
			log.Printf("WARNING: seed file %s not found: %v", s.file, err)
			continue
		}
		p.graph.Upsert(s.id, s.title, string(data), s.nodeType, nil)
	}

	// Second pass: save all nodes to ensure auto-wired backlinks are persisted
	for _, n := range p.graph.All() {
		if err := p.store.Save(n); err != nil {
			log.Printf("WARNING: could not save seeded node %s: %v", n.ID, err)
		}
	}

	log.Printf("[PERSONA] seeded %d nodes from markdown defaults", len(seed))
}

// Graph exposes the DENDRITE memory graph (used by API server).
func (p *Persona) Graph() *Dendrite { return p.graph }

// Store exposes the graph store (used by API server).
func (p *Persona) Store() *DendriteStore { return p.store }

// CompileSystemPrompt replaces the old flat-file version.
// Pass userMessage to get relevant context; pass "" for the general cached prompt.
func (p *Persona) CompileSystemPrompt(userMessage string) string {
	return p.contextBuilder.BuildPrompt(userMessage, 6000)
}

// ReadFile reads any file in the persona directory.
func (p *Persona) ReadFile(name string) (string, error) {
	p.mu.RLock()
	defer p.mu.RUnlock()
	data, err := os.ReadFile(filepath.Join(p.basePath, name))
	if err != nil {
		return "", err
	}
	return string(data), nil
}

// WriteFile writes to a file in the persona directory and syncs to the graph if it's a core node.
func (p *Persona) WriteFile(name, content string) error {
	p.mu.Lock()
	defer p.mu.Unlock()

	// Mapping of filenames to graph node IDs and metadata
	nodeMap := map[string]struct {
		id       string
		title    string
		nodeType NodeType
	}{
		"IDENTITY.md":  {"identity", "Identity", NodeTypeIdentity},
		"SOUL.md":      {"soul", "Soul", NodeTypeIdentity},
		"AGENTS.md":    {"agents", "Agent Rules", NodeTypeConcept},
		"USER.md":      {"user", "User Profile", NodeTypePerson},
		"TOOLS.md":     {"tools", "Tools", NodeTypeConcept},
		"MEMORY.md":    {"memory_notes", "Memory", NodeTypeMemory},
		"HEARTBEAT.md": {"heartbeat", "Heartbeat", NodeTypeConcept},
	}

	if meta, ok := nodeMap[name]; ok {
		node := p.graph.Upsert(meta.id, meta.title, content, meta.nodeType, nil)
		if err := p.store.Save(node); err != nil {
			log.Printf("WARNING: could not sync %s to graph: %v", name, err)
		}
	}

	return os.WriteFile(filepath.Join(p.basePath, name), []byte(content), 0644)
}

// AppendDailyLog appends an entry to today's interaction log.
func (p *Persona) AppendDailyLog(entry string) error {
	p.mu.Lock()
	defer p.mu.Unlock()

	date := time.Now().Format("2006-01-02")
	path := filepath.Join(p.basePath, "logs", "daily", date+".md")

	f, err := os.OpenFile(path, os.O_APPEND|os.O_CREATE|os.O_WRONLY, 0644)
	if err != nil {
		return err
	}
	defer f.Close()

	ts := time.Now().Format("15:04:05")
	_, err = f.WriteString(fmt.Sprintf("\n## %s\n%s\n", ts, entry))
	return err
}

// ReadRecentLogs reads the daily log files from the last N days.
func (p *Persona) ReadRecentLogs(days int) string {
	p.mu.RLock()
	defer p.mu.RUnlock()

	var parts []string
	for i := 0; i < days; i++ {
		date := time.Now().AddDate(0, 0, -i).Format("2006-01-02")
		path := filepath.Join(p.basePath, "logs", "daily", date+".md")
		data, err := os.ReadFile(path)
		if err != nil {
			continue
		}
		parts = append(parts, fmt.Sprintf("## %s\n%s", date, string(data)))
	}
	return strings.Join(parts, "\n\n")
}

// Search performs a full-text search on the graph and returns a formatted string.
func (p *Persona) Search(query string, limit int) (string, error) {
	ids, err := p.store.FTSSearch(query, limit)
	if err != nil {
		return "", err
	}

	if len(ids) == 0 {
		return "(no memories found)", nil
	}

	var lines []string
	for _, id := range ids {
		if node, ok := p.graph.Get(id); ok {
			lines = append(lines, fmt.Sprintf("## %s\n%s", node.Title, node.Content))
		}
	}
	return strings.Join(lines, "\n\n"), nil
}

// SaveFact creates a new memory node in the graph for a discovered fact.
func (p *Persona) SaveFact(fact, tags string) error {
	id := fmt.Sprintf("fact_%d", time.Now().UnixNano())
	title := "Fact: " + truncate(fact, 40)
	
	var tagList []string
	if tags != "" {
		tagList = strings.Split(tags, ",")
		for i, t := range tagList {
			tagList[i] = strings.TrimSpace(t)
		}
	}

	node := p.graph.Upsert(id, title, fact, NodeTypeMemory, tagList)
	return p.store.Save(node)
}

func truncate(s string, n int) string {
	if len(s) <= n {
		return s
	}
	return s[:n] + "..."
}

// ─── Heartbeat Curator ────────────────────────────────────────────────────────
// Runs periodically, reads recent daily logs, and asks the LLM to update MEMORY.md.
// This is the self-improvement loop from Hermes Agent.

type Curator struct {
	persona  *Persona
	llmCli   llm.Client
	interval time.Duration
	stop     chan struct{}
}

func NewCurator(persona *Persona, client llm.Client, intervalHours int) *Curator {
	if intervalHours <= 0 {
		intervalHours = 6
	}
	return &Curator{
		persona:  persona,
		llmCli:   client,
		interval: time.Duration(intervalHours) * time.Hour,
		stop:     make(chan struct{}),
	}
}

func (c *Curator) Start(ctx context.Context) {
	go func() {
		ticker := time.NewTicker(c.interval)
		defer ticker.Stop()
		for {
			select {
			case <-ticker.C:
				if err := c.RunMaintenance(ctx); err != nil {
					log.Printf("[CURATOR] Maintenance error: %v", err)
				}
			case <-c.stop:
				return
			case <-ctx.Done():
				return
			}
		}
	}()
}

func (c *Curator) Stop() { close(c.stop) }

// RunMaintenance can also be triggered manually via the /heartbeat command.
func (c *Curator) RunMaintenance(ctx context.Context) error {
	log.Printf("[CURATOR] Running heartbeat maintenance for %s", c.persona.deviceID)

	recentLogs := c.persona.ReadRecentLogs(7)
	if strings.TrimSpace(recentLogs) == "" {
		log.Printf("[CURATOR] No recent logs, skipping")
		return nil
	}

	currentMemory, _ := c.persona.ReadFile("MEMORY.md")
	heartbeatInstructions, _ := c.persona.ReadFile("HEARTBEAT.md")

	if heartbeatInstructions == "" {
		heartbeatInstructions = "Review the daily logs and extract important facts, preferences, patterns, and decisions. Keep the memory concise and well-organised."
	}

	prompt := fmt.Sprintf(`You are maintaining the long-term memory of an AI assistant.

Current MEMORY.md:
---
%s
---

Recent daily interaction logs (last 7 days):
---
%s
---

Instructions from HEARTBEAT.md:
%s

Task: Update MEMORY.md based on the new interactions. Extract important facts, patterns, user preferences, decisions, and skills. Merge with existing memory. Keep it concise and well-organised.

Respond with ONLY the new content for MEMORY.md. No preamble, no markdown fences.`,
		currentMemory, recentLogs, heartbeatInstructions,
	)

	resp, err := c.llmCli.Chat(ctx, &llm.Request{
		SystemPrompt: "You are a memory curator. You extract and organise important information from conversation logs.",
		Messages:     []llm.Message{{Role: llm.RoleUser, Content: prompt}},
		MaxTokens:    4096,
		Temperature:  0.3,
	})
	if err != nil {
		return fmt.Errorf("LLM call failed: %w", err)
	}

	if strings.TrimSpace(resp.Content) == "" {
		return fmt.Errorf("LLM returned empty response")
	}

	if err := c.persona.WriteFile("MEMORY.md", resp.Content); err != nil {
		return fmt.Errorf("writing MEMORY.md: %w", err)
	}

	// Log the maintenance run
	logEntry := fmt.Sprintf("Heartbeat complete. Tokens used: in=%d out=%d. MEMORY.md updated.",
		resp.Usage.InputTokens, resp.Usage.OutputTokens)
	c.persona.AppendDailyLog("[CURATOR] " + logEntry)

	log.Printf("[CURATOR] %s", logEntry)
	return nil
}
