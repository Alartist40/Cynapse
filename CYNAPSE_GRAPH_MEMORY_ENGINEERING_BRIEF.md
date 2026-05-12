# CYNAPSE — Graph Memory System
## Engineering Implementation Brief

**Project:** CYNAPSE  
**Feature:** Obsidian-Style Knowledge Graph Memory  
**Version Target:** v2.0  
**Language:** Go (pure — no Rust, no Python)  
**Author:** Engineering Lead  
**Status:** Ready for implementation  

---

## ⚠️ CRITICAL NOTICE TO ENGINEERING TEAM

**We are REPLACING the current flat markdown file memory system entirely.**

The current system uses static `.md` files (`SOUL.md`, `IDENTITY.md`, `MEMORY.md`, etc.) compiled into a system prompt on every single message. This approach:

- Reads from disk on every message (slow on SD cards)
- Has no relationships between facts (flat, dumb)
- Cannot query context intelligently
- Cannot show connections visually
- Grows unbounded with no pruning

**The new system replaces ALL of this** with a graph-based knowledge store backed by SQLite, with an in-browser visual explorer accessible via `/memory` in the terminal.

**Do not preserve the old system. Do not try to run both in parallel. Replace it.**

The only exception: **CYNAPSE Mini** keeps the flat `.md` system because it targets ultra-low-RAM hardware (Pi Zero 2W tier) where the graph overhead is not justified. This brief is for **CYNAPSE only**.

---

## What We Are Building

### User Experience

```
User is chatting in CYNAPSE terminal:

  CYNAPSE > /memory

  ● Starting memory graph server...
  ◆ Memory graph → http://localhost:54231
  ● Browser opened. Return here to keep chatting.

User opens browser. Sees a beautiful force-directed graph.
Nodes are colour-coded by type (identity, person, project, concept, memory, event).
Edges show wiki-link connections between nodes.
User clicks a node → sees content, tags, links, backlinks.
User edits content in browser → agent uses updated memory immediately.
User closes browser → continues chatting in terminal.
```

### Architecture Overview

```
┌──────────────────────────────────────────────────────────────┐
│                    CYNAPSE TUI (existing)                     │
│  /memory command → spawns graph server → shows URL           │
└──────────────────┬───────────────────────────────────────────┘
                   │
                   ▼
┌──────────────────────────────────────────────────────────────┐
│              KnowledgeGraph (in-memory, thread-safe)          │
│  Nodes + wiki-link edges + backlinks + tag index              │
│  Invalidates prompt cache on every mutation                   │
└──────────┬───────────────────────┬───────────────────────────┘
           │                       │
           ▼                       ▼
┌──────────────────┐   ┌──────────────────────────────────────┐
│  GraphStore       │   │  ContextBuilder                       │
│  SQLite + FTS5    │   │  Assembles system prompt from graph   │
│  Persistence      │   │  Caches. Invalidates on graph change  │
└──────────────────┘   └──────────────────────────────────────┘
           │
           ▼
┌──────────────────────────────────────────────────────────────┐
│  API Server (local HTTP, random port)                         │
│  REST endpoints for graph CRUD                                │
│  Serves embedded web UI HTML at GET /                         │
└──────────────────────────────────────────────────────────────┘
           │
           ▼
┌──────────────────────────────────────────────────────────────┐
│  Browser — Force-Directed Graph (D3.js)                       │
│  Click to view · Edit · Create · Delete                       │
│  Auto-refreshes every 10s. Syncs live to running agent.       │
└──────────────────────────────────────────────────────────────┘
```

---

## File Structure

All new files go into the existing CYNAPSE repository. Here is exactly what to create and what to modify:

```
cynapse/
├── internal/
│   ├── memory/
│   │   ├── memory.go          ← MODIFY: wire in graph, replace CompileSystemPrompt
│   │   ├── graph.go           ← CREATE: in-memory knowledge graph
│   │   ├── graph_store.go     ← CREATE: SQLite persistence
│   │   └── context.go         ← CREATE: smart context assembly + caching
│   ├── api/
│   │   ├── server.go          ← CREATE: REST API server (new package)
│   │   └── web_ui.go          ← CREATE: embedded HTML/JS graph UI
│   └── agent/
│       └── agent.go           ← MODIFY: add StartGraphServer() method
├── internal/tui/
│   └── tui.go                 ← MODIFY: replace cmdMemory, add graphServerURL field
└── persona/
    └── defaults/              ← CONVERT: these .md files become initial graph nodes
        ├── AGENTS.md          → node id: "agents"
        ├── SOUL.md            → node id: "soul"
        ├── IDENTITY.md        → node id: "identity"
        ├── USER.md            → node id: "user"
        ├── TOOLS.md           → node id: "tools"
        ├── MEMORY.md          → node id: "memory_notes"
        └── HEARTBEAT.md       → node id: "heartbeat" (curator instructions)
```

---

## Part 1: `internal/memory/graph.go` — CREATE THIS FILE

This is the core in-memory graph. Thread-safe. No external dependencies.

```go
package memory

import (
    "regexp"
    "sort"
    "strings"
    "sync"
    "time"
)

// NodeType classifies what kind of knowledge a node holds.
type NodeType string

const (
    NodeTypeIdentity NodeType = "identity" // Core self / agent persona
    NodeTypePerson   NodeType = "person"   // A real person (user, contact)
    NodeTypeConcept  NodeType = "concept"  // Abstract idea or skill
    NodeTypeProject  NodeType = "project"  // A project or task
    NodeTypeEvent    NodeType = "event"    // Something that happened
    NodeTypeMemory   NodeType = "memory"   // Episodic memory entry
    NodeTypeCustom   NodeType = "custom"   // User-defined
)

// Node is a single knowledge node in the graph.
type Node struct {
    ID        string   `json:"id"`
    Title     string   `json:"title"`
    Content   string   `json:"content"`
    Type      NodeType `json:"type"`
    Tags      []string `json:"tags"`
    Links     []string `json:"links"`     // outgoing [[links]]
    Backlinks []string `json:"backlinks"` // auto-maintained incoming
    CreatedAt int64    `json:"created_at"`
    UpdatedAt int64    `json:"updated_at"`
}

// KnowledgeGraph is the in-memory graph. All operations are thread-safe.
type KnowledgeGraph struct {
    nodes       map[string]*Node
    mu          sync.RWMutex
    linkPattern *regexp.Regexp
    tagPattern  *regexp.Regexp
    onChange    []func()
}

func NewKnowledgeGraph() *KnowledgeGraph {
    return &KnowledgeGraph{
        nodes:       make(map[string]*Node),
        linkPattern: regexp.MustCompile(`\[\[([^\]|]+)(?:\|[^\]]+)?\]\]`),
        tagPattern:  regexp.MustCompile(`#([A-Za-z0-9_-]+)`),
    }
}

// OnChange registers a callback invoked on every mutation.
// Used by ContextBuilder to invalidate the prompt cache.
func (kg *KnowledgeGraph) OnChange(fn func()) {
    kg.mu.Lock()
    defer kg.mu.Unlock()
    kg.onChange = append(kg.onChange, fn)
}

func (kg *KnowledgeGraph) notify() {
    for _, fn := range kg.onChange {
        go fn()
    }
}

// Upsert creates or fully replaces a node and re-wires all backlinks.
func (kg *KnowledgeGraph) Upsert(id, title, content string, nodeType NodeType, tags []string) *Node {
    kg.mu.Lock()
    defer kg.mu.Unlock()

    now := time.Now().Unix()
    links := kg.parseLinks(content)
    if tags == nil {
        tags = kg.parseTags(content)
    }

    // Remove old backlinks from previous version of this node
    if old, ok := kg.nodes[id]; ok {
        for _, oldLink := range old.Links {
            if target, ok := kg.nodes[oldLink]; ok {
                target.Backlinks = removeStr(target.Backlinks, id)
            }
        }
    }

    node, exists := kg.nodes[id]
    if !exists {
        node = &Node{ID: id, CreatedAt: now}
        kg.nodes[id] = node
    }

    node.Title = title
    node.Content = content
    node.Type = nodeType
    node.Tags = tags
    node.Links = links
    node.UpdatedAt = now

    // Wire new backlinks
    for _, link := range links {
        if target, ok := kg.nodes[link]; ok {
            if !containsStr(target.Backlinks, id) {
                target.Backlinks = append(target.Backlinks, id)
            }
        }
    }

    kg.notify()
    return node
}

// Delete removes a node and cleans up all references in the graph.
func (kg *KnowledgeGraph) Delete(id string) bool {
    kg.mu.Lock()
    defer kg.mu.Unlock()

    node, ok := kg.nodes[id]
    if !ok {
        return false
    }

    for _, link := range node.Links {
        if target, ok := kg.nodes[link]; ok {
            target.Backlinks = removeStr(target.Backlinks, id)
        }
    }

    for _, n := range kg.nodes {
        n.Links = removeStr(n.Links, id)
    }

    delete(kg.nodes, id)
    kg.notify()
    return true
}

