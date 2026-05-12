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

// Server exposes the DENDRITE memory graph over a local HTTP API
// and serves the embedded graph visualisation UI.
type Server struct {
    graph  *memory.Dendrite
    store  *memory.DendriteStore
    server *http.Server
    url    string
}

func NewServer(graph *memory.Dendrite, store *memory.DendriteStore) *Server {
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
    mux.HandleFunc("/api/dendrite",      s.withCORS(s.handleGraph))
    mux.HandleFunc("/api/nodes",      s.withCORS(s.handleNodes))
    mux.HandleFunc("/api/nodes/",     s.withCORS(s.handleNode))
    mux.HandleFunc("/api/search",     s.withCORS(s.handleSearch))
    mux.HandleFunc("/api/neighbors/", s.withCORS(s.handleNeighbors))
    mux.HandleFunc("/d3.min.js",      s.handleD3)
    mux.HandleFunc("/",               s.handleUI)

    s.server = &http.Server{
        Handler:      mux,
        ReadTimeout:  10 * time.Second,
        WriteTimeout: 10 * time.Second,
    }

    go func() {
        if err := s.server.Serve(listener); err != nil && err != http.ErrServerClosed {
            log.Printf("[DENDRITE API] error: %v", err)
        }
    }()

    go func() {
        <-ctx.Done()
        shutCtx, cancel := context.WithTimeout(context.Background(), 3*time.Second)
        defer cancel()
        s.server.Shutdown(shutCtx) //nolint:errcheck
    }()

    log.Printf("[DENDRITE API] serving at %s", s.url)
    return s.url, nil
}

// ── Handlers ──────────────────────────────────────────────────────────────────

// GET /api/dendrite — returns {nodes, links} shaped for D3 force layout.
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
            log.Printf("[DENDRITE API] save: %v", err)
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

// GET /d3.min.js — serves the embedded D3.js library for offline support.
func (s *Server) handleD3(w http.ResponseWriter, r *http.Request) {
    w.Header().Set("Content-Type", "application/javascript")
    w.Write([]byte(d3JS)) //nolint:errcheck
}

// ── Helpers ───────────────────────────────────────────────────────────────────

func (s *Server) jsonResponse(w http.ResponseWriter, v any) {
    w.Header().Set("Content-Type", "application/json")
    if err := json.NewEncoder(w).Encode(v); err != nil {
        log.Printf("[DENDRITE API] encode: %v", err)
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
