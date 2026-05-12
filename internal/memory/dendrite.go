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

// Dendrite is the in-memory graph. All operations are thread-safe.
type Dendrite struct {
    nodes       map[string]*Node
    mu          sync.RWMutex
    linkPattern *regexp.Regexp
    tagPattern  *regexp.Regexp
    onChange    []func()
}

func NewDendrite() *Dendrite {
    return &Dendrite{
        nodes:       make(map[string]*Node),
        linkPattern: regexp.MustCompile(`\[\[([^\]|]+)(?:\|[^\]]+)?\]\]`),
        tagPattern:  regexp.MustCompile(`#([A-Za-z0-9_-]+)`),
    }
}

// OnChange registers a callback invoked on every mutation.
// Used by DendriteContext to invalidate the prompt cache.
func (kg *Dendrite) OnChange(fn func()) {
    kg.mu.Lock()
    defer kg.mu.Unlock()
    kg.onChange = append(kg.onChange, fn)
}

func (kg *Dendrite) notify() {
    for _, fn := range kg.onChange {
        go fn()
    }
}

// Upsert creates or fully replaces a node and re-wires all backlinks.
func (kg *Dendrite) Upsert(id, title, content string, nodeType NodeType, tags []string) *Node {
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

    // NEW: Search all other nodes to see if they link to this new node
    for _, other := range kg.nodes {
        if other.ID == id {
            continue
        }
        if containsStr(other.Links, id) {
            if !containsStr(node.Backlinks, other.ID) {
                node.Backlinks = append(node.Backlinks, other.ID)
            }
        }
    }

    kg.notify()
    return node
}

// Delete removes a node and cleans up all references in the graph.
func (kg *Dendrite) Delete(id string) bool {
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
func (kg *Dendrite) Get(id string) (*Node, bool) {
    kg.mu.RLock()
    defer kg.mu.RUnlock()
    n, ok := kg.nodes[id]
    return n, ok
}

// All returns every node sorted by UpdatedAt descending.
func (kg *Dendrite) All() []*Node {
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
func (kg *Dendrite) Neighbors(id string) []*Node {
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
func (kg *Dendrite) Search(query string) []*Node {
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
func (kg *Dendrite) ByTag(tag string) []*Node {
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
func (kg *Dendrite) Len() int {
    kg.mu.RLock()
    defer kg.mu.RUnlock()
    return len(kg.nodes)
}

// ── Internal parsing helpers ──────────────────────────────────────────────────

func (kg *Dendrite) parseLinks(content string) []string {
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

func (kg *Dendrite) parseTags(content string) []string {
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