// Get returns a node by ID. Returns nil, false if not found.
func (kg *KnowledgeGraph) Get(id string) (*Node, bool) {
    kg.mu.RLock()
    defer kg.mu.RUnlock()
    n, ok := kg.nodes[id]
    return n, ok
}

// All returns every node sorted by UpdatedAt descending.
func (kg *KnowledgeGraph) All() []*Node {
    kg.mu.RLock()
    defer kg.mu.RUnlock()

    nodes := make([]*Node, 0, len(kg.nodes))
    for _, n := range kg.nodes {
        nodes = append(nodes, n)
    }
    sort.Slice(nodes, func(i, j int) bool {
        return nodes[i].UpdatedAt > nodes[j].UpdatedAt
    })
    return nodes
}

// Neighbors returns the 1-hop neighborhood of a node (links + backlinks combined).
func (kg *KnowledgeGraph) Neighbors(id string) []*Node {
    kg.mu.RLock()
    defer kg.mu.RUnlock()

    node, ok := kg.nodes[id]
    if !ok {
        return nil
    }

    seen := map[string]bool{id: true}
    var out []*Node

    for _, lid := range node.Links {
        if !seen[lid] {
            if n, ok := kg.nodes[lid]; ok {
                out = append(out, n)
                seen[lid] = true
            }
        }
    }
    for _, bid := range node.Backlinks {
        if !seen[bid] {
            if n, ok := kg.nodes[bid]; ok {
                out = append(out, n)
                seen[bid] = true
            }
        }
    }
    return out
}

// Search returns nodes whose title, content, or tags contain the query string.
func (kg *KnowledgeGraph) Search(query string) []*Node {
    kg.mu.RLock()
    defer kg.mu.RUnlock()

    q := strings.ToLower(strings.TrimSpace(query))
    if q == "" {
        return nil
    }

    var out []*Node
    for _, n := range kg.nodes {
        if strings.Contains(strings.ToLower(n.Title), q) ||
            strings.Contains(strings.ToLower(n.Content), q) ||
            containsStrFold(n.Tags, q) {
            out = append(out, n)
        }
    }
    return out
}

// ByTag returns all nodes that carry a specific tag.
func (kg *KnowledgeGraph) ByTag(tag string) []*Node {
    kg.mu.RLock()
    defer kg.mu.RUnlock()

    var out []*Node
    for _, n := range kg.nodes {
        if containsStrFold(n.Tags, tag) {
            out = append(out, n)
        }
    }
    return out
}

// Len returns the total number of nodes.
func (kg *KnowledgeGraph) Len() int {
    kg.mu.RLock()
    defer kg.mu.RUnlock()
    return len(kg.nodes)
}

// ── Internal parsing helpers ──────────────────────────────────────────────────

func (kg *KnowledgeGraph) parseLinks(content string) []string {
    matches := kg.linkPattern.FindAllStringSubmatch(content, -1)
    seen := map[string]bool{}
    var links []string
    for _, m := range matches {
        if len(m) > 1 {
            id := toNodeID(m[1])
            if !seen[id] {
                seen[id] = true
                links = append(links, id)
            }
        }
    }
    return links
}

func (kg *KnowledgeGraph) parseTags(content string) []string {
    matches := kg.tagPattern.FindAllStringSubmatch(content, -1)
    seen := map[string]bool{}
    var tags []string
    for _, m := range matches {
        if len(m) > 1 && !seen[m[1]] {
            seen[m[1]] = true
            tags = append(tags, m[1])
        }
    }
    return tags
}

// toNodeID normalises a wiki-link target into a stable lowercase_underscore ID.
func toNodeID(s string) string {
    s = strings.TrimSpace(s)
    s = strings.ToLower(s)
    s = strings.ReplaceAll(s, " ", "_")
    return s
}

// ── String slice helpers ──────────────────────────────────────────────────────

func containsStr(slice []string, item string) bool {
    for _, s := range slice {
        if s == item {
            return true
        }
    }
    return false
}

func containsStrFold(slice []string, item string) bool {
    for _, s := range slice {
        if strings.EqualFold(s, item) {
            return true
        }
    }
    return false
}

func removeStr(slice []string, item string) []string {
    out := slice[:0]
    for _, s := range slice {
        if s != item {
            out = append(out, s)
        }
    }
    return out
}
```

---

## Part 2: `internal/memory/graph_store.go` — CREATE THIS FILE

SQLite persistence with FTS5 full-text search. Uses WAL mode for concurrency safety.

```go
package memory

import (
    "database/sql"
    "encoding/json"
    "fmt"

    _ "github.com/mattn/go-sqlite3"
)

// GraphStore persists KnowledgeGraph nodes to SQLite.
type GraphStore struct {
    db *sql.DB
}

func NewGraphStore(dbPath string) (*GraphStore, error) {
    db, err := sql.Open("sqlite3", dbPath+"?_journal=WAL&_busy_timeout=5000")
    if err != nil {
        return nil, fmt.Errorf("open graph db: %w", err)
    }
    db.SetMaxOpenConns(1) // SQLite is single-writer

    gs := &GraphStore{db: db}
    if err := gs.migrate(); err != nil {
        return nil, fmt.Errorf("graph db migrate: %w", err)
    }
    return gs, nil
}

func (gs *GraphStore) migrate() error {
    _, err := gs.db.Exec(`
    CREATE TABLE IF NOT EXISTS graph_nodes (
        id         TEXT PRIMARY KEY,
        title      TEXT NOT NULL,
        content    TEXT NOT NULL DEFAULT '',
        type       TEXT NOT NULL DEFAULT 'custom',
        tags       TEXT NOT NULL DEFAULT '[]',
        links      TEXT NOT NULL DEFAULT '[]',
        backlinks  TEXT NOT NULL DEFAULT '[]',
        created_at INTEGER NOT NULL,
        updated_at INTEGER NOT NULL
    );

    CREATE INDEX IF NOT EXISTS idx_graph_updated ON graph_nodes(updated_at DESC);

    -- FTS5 for fast full-text search across all node content
    CREATE VIRTUAL TABLE IF NOT EXISTS graph_fts USING fts5(
        id         UNINDEXED,
        title,
        content,
        tags,
        tokenize = 'porter unicode61'
    );

    -- Keep FTS in sync automatically via triggers
    CREATE TRIGGER IF NOT EXISTS graph_nodes_ai
    AFTER INSERT ON graph_nodes BEGIN
        INSERT INTO graph_fts(id, title, content, tags)
        VALUES (new.id, new.title, new.content, new.tags);
    END;

    CREATE TRIGGER IF NOT EXISTS graph_nodes_au
    AFTER UPDATE ON graph_nodes BEGIN
        INSERT INTO graph_fts(graph_fts, rowid, id, title, content, tags)
        VALUES ('delete', old.rowid, old.id, old.title, old.content, old.tags);
        INSERT INTO graph_fts(id, title, content, tags)
        VALUES (new.id, new.title, new.content, new.tags);
    END;

    CREATE TRIGGER IF NOT EXISTS graph_nodes_ad
    AFTER DELETE ON graph_nodes BEGIN
        INSERT INTO graph_fts(graph_fts, rowid, id, title, content, tags)
        VALUES ('delete', old.rowid, old.id, old.title, old.content, old.tags);
    END;
    `)
    return err
}

// Save upserts a node into SQLite.
func (gs *GraphStore) Save(n *Node) error {
    tags, _ := json.Marshal(n.Tags)
    links, _ := json.Marshal(n.Links)
    backlinks, _ := json.Marshal(n.Backlinks)

    _, err := gs.db.Exec(`
        INSERT INTO graph_nodes
            (id, title, content, type, tags, links, backlinks, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            title      = excluded.title,
            content    = excluded.content,
            type       = excluded.type,
            tags       = excluded.tags,
            links      = excluded.links,
            backlinks  = excluded.backlinks,
            updated_at = excluded.updated_at
    `,
        n.ID, n.Title, n.Content, string(n.Type),
        string(tags), string(links), string(backlinks),
        n.CreatedAt, n.UpdatedAt,
    )
    return err
}

// Delete removes a node from SQLite.
func (gs *GraphStore) Delete(id string) error {
    _, err := gs.db.Exec(`DELETE FROM graph_nodes WHERE id = ?`, id)
    return err
}

