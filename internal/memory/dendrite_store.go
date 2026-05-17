package memory

import (
    "database/sql"
    "encoding/json"
    "fmt"

    _ "github.com/mattn/go-sqlite3"
)

// DendriteStore persists Dendrite nodes to SQLite.
type DendriteStore struct {
    db      *sql.DB
    hasFTS5 bool
}

func NewDendriteStore(dbPath string) (*DendriteStore, error) {
    db, err := sql.Open("sqlite3", dbPath+"?_journal=WAL&_busy_timeout=5000")
    if err != nil {
        return nil, fmt.Errorf("open graph db: %w", err)
    }
    db.SetMaxOpenConns(1) // SQLite is single-writer

    gs := &DendriteStore{db: db}
    if err := gs.migrate(); err != nil {
        return nil, fmt.Errorf("graph db migrate: %w", err)
    }
    return gs, nil
}

func (gs *DendriteStore) migrate() error {
    // Core table always created
    if _, err := gs.db.Exec(`
    CREATE TABLE IF NOT EXISTS dendrite_nodes (
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

    CREATE INDEX IF NOT EXISTS idx_dendrite_updated ON dendrite_nodes(updated_at DESC);
    `); err != nil {
        return err
    }

    // Try FTS5; if unavailable, gracefully fall back
    if _, err := gs.db.Exec(`
    CREATE VIRTUAL TABLE IF NOT EXISTS dendrite_fts USING fts5(
        id         UNINDEXED,
        title,
        content,
        tags,
        tokenize = 'porter unicode61'
    );
    `); err != nil {
        // FTS5 not available — create fallback text index table
        gs.hasFTS5 = false
        _, _ = gs.db.Exec(`
        CREATE TABLE IF NOT EXISTS dendrite_fts_fallback (
            id    TEXT PRIMARY KEY,
            title TEXT,
            content TEXT,
            tags  TEXT
        );
        `)
        return nil
    }

    gs.hasFTS5 = true

    // Sync triggers only if FTS5 exists
    _, err := gs.db.Exec(`
    CREATE TRIGGER IF NOT EXISTS dendrite_nodes_ai
    AFTER INSERT ON dendrite_nodes BEGIN
        INSERT INTO dendrite_fts(id, title, content, tags)
        VALUES (new.id, new.title, new.content, new.tags);
    END;

    CREATE TRIGGER IF NOT EXISTS dendrite_nodes_au
    AFTER UPDATE ON dendrite_nodes BEGIN
        DELETE FROM dendrite_fts WHERE id = old.id;
        INSERT INTO dendrite_fts(id, title, content, tags)
        VALUES (new.id, new.title, new.content, new.tags);
    END;

    CREATE TRIGGER IF NOT EXISTS dendrite_nodes_ad
    AFTER DELETE ON dendrite_nodes BEGIN
        DELETE FROM dendrite_fts WHERE id = old.id;
    END;
    `)
    return err
}

// Save upserts a node into SQLite.
func (gs *DendriteStore) Save(n *Node) error {
    tags, _ := json.Marshal(n.Tags)
    links, _ := json.Marshal(n.Links)
    backlinks, _ := json.Marshal(n.Backlinks)

    tx, err := gs.db.Begin()
    if err != nil {
        return err
    }
    defer tx.Rollback()

    _, err = tx.Exec(`
        INSERT INTO dendrite_nodes
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
    if err != nil {
        return err
    }

    // Fallback FTS sync when FTS5 is unavailable
    if !gs.hasFTS5 {
        _, err = tx.Exec(`
            INSERT INTO dendrite_fts_fallback (id, title, content, tags)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                title = excluded.title,
                content = excluded.content,
                tags = excluded.tags
        `, n.ID, n.Title, n.Content, string(tags))
        if err != nil {
            return err
        }
    }

    return tx.Commit()
}

// Delete removes a node from SQLite.
func (gs *DendriteStore) Delete(id string) error {
    tx, err := gs.db.Begin()
    if err != nil {
        return err
    }
    defer tx.Rollback()

    _, err = tx.Exec(`DELETE FROM dendrite_nodes WHERE id = ?`, id)
    if err != nil {
        return err
    }

    if !gs.hasFTS5 {
        _, err = tx.Exec(`DELETE FROM dendrite_fts_fallback WHERE id = ?`, id)
        if err != nil {
            return err
        }
    }

    return tx.Commit()
}

// LoadAll hydrates all stored nodes directly into the graph's node map.
// Call this once at startup before serving any requests.
func (gs *DendriteStore) LoadAll(kg *Dendrite) error {
    rows, err := gs.db.Query(`
        SELECT id, title, content, type, tags, links, backlinks, created_at, updated_at
        FROM dendrite_nodes
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
func (gs *DendriteStore) FTSSearch(query string, limit int) ([]string, error) {
    if limit <= 0 {
        limit = 10
    }

    if gs.hasFTS5 {
        rows, err := gs.db.Query(`
            SELECT id FROM dendrite_fts
            WHERE dendrite_fts MATCH ?
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

    // Fallback: LIKE-based search across title/content/tags
    pattern := "%" + query + "%"
    rows, err := gs.db.Query(`
        SELECT id FROM dendrite_fts_fallback
        WHERE title LIKE ? OR content LIKE ? OR tags LIKE ?
        LIMIT ?
    `, pattern, pattern, pattern, limit)
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

func (gs *DendriteStore) Close() error {
    return gs.db.Close()
}
