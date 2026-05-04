package memory

import (
	"context"
	"database/sql"
	"fmt"
	"log"
	"os"
	"path/filepath"
	"strings"
	"sync"
	"time"

	_ "github.com/mattn/go-sqlite3"
	"github.com/yourusername/cynapse/internal/llm"
)

// ─── Persona Manager ─────────────────────────────────────────────────────────
// Manages the markdown files that define a device's personality and memory.
// The agent itself can call tools to update these files, enabling self-improvement.

type Persona struct {
	deviceID     string
	basePath     string
	defaultsPath string
	mu           sync.RWMutex
}

func NewPersona(deviceID, basePath, defaultsPath string) (*Persona, error) {
	path := filepath.Join(basePath, deviceID)
	if err := os.MkdirAll(path, 0755); err != nil {
		return nil, err
	}
	os.MkdirAll(filepath.Join(path, "logs", "daily"), 0755)
	os.MkdirAll(filepath.Join(path, "logs", "heartbeat"), 0755)
	os.MkdirAll(filepath.Join(path, "skills"), 0755)

	p := &Persona{deviceID: deviceID, basePath: path, defaultsPath: defaultsPath}
	p.initDefaults()
	return p, nil
}

// initDefaults copies default markdown files if they don't exist yet.
func (p *Persona) initDefaults() {
	files := []string{"AGENTS.md", "SOUL.md", "IDENTITY.md", "USER.md", "TOOLS.md", "MEMORY.md", "HEARTBEAT.md"}
	for _, f := range files {
		dest := filepath.Join(p.basePath, f)
		if _, err := os.Stat(dest); os.IsNotExist(err) {
			src := filepath.Join(p.defaultsPath, f)
			data, err := os.ReadFile(src)
			if err != nil {
				// Fallback: write a placeholder
				data = []byte(fmt.Sprintf("# %s\n\n_No content yet. The agent will update this file over time._\n", strings.TrimSuffix(f, ".md")))
			}
			os.WriteFile(dest, data, 0644)
		}
	}
}

// CompileSystemPrompt assembles all markdown files into a single system prompt.
func (p *Persona) CompileSystemPrompt() string {
	p.mu.RLock()
	defer p.mu.RUnlock()

	order := []string{"AGENTS.md", "SOUL.md", "IDENTITY.md", "USER.md", "TOOLS.md", "MEMORY.md"}
	var parts []string

	for _, f := range order {
		content, err := os.ReadFile(filepath.Join(p.basePath, f))
		if err != nil {
			continue
		}
		if strings.TrimSpace(string(content)) != "" {
			parts = append(parts, string(content))
		}
	}

	return strings.Join(parts, "\n\n---\n\n")
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

// WriteFile writes to any file in the persona directory (called by tool handlers).
func (p *Persona) WriteFile(name, content string) error {
	p.mu.Lock()
	defer p.mu.Unlock()
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

// ─── SQLite Memory Store ──────────────────────────────────────────────────────

type Store struct {
	db *sql.DB
}

func NewStore(dbPath string) (*Store, error) {
	os.MkdirAll(filepath.Dir(dbPath), 0755)
	db, err := sql.Open("sqlite3", dbPath+"?_journal_mode=WAL")
	if err != nil {
		return nil, err
	}

	schema := `
	CREATE TABLE IF NOT EXISTS memories (
		id        INTEGER PRIMARY KEY AUTOINCREMENT,
		device_id TEXT    NOT NULL,
		fact      TEXT    NOT NULL,
		context   TEXT    DEFAULT '',
		tags      TEXT    DEFAULT '',
		ts        INTEGER NOT NULL
	);
	CREATE INDEX IF NOT EXISTS idx_device_ts ON memories(device_id, ts DESC);
	CREATE INDEX IF NOT EXISTS idx_device_fact ON memories(device_id, fact);`

	if _, err := db.Exec(schema); err != nil {
		return nil, err
	}
	return &Store{db: db}, nil
}

type MemoryEntry struct {
	ID       int64
	DeviceID string
	Fact     string
	Context  string
	Tags     string
	Time     time.Time
}

func (s *Store) Save(deviceID, fact, context, tags string) error {
	_, err := s.db.Exec(
		`INSERT INTO memories(device_id,fact,context,tags,ts) VALUES(?,?,?,?,?)`,
		deviceID, fact, context, tags, time.Now().Unix(),
	)
	return err
}

func (s *Store) Search(deviceID, query string, limit int) ([]MemoryEntry, error) {
	rows, err := s.db.Query(`
		SELECT id,device_id,fact,context,tags,ts FROM memories
		WHERE device_id=? AND (fact LIKE ? OR context LIKE ? OR tags LIKE ?)
		ORDER BY ts DESC LIMIT ?`,
		deviceID, "%"+query+"%", "%"+query+"%", "%"+query+"%", limit)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	return scanMemories(rows)
}

func (s *Store) Recent(deviceID string, limit int) ([]MemoryEntry, error) {
	rows, err := s.db.Query(`
		SELECT id,device_id,fact,context,tags,ts FROM memories
		WHERE device_id=? ORDER BY ts DESC LIMIT ?`,
		deviceID, limit)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	return scanMemories(rows)
}

func scanMemories(rows *sql.Rows) ([]MemoryEntry, error) {
	var result []MemoryEntry
	for rows.Next() {
		var m MemoryEntry
		var ts int64
		if err := rows.Scan(&m.ID, &m.DeviceID, &m.Fact, &m.Context, &m.Tags, &ts); err != nil {
			return nil, err
		}
		m.Time = time.Unix(ts, 0)
		result = append(result, m)
	}
	return result, rows.Err()
}

func (s *Store) Close() error { return s.db.Close() }

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