// LoadAll hydrates all stored nodes directly into the graph's node map.
// Call this once at startup before serving any requests.
func (gs *GraphStore) LoadAll(kg *KnowledgeGraph) error {
    rows, err := gs.db.Query(`
        SELECT id, title, content, type, tags, links, backlinks, created_at, updated_at
        FROM graph_nodes
        ORDER BY updated_at DESC
    `)
    if err != nil {
        return err
    }
    defer rows.Close()

    for rows.Next() {
        n := &Node{}
        var nodeType string
        var tagsJSON, linksJSON, backlinksJSON string

        if err := rows.Scan(
            &n.ID, &n.Title, &n.Content, &nodeType,
            &tagsJSON, &linksJSON, &backlinksJSON,
            &n.CreatedAt, &n.UpdatedAt,
        ); err != nil {
            return err
        }

        n.Type = NodeType(nodeType)
        json.Unmarshal([]byte(tagsJSON), &n.Tags)
        json.Unmarshal([]byte(linksJSON), &n.Links)
        json.Unmarshal([]byte(backlinksJSON), &n.Backlinks)

        // Insert directly into node map to skip backlink recalculation
        // (backlinks are already stored correctly in the DB)
        kg.mu.Lock()
        kg.nodes[n.ID] = n
        kg.mu.Unlock()
    }
    return rows.Err()
}

// FTSSearch performs a full-text search and returns matching node IDs.
func (gs *GraphStore) FTSSearch(query string, limit int) ([]string, error) {
    if limit <= 0 {
        limit = 10
    }
    rows, err := gs.db.Query(`
        SELECT id FROM graph_fts
        WHERE graph_fts MATCH ?
        ORDER BY rank
        LIMIT ?
    `, query, limit)
    if err != nil {
        return nil, err
    }
    defer rows.Close()

    var ids []string
    for rows.Next() {
        var id string
        if err := rows.Scan(&id); err != nil {
            continue
        }
        ids = append(ids, id)
    }
    return ids, rows.Err()
}

func (gs *GraphStore) Close() error {
    return gs.db.Close()
}
```

---

## Part 3: `internal/memory/context.go` — CREATE THIS FILE

Replaces the flat `CompileSystemPrompt()` with intelligent graph-aware context assembly. Caches the compiled prompt and invalidates automatically when the graph changes.

```go
package memory

import (
    "fmt"
    "sort"
    "strings"
    "sync"
    "time"
)

const (
    defaultMaxTokens  = 6000
    coreNodeBudget    = 0.40 // 40% of token budget for core identity nodes
    contextNodeBudget = 0.60 // 60% for conversation-relevant nodes
)

// ContextBuilder assembles the LLM system prompt from graph nodes.
type ContextBuilder struct {
    graph *KnowledgeGraph
    store *GraphStore

    mu           sync.Mutex
    cachedPrompt string
    cachedAt     time.Time
    cacheTTL     time.Duration
    dirty        bool
}

func NewContextBuilder(graph *KnowledgeGraph, store *GraphStore) *ContextBuilder {
    cb := &ContextBuilder{
        graph:    graph,
        store:    store,
        cacheTTL: 5 * time.Minute,
        dirty:    true,
    }

    // Whenever the graph mutates, mark cache dirty
    graph.OnChange(func() {
        cb.mu.Lock()
        cb.dirty = true
        cb.mu.Unlock()
    })

    return cb
}

// BuildPrompt returns the system prompt.
// If userMessage is non-empty, it biases context toward relevant nodes.
// Otherwise returns a cached general-purpose prompt.
func (cb *ContextBuilder) BuildPrompt(userMessage string, maxTokens int) string {
    if maxTokens <= 0 {
        maxTokens = defaultMaxTokens
    }

    // Message-specific context skips the cache
    if strings.TrimSpace(userMessage) != "" {
        return cb.assemble(userMessage, maxTokens)
    }

    cb.mu.Lock()
    defer cb.mu.Unlock()

    if !cb.dirty && time.Since(cb.cachedAt) < cb.cacheTTL && cb.cachedPrompt != "" {
        return cb.cachedPrompt
    }

    prompt := cb.assemble("", maxTokens)
    cb.cachedPrompt = prompt
    cb.cachedAt = time.Now()
    cb.dirty = false
    return prompt
}

func (cb *ContextBuilder) assemble(userMessage string, maxTokens int) string {
    var parts []string
    used := 0

    coreBudget := int(float64(maxTokens) * coreNodeBudget)
    ctxBudget := maxTokens - coreBudget

    // Always include core identity nodes first
    coreIDs := []string{"identity", "soul", "agents", "tools"}
    for _, id := range coreIDs {
        node, ok := cb.graph.Get(id)
        if !ok {
            continue
        }
        part := fmt.Sprintf("## %s\n\n%s", node.Title, node.Content)
        cost := estimateTokens(part)
        if used+cost > coreBudget {
            break
        }
        parts = append(parts, part)
        used += cost
    }

    // Add conversation-relevant nodes
    if strings.TrimSpace(userMessage) != "" {
        candidates := cb.findRelevant(userMessage)
        scored := cb.score(candidates, userMessage)

        for _, sn := range scored {
            if containsStr(coreIDs, sn.node.ID) {
                continue // already included
            }
            part := fmt.Sprintf("## %s\n\n%s", sn.node.Title, sn.node.Content)
            cost := estimateTokens(part)
            if used+cost > used+ctxBudget {
                break
            }
            parts = append(parts, part)
            used += cost
        }
    } else {
        // No message context: add recently updated non-core nodes
        all := cb.graph.All()
        for _, node := range all {
            if containsStr(coreIDs, node.ID) {
                continue
            }
            part := fmt.Sprintf("## %s\n\n%s", node.Title, node.Content)
            cost := estimateTokens(part)
            if used+cost > maxTokens {
                break
            }
            parts = append(parts, part)
            used += cost
        }
    }

    if len(parts) == 0 {
        return ""
    }

    return strings.Join(parts, "\n\n---\n\n")
}

func (cb *ContextBuilder) findRelevant(userMessage string) []*Node {
    seen := map[string]bool{}
    var out []*Node

    addNode := func(n *Node) {
        if n != nil && !seen[n.ID] {
            seen[n.ID] = true
            out = append(out, n)
        }
    }

    // Graph content search
    for _, n := range cb.graph.Search(userMessage) {
        addNode(n)
        for _, neighbor := range cb.graph.Neighbors(n.ID) {
            addNode(neighbor)
        }
    }

    // Tag-based search from individual words
    words := strings.Fields(strings.ToLower(userMessage))
    for _, word := range words {
        if len(word) >= 3 {
            for _, n := range cb.graph.ByTag(word) {
                addNode(n)
            }
        }
    }

    return out
}

type scoredNode struct {
    node  *Node
    score float64
}

func (cb *ContextBuilder) score(nodes []*Node, query string) []scoredNode {
    q := strings.ToLower(query)
    now := time.Now().Unix()

    var scored []scoredNode
    for _, n := range nodes {
        s := 0.0

        if strings.Contains(strings.ToLower(n.Title), q) {
            s += 15
        }
        s += float64(strings.Count(strings.ToLower(n.Content), q)) * 2

        // Recency boost (linear decay, max 5 points over 7 days)
        age := float64(now-n.UpdatedAt) / 86400.0
        if age < 7 {
            s += (7 - age) * (5.0 / 7.0)
        }

        // Connectivity bonus — hub nodes carry more weight
        s += float64(len(n.Links)+len(n.Backlinks)) * 0.3

        // Node type priority
        switch n.Type {
        case NodeTypeIdentity:
            s += 10
        case NodeTypePerson:
            s += 5
        case NodeTypeProject:
            s += 3
        }

        scored = append(scored, scoredNode{node: n, score: s})
    }

    sort.Slice(scored, func(i, j int) bool {
        return scored[i].score > scored[j].score
    })
    return scored
}

// estimateTokens gives a rough token count (1 token ≈ 4 chars).
func estimateTokens(text string) int {
    return len(text) / 4
}
```

---

## Part 4: `internal/api/server.go` — CREATE THIS FILE (new package)

REST API that bridges the web UI to the live KnowledgeGraph. Serves the embedded HTML at `/`.

```go
package api

import (
    "context"
    "encoding/json"
    "fmt"
    "log"
    "net"
    "net/http"
    "strings"
    "time"

    "github.com/Alartist40/cynapse/internal/memory"
)

// Server exposes the knowledge graph over a local HTTP API
// and serves the embedded graph visualisation UI.
type Server struct {
    graph  *memory.KnowledgeGraph
    store  *memory.GraphStore
    server *http.Server
    url    string
}

func NewServer(graph *memory.KnowledgeGraph, store *memory.GraphStore) *Server {
    return &Server{graph: graph, store: store}
}

// URL returns the server's base URL. Empty until Start() is called.
func (s *Server) URL() string { return s.url }

