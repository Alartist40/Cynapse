package session

import (
	"bufio"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"sync"
	"time"

	"github.com/yourusername/cynapse/internal/llm"
)

// ─── Message ─────────────────────────────────────────────────────────────────

type Entry struct {
	Role      llm.Role   `json:"role"`
	Content   string     `json:"content"`
	ToolCalls []llm.ToolCall `json:"tool_calls,omitempty"`
	Timestamp int64      `json:"ts"`
}

// ─── Session ─────────────────────────────────────────────────────────────────

type Session struct {
	Key      string
	entries  []Entry
	filePath string
	mu       sync.Mutex
}

func load(path string) (*Session, error) {
	s := &Session{filePath: path}

	f, err := os.Open(path)
	if os.IsNotExist(err) {
		return s, nil
	}
	if err != nil {
		return nil, err
	}
	defer f.Close()

	sc := bufio.NewScanner(f)
	for sc.Scan() {
		var e Entry
		if err := json.Unmarshal(sc.Bytes(), &e); err == nil {
			s.entries = append(s.entries, e)
		}
	}
	return s, sc.Err()
}

func (s *Session) Append(e Entry) error {
	s.mu.Lock()
	defer s.mu.Unlock()

	e.Timestamp = time.Now().Unix()
	s.entries = append(s.entries, e)

	f, err := os.OpenFile(s.filePath, os.O_APPEND|os.O_CREATE|os.O_WRONLY, 0644)
	if err != nil {
		return err
	}
	defer f.Close()

	data, err := json.Marshal(e)
	if err != nil {
		return err
	}
	_, err = f.Write(append(data, '\n'))
	return err
}

// Recent returns the last n messages as LLM messages (for context window)
func (s *Session) Recent(n int) []llm.Message {
	s.mu.Lock()
	defer s.mu.Unlock()

	start := len(s.entries) - n
	if start < 0 {
		start = 0
	}

	result := make([]llm.Message, 0, n)
	for _, e := range s.entries[start:] {
		result = append(result, llm.Message{
			Role:      e.Role,
			Content:   e.Content,
			ToolCalls: e.ToolCalls,
		})
	}
	return result
}

func (s *Session) Len() int {
	s.mu.Lock()
	defer s.mu.Unlock()
	return len(s.entries)
}

// Compact rewrites the file keeping only the last n entries
func (s *Session) Compact(keep int) error {
	s.mu.Lock()
	defer s.mu.Unlock()

	if len(s.entries) <= keep {
		return nil
	}
	s.entries = s.entries[len(s.entries)-keep:]

	f, err := os.Create(s.filePath)
	if err != nil {
		return err
	}
	defer f.Close()

	for _, e := range s.entries {
		data, _ := json.Marshal(e)
		f.Write(append(data, '\n'))
	}
	return nil
}

// ─── Manager ─────────────────────────────────────────────────────────────────

type Manager struct {
	basePath string
	sessions map[string]*Session
	mu       sync.RWMutex
}

func NewManager(basePath string) *Manager {
	os.MkdirAll(basePath, 0755)
	return &Manager{basePath: basePath, sessions: make(map[string]*Session)}
}

func (m *Manager) Get(key string) (*Session, error) {
	m.mu.RLock()
	if s, ok := m.sessions[key]; ok {
		m.mu.RUnlock()
		return s, nil
	}
	m.mu.RUnlock()

	m.mu.Lock()
	defer m.mu.Unlock()

	// Double-check
	if s, ok := m.sessions[key]; ok {
		return s, nil
	}

	path := filepath.Join(m.basePath, fmt.Sprintf("%s.jsonl", sanitizeKey(key)))
	s, err := load(path)
	if err != nil {
		return nil, err
	}
	s.Key = key
	m.sessions[key] = s
	return s, nil
}

func sanitizeKey(k string) string {
	out := make([]byte, 0, len(k))
	for _, c := range []byte(k) {
		if (c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') ||
			(c >= '0' && c <= '9') || c == '-' || c == '_' {
			out = append(out, c)
		} else {
			out = append(out, '_')
		}
	}
	return string(out)
}
