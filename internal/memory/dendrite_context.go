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

// DendriteContext assembles the LLM system prompt from graph nodes.
type DendriteContext struct {
    graph *Dendrite
    store *DendriteStore

    mu           sync.Mutex
    cachedPrompt string
    cachedAt     time.Time
    cacheTTL     time.Duration
    dirty        bool
}

func NewDendriteContext(graph *Dendrite, store *DendriteStore) *DendriteContext {
    cb := &DendriteContext{
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
func (cb *DendriteContext) BuildPrompt(userMessage string, maxTokens int) string {
    cb.mu.Lock()
    defer cb.mu.Unlock()

    if maxTokens <= 0 {
        maxTokens = defaultMaxTokens
    }

    // Message-specific context skips the cache
    if strings.TrimSpace(userMessage) != "" {
        return cb.assemble(userMessage, maxTokens)
    }

    if !cb.dirty && time.Since(cb.cachedAt) < cb.cacheTTL && cb.cachedPrompt != "" {
        return cb.cachedPrompt
    }

    prompt := cb.assemble("", maxTokens)
    cb.cachedPrompt = prompt
    cb.cachedAt = time.Now()
    cb.dirty = false
    return prompt
}

func (cb *DendriteContext) assemble(userMessage string, maxTokens int) string {
    var parts []string
    used := 0

    coreBudget := int(float64(maxTokens) * coreNodeBudget)

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
            if used+cost > maxTokens {
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

func (cb *DendriteContext) findRelevant(userMessage string) []*Node {
    seen := map[string]bool{}
    var out []*Node

    addNode := func(n *Node) {
        if n != nil && !seen[n.ID] {
            seen[n.ID] = true
            out = append(out, n)
        }
    }

    // 1. Try FTS5 first (most precise, if available)
    if cb.store != nil {
        ids, err := cb.store.FTSSearch(userMessage, 20)
        if err == nil {
            for _, id := range ids {
                if n, ok := cb.graph.Get(id); ok {
                    addNode(n)
                    for _, neighbor := range cb.graph.Neighbors(n.ID) {
                        addNode(neighbor)
                    }
                }
            }
        }
    }

    // 2. Full-query substring search (fallback / complement)
    for _, n := range cb.graph.Search(userMessage) {
        addNode(n)
        for _, neighbor := range cb.graph.Neighbors(n.ID) {
            addNode(neighbor)
        }
    }

    // 3. Word-by-word search in titles, content, and tags
    words := strings.Fields(strings.ToLower(userMessage))
    for _, word := range words {
        if len(word) < 3 {
            continue
        }
        if isStopWord(word) {
            continue
        }
        for _, n := range cb.graph.Search(word) {
            addNode(n)
            for _, neighbor := range cb.graph.Neighbors(n.ID) {
                addNode(neighbor)
            }
        }
        for _, n := range cb.graph.ByTag(word) {
            addNode(n)
        }
    }

    return out
}

var stopWords = map[string]bool{
    "the": true, "and": true, "for": true, "are": true, "but": true,
    "not": true, "you": true, "all": true, "can": true, "had": true,
    "her": true, "was": true, "one": true, "our": true, "out": true,
    "day": true, "get": true, "has": true, "him": true, "his": true,
    "how": true, "its": true, "may": true, "new": true, "now": true,
    "old": true, "see": true, "two": true, "who": true, "boy": true,
    "did": true, "she": true, "use": true, "way": true,
    "many": true, "oil": true, "sit": true, "set": true, "run": true,
    "eat": true, "far": true, "sea": true, "eye": true, "ago": true,
    "off": true, "too": true, "any": true, "say": true, "man": true,
    "try": true, "ask": true, "end": true, "why": true, "let": true,
    "put": true, "own": true, "tell": true,
    "when": true, "come": true, "here": true, "just": true,
    "like": true, "long": true, "make": true, "over": true, "such": true,
    "take": true, "than": true, "them": true, "well": true, "were": true,
    "what": true, "will": true, "with": true, "have": true, "from": true,
    "they": true, "know": true, "want": true, "been": true, "good": true,
    "much": true, "some": true, "time": true, "would": true,
    "there": true, "their": true, "could": true, "other": true, "after": true,
    "first": true, "never": true, "these": true, "think": true, "where": true,
    "being": true, "every": true, "great": true, "might": true, "shall": true,
    "still": true, "those": true, "while": true, "about": true, "should": true,
}

func isStopWord(w string) bool {
    return stopWords[w]
}

type scoredNode struct {
    node  *Node
    score float64
}

func (cb *DendriteContext) score(nodes []*Node, query string) []scoredNode {
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