// Start binds to a random available localhost port and begins serving.
// The returned URL is what the TUI displays to the user.
// The server shuts down when ctx is cancelled.
func (s *Server) Start(ctx context.Context) (string, error) {
    listener, err := net.Listen("tcp", "127.0.0.1:0")
    if err != nil {
        return "", fmt.Errorf("graph server bind: %w", err)
    }

    port := listener.Addr().(*net.TCPAddr).Port
    s.url = fmt.Sprintf("http://localhost:%d", port)

    mux := http.NewServeMux()
    mux.HandleFunc("/api/graph",      s.withCORS(s.handleGraph))
    mux.HandleFunc("/api/nodes",      s.withCORS(s.handleNodes))
    mux.HandleFunc("/api/nodes/",     s.withCORS(s.handleNode))
    mux.HandleFunc("/api/search",     s.withCORS(s.handleSearch))
    mux.HandleFunc("/api/neighbors/", s.withCORS(s.handleNeighbors))
    mux.HandleFunc("/",               s.handleUI)

    s.server = &http.Server{
        Handler:      mux,
        ReadTimeout:  10 * time.Second,
        WriteTimeout: 10 * time.Second,
    }

    go func() {
        if err := s.server.Serve(listener); err != nil && err != http.ErrServerClosed {
            log.Printf("[GRAPH API] error: %v", err)
        }
    }()

    go func() {
        <-ctx.Done()
        shutCtx, cancel := context.WithTimeout(context.Background(), 3*time.Second)
        defer cancel()
        s.server.Shutdown(shutCtx) //nolint:errcheck
    }()

    log.Printf("[GRAPH API] serving at %s", s.url)
    return s.url, nil
}

// ── Handlers ──────────────────────────────────────────────────────────────────

// GET /api/graph — returns {nodes, links} shaped for D3 force layout.
func (s *Server) handleGraph(w http.ResponseWriter, r *http.Request) {
    if r.Method != http.MethodGet {
        http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
        return
    }

    type d3Node struct {
        ID        string   `json:"id"`
        Title     string   `json:"title"`
        Type      string   `json:"type"`
        Tags      []string `json:"tags"`
        UpdatedAt int64    `json:"updated_at"`
        LinkCount int      `json:"link_count"`
    }
    type d3Link struct {
        Source string `json:"source"`
        Target string `json:"target"`
    }

    all := s.graph.All()
    var nodes []d3Node
    var links []d3Link
    seen := map[[2]string]bool{}

    for _, n := range all {
        nodes = append(nodes, d3Node{
            ID:        n.ID,
            Title:     n.Title,
            Type:      string(n.Type),
            Tags:      n.Tags,
            UpdatedAt: n.UpdatedAt,
            LinkCount: len(n.Links) + len(n.Backlinks),
        })
        for _, target := range n.Links {
            key := [2]string{n.ID, target}
            if !seen[key] {
                links = append(links, d3Link{Source: n.ID, Target: target})
                seen[key] = true
            }
        }
    }

    s.jsonResponse(w, map[string]any{"nodes": nodes, "links": links})
}

// GET /api/nodes — list all nodes.
// POST /api/nodes — create a new node.
func (s *Server) handleNodes(w http.ResponseWriter, r *http.Request) {
    switch r.Method {
    case http.MethodGet:
        s.jsonResponse(w, s.graph.All())

    case http.MethodPost:
        var body struct {
            ID      string   `json:"id"`
            Title   string   `json:"title"`
            Content string   `json:"content"`
            Type    string   `json:"type"`
            Tags    []string `json:"tags"`
        }
        if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
            http.Error(w, "invalid JSON", http.StatusBadRequest)
            return
        }
        if body.ID == "" || body.Title == "" {
            http.Error(w, "id and title required", http.StatusBadRequest)
            return
        }

        nodeType := memory.NodeType(body.Type)
        if nodeType == "" {
            nodeType = memory.NodeTypeCustom
        }

        node := s.graph.Upsert(body.ID, body.Title, body.Content, nodeType, body.Tags)
        if err := s.store.Save(node); err != nil {
            log.Printf("[GRAPH API] save: %v", err)
            http.Error(w, "storage error", http.StatusInternalServerError)
            return
        }
        w.WriteHeader(http.StatusCreated)
        s.jsonResponse(w, node)

    default:
        http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
    }
}

// GET /api/nodes/{id} — get one node.
// PUT /api/nodes/{id} — update a node.
// DELETE /api/nodes/{id} — delete a node.
func (s *Server) handleNode(w http.ResponseWriter, r *http.Request) {
    id := strings.TrimPrefix(r.URL.Path, "/api/nodes/")
    if id == "" {
        http.Error(w, "node id required", http.StatusBadRequest)
        return
    }

    switch r.Method {
    case http.MethodGet:
        node, ok := s.graph.Get(id)
        if !ok {
            http.Error(w, "not found", http.StatusNotFound)
            return
        }
        s.jsonResponse(w, node)

    case http.MethodPut:
        var body struct {
            Title   string   `json:"title"`
            Content string   `json:"content"`
            Type    string   `json:"type"`
            Tags    []string `json:"tags"`
        }
        if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
            http.Error(w, "invalid JSON", http.StatusBadRequest)
            return
        }

        nodeType := memory.NodeType(body.Type)
        if nodeType == "" {
            if existing, ok := s.graph.Get(id); ok {
                nodeType = existing.Type
            } else {
                nodeType = memory.NodeTypeCustom
            }
        }

        node := s.graph.Upsert(id, body.Title, body.Content, nodeType, body.Tags)
        if err := s.store.Save(node); err != nil {
            http.Error(w, "storage error", http.StatusInternalServerError)
            return
        }
        s.jsonResponse(w, node)

    case http.MethodDelete:
        s.graph.Delete(id)
        if err := s.store.Delete(id); err != nil {
            http.Error(w, "storage error", http.StatusInternalServerError)
            return
        }
        w.WriteHeader(http.StatusNoContent)

    default:
        http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
    }
}

// GET /api/search?q=... — search nodes.
func (s *Server) handleSearch(w http.ResponseWriter, r *http.Request) {
    if r.Method != http.MethodGet {
        http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
        return
    }
    s.jsonResponse(w, s.graph.Search(r.URL.Query().Get("q")))
}

// GET /api/neighbors/{id} — 1-hop neighborhood.
func (s *Server) handleNeighbors(w http.ResponseWriter, r *http.Request) {
    if r.Method != http.MethodGet {
        http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
        return
    }
    id := strings.TrimPrefix(r.URL.Path, "/api/neighbors/")
    s.jsonResponse(w, s.graph.Neighbors(id))
}

// GET / — serves the embedded single-page graph visualisation.
func (s *Server) handleUI(w http.ResponseWriter, r *http.Request) {
    w.Header().Set("Content-Type", "text/html; charset=utf-8")
    w.Write([]byte(webUI)) //nolint:errcheck
}

// ── Helpers ───────────────────────────────────────────────────────────────────

func (s *Server) jsonResponse(w http.ResponseWriter, v any) {
    w.Header().Set("Content-Type", "application/json")
    if err := json.NewEncoder(w).Encode(v); err != nil {
        log.Printf("[GRAPH API] encode: %v", err)
    }
}

func (s *Server) withCORS(next http.HandlerFunc) http.HandlerFunc {
    return func(w http.ResponseWriter, r *http.Request) {
        w.Header().Set("Access-Control-Allow-Origin", "*")
        w.Header().Set("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
        w.Header().Set("Access-Control-Allow-Headers", "Content-Type")
        if r.Method == http.MethodOptions {
            w.WriteHeader(http.StatusNoContent)
            return
        }
        next(w, r)
    }
}
```

---

## Part 5: `internal/api/web_ui.go` — CREATE THIS FILE

The complete graph visualisation web app, embedded as a Go string constant. No build step. No separate files. D3.js loads from CDN.

> **Note to team:** If you need the app to work offline, download D3.js and embed it here as a second Go string constant, inserting it into the HTML with a `<script>` tag inline. For now, CDN is fine.

```go
package api

// webUI is the single-file graph visualisation app served at GET /.
// It is embedded in the binary — no separate web/ directory needed.
const webUI = `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>CYNAPSE — Memory Graph</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/d3/7.9.0/d3.min.js"></script>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Space+Mono:ital,wght@0,400;0,700;1,400&family=Syne:wght@400;600;800&display=swap');

  :root {
    --bg:#080b10;--surface:#0d1117;--surface2:#161b24;--border:#1e2733;
    --purple:#9b59b6;--purple-dim:#6c3483;--orange:#e67e22;--orange-dim:#a04000;
    --cyan:#00d4ff;--green:#2ecc71;--red:#e74c3c;--text:#c9d1d9;
    --text-dim:#4a5568;--text-bright:#f0f6fc;
    --mono:'Space Mono',monospace;--sans:'Syne',sans-serif;
  }
  *{box-sizing:border-box;margin:0;padding:0}
  html,body{width:100%;height:100%;background:var(--bg);color:var(--text);font-family:var(--mono);overflow:hidden}
  #app{display:flex;width:100vw;height:100vh}

  /* Sidebar */
  #sidebar{width:320px;min-width:280px;background:var(--surface);border-right:1px solid var(--border);display:flex;flex-direction:column;z-index:10}
  #header{padding:20px 20px 16px;border-bottom:1px solid var(--border)}
  #logo{font-family:var(--sans);font-weight:800;font-size:18px;color:var(--purple);letter-spacing:.12em;text-transform:uppercase}
  #logo span{color:var(--orange)}
  #subtitle{font-size:10px;color:var(--text-dim);letter-spacing:.08em;margin-top:4px}
  #search-wrap{padding:12px 16px;border-bottom:1px solid var(--border)}
  #search{width:100%;background:var(--surface2);border:1px solid var(--border);border-radius:4px;color:var(--text);font-family:var(--mono);font-size:12px;padding:8px 10px;outline:none;transition:border-color .2s}
  #search:focus{border-color:var(--purple)}
  #search::placeholder{color:var(--text-dim)}
  #stats{display:flex;border-bottom:1px solid var(--border)}
  .stat{flex:1;text-align:center;padding:10px 0;border-right:1px solid var(--border)}
  .stat:last-child{border-right:none}
  .stat-val{font-family:var(--sans);font-size:20px;font-weight:800;color:var(--purple)}
  .stat-lbl{font-size:9px;color:var(--text-dim);letter-spacing:.1em;text-transform:uppercase}
  #node-list{flex:1;overflow-y:auto}
  #node-list::-webkit-scrollbar{width:4px}
  #node-list::-webkit-scrollbar-thumb{background:var(--border);border-radius:2px}
  .node-item{padding:10px 16px;border-bottom:1px solid var(--border);cursor:pointer;transition:background .15s;display:flex;align-items:flex-start;gap:10px}
  .node-item:hover{background:var(--surface2)}
  .node-item.active{background:rgba(155,89,182,.12);border-left:2px solid var(--purple)}
  .node-type-dot{width:8px;height:8px;border-radius:50%;margin-top:5px;flex-shrink:0}
  .node-item-content{flex:1;min-width:0}
  .node-item-title{font-family:var(--sans);font-size:13px;font-weight:600;color:var(--text-bright);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
  .node-item-meta{font-size:10px;color:var(--text-dim);margin-top:2px}

  /* Graph area */
  #graph-area{flex:1;position:relative;overflow:hidden}
  #canvas{width:100%;height:100%}
  #toolbar{position:absolute;top:16px;left:16px;display:flex;gap:8px;z-index:5}
  .tool-btn{background:var(--surface);border:1px solid var(--border);border-radius:4px;color:var(--text-dim);font-family:var(--mono);font-size:11px;padding:6px 12px;cursor:pointer;transition:all .15s}
  .tool-btn:hover{border-color:var(--purple);color:var(--purple)}
  #add-btn{position:absolute;bottom:20px;left:50%;transform:translateX(-50%);background:var(--purple);border:none;border-radius:4px;color:#fff;font-family:var(--mono);font-size:12px;padding:10px 24px;cursor:pointer;letter-spacing:.08em;transition:background .15s,transform .15s;z-index:5}
  #add-btn:hover{background:var(--purple-dim);transform:translateX(-50%) translateY(-1px)}
  #legend{position:absolute;bottom:20px;right:20px;background:var(--surface);border:1px solid var(--border);border-radius:6px;padding:12px 14px;z-index:5}
  .legend-title{font-size:9px;color:var(--text-dim);letter-spacing:.1em;text-transform:uppercase;margin-bottom:8px}
  .legend-item{display:flex;align-items:center;gap:8px;margin-bottom:5px;font-size:11px;color:var(--text-dim)}
  .legend-dot{width:10px;height:10px;border-radius:50%}

  /* Detail panel */
  #detail{position:absolute;right:0;top:0;bottom:0;width:380px;background:var(--surface);border-left:1px solid var(--border);display:flex;flex-direction:column;transform:translateX(100%);transition:transform .25s ease;z-index:20}
  #detail.open{transform:translateX(0)}
  #detail-header{padding:16px 20px;border-bottom:1px solid var(--border);display:flex;align-items:center;gap:12px}
  #detail-close{background:none;border:none;color:var(--text-dim);cursor:pointer;font-size:18px;line-height:1;margin-left:auto;transition:color .15s}
  #detail-close:hover{color:var(--text-bright)}
  #detail-title{font-family:var(--sans);font-size:16px;font-weight:800;color:var(--text-bright)}
  #detail-body{flex:1;overflow-y:auto;padding:16px 20px;display:flex;flex-direction:column;gap:16px}
  #detail-body::-webkit-scrollbar{width:3px}
  #detail-body::-webkit-scrollbar-thumb{background:var(--border)}
  .detail-label{font-size:10px;color:var(--text-dim);letter-spacing:.1em;text-transform:uppercase;margin-bottom:6px}
  #detail-content{background:var(--surface2);border:1px solid var(--border);border-radius:4px;padding:10px;font-size:12px;line-height:1.7;color:var(--text);white-space:pre-wrap;word-break:break-word;max-height:200px;overflow-y:auto}
  .tag-list{display:flex;flex-wrap:wrap;gap:6px}
  .tag{background:rgba(155,89,182,.18);border:1px solid var(--purple-dim);color:var(--purple);font-size:10px;padding:2px 8px;border-radius:99px}
  .link-list{display:flex;flex-direction:column;gap:4px}
  .link-item{background:var(--surface2);border:1px solid var(--border);border-radius:4px;padding:6px 10px;font-size:11px;color:var(--text);cursor:pointer;display:flex;align-items:center;gap:8px;transition:border-color .15s}
  .link-item:hover{border-color:var(--purple);color:var(--text-bright)}
  .link-arrow{color:var(--text-dim);font-size:10px}

  /* Edit form */
  #edit-form{display:none;flex-direction:column;gap:10px;padding:16px 20px;overflow-y:auto}
  #edit-form.active{display:flex}
  .form-label{font-size:10px;color:var(--text-dim);letter-spacing:.1em;text-transform:uppercase;margin-bottom:4px}
  .form-input,.form-textarea,.form-select{width:100%;background:var(--surface2);border:1px solid var(--border);border-radius:4px;color:var(--text);font-family:var(--mono);font-size:12px;padding:8px 10px;outline:none;transition:border-color .2s}
  .form-input:focus,.form-textarea:focus,.form-select:focus{border-color:var(--purple)}
  .form-textarea{resize:vertical;min-height:140px;line-height:1.6}
  .form-hint{font-size:10px;color:var(--text-dim);margin-top:4px}
  .btn{font-family:var(--mono);font-size:11px;padding:7px 14px;border-radius:4px;border:1px solid;cursor:pointer;letter-spacing:.05em;transition:all .15s}
  .btn-primary{background:var(--purple);border-color:var(--purple);color:#fff}
  .btn-primary:hover{background:var(--purple-dim)}
  .btn-ghost{background:transparent;border-color:var(--border);color:var(--text-dim)}
  .btn-ghost:hover{border-color:var(--text-dim);color:var(--text)}
  .btn-danger{background:transparent;border-color:var(--red);color:var(--red)}
  .btn-danger:hover{background:var(--red);color:#fff}
  .btn-row{display:flex;gap:8px}

  /* Graph elements */
  .g-link{stroke:var(--border);stroke-width:1.5;stroke-opacity:.7}
  .g-link.highlighted{stroke:var(--purple);stroke-opacity:1;stroke-width:2}
  .g-node circle{stroke-width:2;cursor:pointer}
  .g-node circle:hover{filter:brightness(1.3)}
  .g-node.selected circle{stroke:var(--text-bright);stroke-width:3}
  .g-label{font-family:var(--sans);font-size:11px;font-weight:600;fill:var(--text);pointer-events:none;text-anchor:middle}
  .g-count{font-family:var(--mono);font-size:9px;fill:var(--text-dim);pointer-events:none;text-anchor:middle}

  /* Toast */
  #toast{position:fixed;bottom:60px;left:50%;transform:translateX(-50%) translateY(20px);background:var(--surface2);border:1px solid var(--border);border-radius:4px;padding:10px 20px;font-size:12px;color:var(--text);opacity:0;transition:opacity .2s,transform .2s;pointer-events:none;z-index:100;white-space:nowrap}
  #toast.show{opacity:1;transform:translateX(-50%) translateY(0)}
</style>
</head>
<body>
<div id="app">
  <aside id="sidebar">
    <div id="header">
      <div id="logo">CYNAPSE <span>◆</span> MEMORY</div>
      <div id="subtitle">KNOWLEDGE GRAPH EXPLORER</div>
    </div>
    <div id="search-wrap">
      <input id="search" type="text" placeholder="Search nodes..." autocomplete="off">
    </div>
    <div id="stats">
      <div class="stat"><div class="stat-val" id="stat-nodes">0</div><div class="stat-lbl">Nodes</div></div>
      <div class="stat"><div class="stat-val" id="stat-links">0</div><div class="stat-lbl">Links</div></div>
      <div class="stat"><div class="stat-val" id="stat-tags">0</div><div class="stat-lbl">Tags</div></div>
    </div>
    <div id="node-list"></div>
  </aside>

  <div id="graph-area">
    <div id="toolbar">
      <button class="tool-btn" onclick="resetZoom()">⟳ Reset</button>
      <button class="tool-btn" id="pause-btn" onclick="toggleForce()">⏸ Pause</button>
    </div>
    <svg id="canvas"></svg>
    <button id="add-btn" onclick="openNewNodeForm()">+ New Node</button>
    <div id="legend">
      <div class="legend-title">Node Types</div>
      <div class="legend-item"><div class="legend-dot" style="background:#9b59b6"></div>Identity</div>
      <div class="legend-item"><div class="legend-dot" style="background:#e67e22"></div>Person</div>
      <div class="legend-item"><div class="legend-dot" style="background:#00d4ff"></div>Project</div>
      <div class="legend-item"><div class="legend-dot" style="background:#2ecc71"></div>Concept</div>
      <div class="legend-item"><div class="legend-dot" style="background:#e74c3c"></div>Memory</div>
      <div class="legend-item"><div class="legend-dot" style="background:#f39c12"></div>Event</div>
      <div class="legend-item"><div class="legend-dot" style="background:#4a5568"></div>Custom</div>
    </div>
  </div>

  <div id="detail">
    <div id="detail-header">
      <div class="node-type-dot" id="detail-type-dot"></div>
      <div id="detail-title">Node</div>
      <button id="detail-close" onclick="closeDetail()">✕</button>
    </div>
    <div id="detail-body">
      <div><div class="detail-label">Content</div><div id="detail-content"></div></div>
      <div id="detail-tags-section"><div class="detail-label">Tags</div><div class="tag-list" id="detail-tags"></div></div>
      <div id="detail-links-section"><div class="detail-label">Links To</div><div class="link-list" id="detail-links"></div></div>
      <div id="detail-backlinks-section"><div class="detail-label">Linked From</div><div class="link-list" id="detail-backlinks"></div></div>
      <div class="btn-row">
        <button class="btn btn-primary" onclick="openEditForm()">Edit</button>
        <button class="btn btn-danger" onclick="deleteNode()">Delete</button>
      </div>
    </div>
    <div id="edit-form">
      <div><div class="form-label">Title</div><input class="form-input" id="edit-title" type="text" placeholder="Node title"></div>
      <div>
        <div class="form-label">Type</div>
        <select class="form-select" id="edit-type">
          <option value="identity">Identity</option><option value="person">Person</option>
          <option value="project">Project</option><option value="concept">Concept</option>
          <option value="memory">Memory</option><option value="event">Event</option>
          <option value="custom">Custom</option>
        </select>
      </div>
      <div>
        <div class="form-label">Content</div>
        <textarea class="form-textarea" id="edit-content" placeholder="Markdown content. Use [[node-id]] to link. Use #tag for tags."></textarea>
        <div class="form-hint">[[node-id]] creates links · #tag adds tags</div>
      </div>
      <div class="btn-row">
        <button class="btn btn-primary" onclick="saveNode()">Save</button>
        <button class="btn btn-ghost" onclick="cancelEdit()">Cancel</button>
      </div>
    </div>
  </div>
</div>
<div id="toast"></div>

<script>
const TYPE_COLORS={identity:'#9b59b6',person:'#e67e22',project:'#00d4ff',concept:'#2ecc71',memory:'#e74c3c',event:'#f39c12',custom:'#4a5568'};
function typeColor(t){return TYPE_COLORS[t]||TYPE_COLORS.custom}

let graphData={nodes:[],links:[]},allNodes=[],selected=null,simulation=null,svg,g,linkSel,nodeSel,forcePaused=false,zoom,isNewNode=false;

window.addEventListener('DOMContentLoaded',async()=>{initGraph();await loadData();setInterval(loadData,10000)});

async function loadData(){
  try{
    const[gr,nr]=await Promise.all([fetch('/api/graph'),fetch('/api/nodes')]);
    graphData=await gr.json();allNodes=await nr.json();
    updateStats();renderNodeList(allNodes);updateGraph();
  }catch(e){toast('⚠ Cannot reach API')}
}

function updateStats(){
  document.getElementById('stat-nodes').textContent=graphData.nodes.length;
  document.getElementById('stat-links').textContent=graphData.links.length;
  const ts=new Set();allNodes.forEach(n=>(n.tags||[]).forEach(t=>ts.add(t)));
  document.getElementById('stat-tags').textContent=ts.size;
}

function renderNodeList(nodes){
  const list=document.getElementById('node-list');list.innerHTML='';
  (nodes||[]).forEach(n=>{
    const item=document.createElement('div');item.className='node-item'+(selected&&selected.id===n.id?' active':'');item.dataset.id=n.id;item.onclick=()=>selectNode(n.id);
    const dot=document.createElement('div');dot.className='node-type-dot';dot.style.background=typeColor(n.type);
    const content=document.createElement('div');content.className='node-item-content';
    const title=document.createElement('div');title.className='node-item-title';title.textContent=n.title||n.id;
    const meta=document.createElement('div');meta.className='node-item-meta';
    const lc=(n.links||[]).length+(n.backlinks||[]).length;
    meta.textContent=n.type+(lc?'  ·  '+lc+' connections':'');
    content.appendChild(title);content.appendChild(meta);item.appendChild(dot);item.appendChild(content);list.appendChild(item);
  });
}

function initGraph(){
  const area=document.getElementById('graph-area');
  const w=area.clientWidth,h=area.clientHeight;
  svg=d3.select('#canvas').attr('width',w).attr('height',h);
  const defs=svg.append('defs');
  const rg=defs.append('radialGradient').attr('id','bg-g').attr('cx','50%').attr('cy','50%').attr('r','70%');
  rg.append('stop').attr('offset','0%').attr('stop-color','#0d1117');
  rg.append('stop').attr('offset','100%').attr('stop-color','#080b10');
  svg.append('rect').attr('width',w).attr('height',h).attr('fill','url(#bg-g)');
  zoom=d3.zoom().scaleExtent([0.1,5]).on('zoom',e=>g.attr('transform',e.transform));
  svg.call(zoom);g=svg.append('g');
  g.append('g').attr('class','links-layer');g.append('g').attr('class','nodes-layer');
  simulation=d3.forceSimulation()
    .force('link',d3.forceLink().id(d=>d.id).distance(130))
    .force('charge',d3.forceManyBody().strength(-400))
    .force('center',d3.forceCenter(w/2,h/2))
    .force('collision',d3.forceCollide(42));
  window.addEventListener('resize',()=>{
    const nw=area.clientWidth,nh=area.clientHeight;
    svg.attr('width',nw).attr('height',nh);
    simulation.force('center',d3.forceCenter(nw/2,nh/2)).alpha(0.1).restart();
  });
}

function updateGraph(){
  const nodes=(graphData.nodes||[]).map(d=>({...d}));
  const links=(graphData.links||[]).map(d=>({...d}));
  const pos={};
  if(simulation.nodes){simulation.nodes().forEach(n=>{pos[n.id]={x:n.x,y:n.y}})}
  nodes.forEach(n=>{if(pos[n.id]){n.x=pos[n.id].x;n.y=pos[n.id].y}});

  const defs=svg.select('defs');
  if(defs.select('#arrow').empty()){
    defs.append('marker').attr('id','arrow').attr('viewBox','0 -4 8 8').attr('refX',22).attr('refY',0).attr('markerWidth',6).attr('markerHeight',6).attr('orient','auto')
      .append('path').attr('d','M0,-4L8,0L0,4').attr('fill','#1e2733');
  }

  linkSel=g.select('.links-layer').selectAll('.g-link').data(links,d=>d.source+'-'+d.target);
  linkSel.exit().remove();
  linkSel=linkSel.enter().append('line').attr('class','g-link').attr('marker-end','url(#arrow)').merge(linkSel);

  const ng=g.select('.nodes-layer').selectAll('.g-node').data(nodes,d=>d.id);
  ng.exit().remove();
  const entered=ng.enter().append('g').attr('class','g-node')
    .call(d3.drag().on('start',dragStart).on('drag',dragging).on('end',dragEnd))
    .on('click',(e,d)=>{e.stopPropagation();selectNode(d.id)});
  entered.append('circle');
  entered.append('text').attr('class','g-label').attr('dy',28);
  entered.append('text').attr('class','g-count').attr('dy',40);
  nodeSel=entered.merge(ng);
  nodeSel.select('circle').attr('r',d=>14+Math.min((d.link_count||0)*1.5,14)).attr('fill',d=>typeColor(d.type)).attr('fill-opacity',.85).attr('stroke',d=>typeColor(d.type));
  nodeSel.select('.g-label').text(d=>(d.title||d.id).length>14?(d.title||d.id).slice(0,14)+'…':d.title||d.id);
  nodeSel.select('.g-count').text(d=>(d.link_count||0)>0?d.link_count+' links':'');
  svg.on('click',()=>{if(selected){selected=null;updateSel()}});
  simulation.nodes(nodes).on('tick',ticked);
  simulation.force('link').links(links);
  simulation.alpha(0.3).restart();
}

function ticked(){
  linkSel.attr('x1',d=>d.source.x).attr('y1',d=>d.source.y).attr('x2',d=>d.target.x).attr('y2',d=>d.target.y);
  nodeSel.attr('transform',d=>'translate('+d.x+','+d.y+')');
}
function dragStart(e,d){if(!e.active)simulation.alphaTarget(0.3).restart();d.fx=d.x;d.fy=d.y}
function dragging(e,d){d.fx=e.x;d.fy=e.y}
function dragEnd(e,d){if(!e.active)simulation.alphaTarget(0);d.fx=null;d.fy=null}
function resetZoom(){svg.transition().duration(500).call(zoom.transform,d3.zoomIdentity)}
function toggleForce(){
  forcePaused=!forcePaused;
  const btn=document.getElementById('pause-btn');
  if(forcePaused){simulation.stop();btn.textContent='▶ Resume'}
  else{simulation.alphaTarget(0.1).restart();btn.textContent='⏸ Pause'}
}
function updateSel(){nodeSel&&nodeSel.classed('selected',d=>selected&&d.id===selected.id)}

async function selectNode(id){
  try{
    const r=await fetch('/api/nodes/'+id);if(!r.ok)return;
    selected=await r.json();openDetail(selected);updateSel();
    linkSel&&linkSel.classed('highlighted',d=>{
      const s=typeof d.source==='object'?d.source.id:d.source;
      const t=typeof d.target==='object'?d.target.id:d.target;
      return s===id||t===id;
    });
    document.querySelectorAll('.node-item').forEach(el=>el.classList.toggle('active',el.dataset.id===id));
  }catch(e){console.error(e)}
}

function openDetail(node){
  const panel=document.getElementById('detail');
  document.getElementById('edit-form').classList.remove('active');
  document.getElementById('detail-body').style.display='flex';
  document.getElementById('detail-title').textContent=node.title;
  document.getElementById('detail-type-dot').style.background=typeColor(node.type);
  document.getElementById('detail-content').textContent=node.content||'(empty)';
  const tagsEl=document.getElementById('detail-tags');tagsEl.innerHTML='';
  (node.tags||[]).forEach(t=>{const el=document.createElement('span');el.className='tag';el.textContent='#'+t;tagsEl.appendChild(el)});
  document.getElementById('detail-tags-section').style.display=(node.tags||[]).length?'block':'none';
  renderLinkList('detail-links',node.links||[],'→');
  document.getElementById('detail-links-section').style.display=(node.links||[]).length?'block':'none';
  renderLinkList('detail-backlinks',node.backlinks||[],'←');
  document.getElementById('detail-backlinks-section').style.display=(node.backlinks||[]).length?'block':'none';
  panel.classList.add('open');
}

function renderLinkList(cid,ids,arrow){
  const el=document.getElementById(cid);el.innerHTML='';
  ids.forEach(id=>{
    const node=allNodes.find(n=>n.id===id);
    const item=document.createElement('div');item.className='link-item';item.onclick=()=>selectNode(id);
    const dot=document.createElement('div');dot.className='node-type-dot';dot.style.background=typeColor(node?node.type:'custom');
    const ar=document.createElement('span');ar.className='link-arrow';ar.textContent=arrow;
    const label=document.createElement('span');label.textContent=node?node.title:id;
    item.appendChild(dot);item.appendChild(ar);item.appendChild(label);el.appendChild(item);
  });
}

function closeDetail(){
  document.getElementById('detail').classList.remove('open');
  selected=null;updateSel();
  linkSel&&linkSel.classed('highlighted',false);
  document.querySelectorAll('.node-item').forEach(el=>el.classList.remove('active'));
}

function openEditForm(){
  if(!selected)return;isNewNode=false;
  document.getElementById('edit-title').value=selected.title;
  document.getElementById('edit-type').value=selected.type||'custom';
  document.getElementById('edit-content').value=selected.content;
  document.getElementById('detail-body').style.display='none';
  document.getElementById('edit-form').classList.add('active');
}

function openNewNodeForm(){
  isNewNode=true;selected=null;closeDetail();
  document.getElementById('edit-title').value='';
  document.getElementById('edit-type').value='custom';
  document.getElementById('edit-content').value='';
  document.getElementById('detail-body').style.display='none';
  document.getElementById('edit-form').classList.add('active');
  document.getElementById('detail').classList.add('open');
  document.getElementById('detail-title').textContent='New Node';
}

function cancelEdit(){
  document.getElementById('edit-form').classList.remove('active');
  if(selected){document.getElementById('detail-body').style.display='flex'}
  else{document.getElementById('detail').classList.remove('open')}
}

async function saveNode(){
  const title=document.getElementById('edit-title').value.trim();
  const type=document.getElementById('edit-type').value;
  const content=document.getElementById('edit-content').value;
  if(!title){toast('Title is required');return}
  try{
    if(isNewNode){
      const id=title.toLowerCase().replace(/\s+/g,'_').replace(/[^a-z0-9_-]/g,'');
      const r=await fetch('/api/nodes',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id,title,type,content})});
      if(!r.ok)throw new Error(await r.text());
      toast('✓ Node created');
    }else{
      const r=await fetch('/api/nodes/'+selected.id,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({title,type,content})});
      if(!r.ok)throw new Error(await r.text());
      toast('✓ Saved');
    }
    document.getElementById('edit-form').classList.remove('active');
    await loadData();
    if(!isNewNode&&selected)selectNode(selected.id);else closeDetail();
  }catch(e){toast('Error: '+e.message)}
}

async function deleteNode(){
  if(!selected)return;
  if(!confirm('Delete "'+selected.title+'"?'))return;
  try{
    const r=await fetch('/api/nodes/'+selected.id,{method:'DELETE'});
    if(!r.ok)throw new Error(await r.text());
    toast('✓ Deleted');closeDetail();await loadData();
  }catch(e){toast('Error: '+e.message)}
}

document.getElementById('search').addEventListener('input',async e=>{
  const q=e.target.value.trim();
  if(!q){renderNodeList(allNodes);nodeSel&&nodeSel.select('circle').attr('fill-opacity',.85);return}
  try{
    const r=await fetch('/api/search?q='+encodeURIComponent(q));
    const results=await r.json()||[];
    renderNodeList(results);
    nodeSel&&nodeSel.select('circle').attr('fill-opacity',d=>results.some(r=>r.id===d.id)?0.9:0.12);
  }catch(e){console.error(e)}
});

function toast(msg){
  const el=document.getElementById('toast');el.textContent=msg;el.classList.add('show');
  setTimeout(()=>el.classList.remove('show'),2500);
}
</script>
</body>
</html>`
```

---

## Part 6: Modifications to Existing Files

### 6a. `internal/memory/memory.go` — MODIFY

**Remove the following entirely:**
- `CompileSystemPrompt()` method (replaced by `ContextBuilder.BuildPrompt()`)
- The hardcoded `order := []string{"AGENTS.md", "SOUL.md", ...}` list
- The silent `if err != nil { continue }` error handling

**Add the following to the `Persona` struct:**

```go
type Persona struct {
    deviceID     string
    basePath     string
    defaultsPath string
    mu           sync.RWMutex

    // NEW: graph-based memory
    graph          *KnowledgeGraph
    store          *GraphStore
    contextBuilder *ContextBuilder
}

func NewPersona(deviceID, basePath, defaultsPath, dbPath string) (*Persona, error) {
    // ... existing directory setup ...

    graph := NewKnowledgeGraph()

    store, err := NewGraphStore(dbPath)
    if err != nil {
        return nil, fmt.Errorf("graph store: %w", err)
    }

    // Load persisted nodes into graph
    if err := store.LoadAll(graph); err != nil {
        log.Printf("WARNING: could not load graph nodes: %v", err)
    }

    p := &Persona{
        deviceID:       deviceID,
        basePath:       filepath.Join(basePath, deviceID),
        defaultsPath:   defaultsPath,
        graph:          graph,
        store:          store,
        contextBuilder: NewContextBuilder(graph, store),
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
        {"IDENTITY.md", "identity", "Identity",     NodeTypeIdentity},
        {"SOUL.md",     "soul",     "Soul",         NodeTypeIdentity},
        {"AGENTS.md",   "agents",   "Agent Rules",  NodeTypeConcept},
        {"USER.md",     "user",     "User Profile", NodeTypePerson},
        {"TOOLS.md",    "tools",    "Tools",        NodeTypeConcept},
        {"MEMORY.md",   "memory_notes", "Memory",  NodeTypeMemory},
        {"HEARTBEAT.md","heartbeat","Heartbeat",    NodeTypeConcept},
    }

    for _, s := range seed {
        path := filepath.Join(p.defaultsPath, s.file)
        data, err := os.ReadFile(path)
        if err != nil {
            log.Printf("WARNING: seed file %s not found: %v", s.file, err)
            continue
        }
        node := p.graph.Upsert(s.id, s.title, string(data), s.nodeType, nil)
        if err := p.store.Save(node); err != nil {
            log.Printf("WARNING: could not save seeded node %s: %v", s.id, err)
        }
    }
    log.Printf("[PERSONA] seeded %d nodes from markdown defaults", len(seed))
}

// Graph exposes the knowledge graph (used by API server).
func (p *Persona) Graph() *KnowledgeGraph { return p.graph }

// Store exposes the graph store (used by API server).
func (p *Persona) Store() *GraphStore { return p.store }

// CompileSystemPrompt replaces the old flat-file version.
// Pass userMessage to get relevant context; pass "" for the general cached prompt.
func (p *Persona) CompileSystemPrompt(userMessage string) string {
    return p.contextBuilder.BuildPrompt(userMessage, 6000)
}
```

**Update all callers of `CompileSystemPrompt()`** in `internal/agent/agent.go`:

```go
// OLD:
SystemPrompt: a.persona.CompileSystemPrompt(),

// NEW:
SystemPrompt: a.persona.CompileSystemPrompt(userMsg),
```

---

### 6b. `internal/agent/agent.go` — MODIFY

Add the graph server launcher. Place alongside other methods:

```go
import "github.com/Alartist40/cynapse/internal/api"

var graphAPIServer *api.Server

// StartGraphServer starts the knowledge graph web UI server.
// Safe to call multiple times — reuses the existing server.
func (a *Agent) StartGraphServer(ctx context.Context) (string, error) {
    if graphAPIServer != nil {
        return graphAPIServer.URL(), nil
    }
    graphAPIServer = api.NewServer(a.persona.Graph(), a.persona.Store())
    return graphAPIServer.Start(ctx)
}
```

---

### 6c. `internal/tui/tui.go` — MODIFY

**Add to imports:**
```go
import (
    "os/exec"
    "runtime"
    // ... existing imports
)
```

**Add to the `Model` struct:**
```go
type Model struct {
    // ... existing fields ...
    graphServerURL string
    graphStarting  bool
}
```

**Add message type (alongside other *Msg types):**
```go
type graphServerMsg struct {
    url string
    err error
}
```

**Add to the `Update()` switch (handle the message):**
```go
case graphServerMsg:
    m.graphStarting = false
    if msg.err != nil {
        m.addSystemMsg("✗ Memory graph failed: " + msg.err.Error())
        return m, nil
    }
    m.graphServerURL = msg.url
    m.addSystemMsg("◆ Memory graph → " + msg.url)
    openBrowser(msg.url)
    return m, nil
```

**Replace `cmdMemory` entirely:**
```go
func cmdMemory(m *Model) tea.Cmd {
    m.showMenu = false
    m.input = ""

    if m.graphServerURL != "" {
        m.addSystemMsg("◆ Memory graph → " + m.graphServerURL)
        openBrowser(m.graphServerURL)
        return nil
    }

    if m.graphStarting {
        m.addSystemMsg("● Memory graph is already starting...")
        return nil
    }

    m.graphStarting = true
    m.addSystemMsg("● Starting memory graph server...")

    return func() tea.Msg {
        url, err := m.agent.StartGraphServer(context.Background())
        return graphServerMsg{url: url, err: err}
    }
}
```

**Add browser opener (bottom of file):**
```go
func openBrowser(url string) {
    var cmd *exec.Cmd
    switch runtime.GOOS {
    case "linux":
        cmd = exec.Command("xdg-open", url)
    case "darwin":
        cmd = exec.Command("open", url)
    case "windows":
        cmd = exec.Command("rundll32", "url.dll,FileProtocolHandler", url)
    default:
        return
    }
    cmd.Start() //nolint:errcheck
}
```

**Update the status bar in `View()` to show the URL permanently once active:**
```go
statusLeft := fmt.Sprintf("Model: %s", m.cfg.LLM.Model)
if m.graphServerURL != "" {
    statusLeft += "  ◆ " + m.graphServerURL
}
```

---

## Part 7: Persona Default Files — Convert to Graph Format

The existing `.md` files in `persona/defaults/` are still used as **seed data** on first boot. They should be updated to use **wiki-link syntax** so the graph picks up relationships automatically.

**Example: `persona/defaults/IDENTITY.md`**

```markdown
# Identity

I am CYNAPSE, a modular AI agent running in the terminal.

I was created by [[user]] and my purpose is to assist with tasks, remember context,
and connect to external tools via the [[agents]] plugin system.

My personality is defined in [[soul]].
My available tools are described in [[tools]].
My long-term memory is maintained in [[memory_notes]].

#identity #core
```

**Example: `persona/defaults/USER.md`**

```markdown
# User Profile

The person I work with is my operator. I should refer to information
in [[memory_notes]] to recall facts about them over time.

If I learn new facts about the user — their name, preferences, work context —
I should update this node using the memory tools.

#user #person
```

**Each wiki-link `[[id]]` creates an edge in the graph.** Team members converting these files should follow the same pattern — use `[[id]]` not `[[Title]]`, keep IDs lowercase with underscores.

---

## Part 8: No New Dependencies Required

The implementation uses only what CYNAPSE already has:

| Dependency | Already In `go.mod` | Used For |
|------------|---------------------|----------|
| `github.com/mattn/go-sqlite3` | ✅ YES | GraphStore |
| `net/http` | ✅ stdlib | API server |
| `encoding/json` | ✅ stdlib | API responses |
| `sync` | ✅ stdlib | Thread safety |
| `regexp` | ✅ stdlib | Wiki-link parsing |
| D3.js v7 | CDN (no install) | Graph visualisation |

**Zero new `go get` commands needed.**

---

## Part 9: Testing the Integration

After implementation, verify in this order:

**Step 1 — Build compiles:**
```bash
go build ./cmd/cynapse
```

**Step 2 — First boot seeds graph:**
```bash
./cynapse
# Check logs for: [PERSONA] seeded 7 nodes from markdown defaults
```

**Step 3 — Memory command works:**
```
CYNAPSE > /memory
● Starting memory graph server...
◆ Memory graph → http://localhost:XXXXX
```

**Step 4 — Browser opens and shows graph:**
- Nodes visible (at least 7 from seed)
- Click Identity node → see content, links
- Click Soul node → see link back to Identity (if wiki-links were added)

**Step 5 — Edit a node in browser:**
- Change content of "User Profile" node
- Return to CYNAPSE terminal
- Send a message mentioning the user
- Verify updated content appears in agent context (check via `/status` or logs)

**Step 6 — Persistence survives restart:**
```bash
# Kill and restart CYNAPSE
./cynapse
# Check logs: should NOT say "seeded" — should load from DB
```

---

## Summary for the Team

| What | Action |
|------|--------|
| `internal/memory/graph.go` | **CREATE** — in-memory graph |
| `internal/memory/graph_store.go` | **CREATE** — SQLite persistence |
| `internal/memory/context.go` | **CREATE** — smart context assembly |
| `internal/api/server.go` | **CREATE** — REST API (new package) |
| `internal/api/web_ui.go` | **CREATE** — embedded graph UI |
| `internal/memory/memory.go` | **MODIFY** — wire in graph, replace `CompileSystemPrompt` |
| `internal/agent/agent.go` | **MODIFY** — add `StartGraphServer()` |
| `internal/tui/tui.go` | **MODIFY** — replace `cmdMemory`, add URL field |
| `persona/defaults/*.md` | **UPDATE** — add `[[wiki-links]]` and `#tags` |
| Old `SOUL.md`, `IDENTITY.md` etc. | **DEPRECATED** — become initial graph nodes, not standalone files |
| CYNAPSE Mini | **UNTOUCHED** — keeps flat `.md` system |

**No new Go dependencies. No Python. No Rust. No build tools beyond what you already have.**

---

*End of engineering brief. Questions go to the engineering lead. Ship it.*
