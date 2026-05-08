package tools

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"time"

	"github.com/Alartist40/cynapse/internal/llm"
)

// ─── Tool definition ─────────────────────────────────────────────────────────

type Tool struct {
	Schema  llm.ToolSchema
	Handler func(ctx context.Context, args map[string]any) (string, error)
}

// ─── Registry ─────────────────────────────────────────────────────────────────

type Registry struct {
	tools   map[string]*Tool
	workDir string
	timeout time.Duration
}

func NewRegistry(workDir string, timeoutSec int) *Registry {
	if workDir == "" {
		workDir = "./workspace"
	}
	if timeoutSec <= 0 {
		timeoutSec = 30
	}
	os.MkdirAll(workDir, 0755)
	r := &Registry{
		tools:   make(map[string]*Tool),
		workDir: workDir,
		timeout: time.Duration(timeoutSec) * time.Second,
	}
	return r
}

func (r *Registry) Register(t *Tool) {
	r.tools[t.Schema.Name] = t
}

func (r *Registry) Schemas() []llm.ToolSchema {
	schemas := make([]llm.ToolSchema, 0, len(r.tools))
	for _, t := range r.tools {
		schemas = append(schemas, t.Schema)
	}
	return schemas
}

func (r *Registry) Execute(ctx context.Context, name string, rawArgs json.RawMessage) (string, error) {
	t, ok := r.tools[name]
	if !ok {
		return "", fmt.Errorf("unknown tool: %s", name)
	}

	var args map[string]any
	if err := json.Unmarshal(rawArgs, &args); err != nil {
		return "", fmt.Errorf("parsing args: %w", err)
	}

	ctx, cancel := context.WithTimeout(ctx, r.timeout)
	defer cancel()

	return t.Handler(ctx, args)
}

// ─── Tool constructors ────────────────────────────────────────────────────────

// BashTool executes shell commands in the workspace directory.
func BashTool(workDir string) *Tool {
	return &Tool{
		Schema: llm.ToolSchema{
			Name:        "bash",
			Description: "Execute a bash command in the workspace directory. Returns stdout+stderr.",
			Parameters: map[string]any{
				"type": "object",
				"properties": map[string]any{
					"command": map[string]any{
						"type":        "string",
						"description": "The bash command to execute",
					},
				},
				"required": []string{"command"},
			},
		},
		Handler: func(ctx context.Context, args map[string]any) (string, error) {
			cmd, _ := args["command"].(string)
			if cmd == "" {
				return "", fmt.Errorf("command is required")
			}

			c := exec.CommandContext(ctx, "bash", "-c", cmd)
			c.Dir = workDir
			out, err := c.CombinedOutput()
			result := string(out)

			if err != nil {
				return fmt.Sprintf("exit error: %v\n%s", err, result), nil
			}
			if result == "" {
				return "(no output)", nil
			}
			return result, nil
		},
	}
}

// ReadFileTool reads a file from the workspace.
func ReadFileTool(workDir string) *Tool {
	return &Tool{
		Schema: llm.ToolSchema{
			Name:        "read_file",
			Description: "Read the contents of a file. Path is relative to the workspace.",
			Parameters: map[string]any{
				"type": "object",
				"properties": map[string]any{
					"path": map[string]any{"type": "string", "description": "File path to read"},
				},
				"required": []string{"path"},
			},
		},
		Handler: func(ctx context.Context, args map[string]any) (string, error) {
			path, _ := args["path"].(string)
			full, err := resolvePath(workDir, path)
			if err != nil {
				return "", err
			}
			data, err := os.ReadFile(full)
			if err != nil {
				return "", fmt.Errorf("reading file: %w", err)
			}
			return string(data), nil
		},
	}
}

// WriteFileTool writes content to a file in the workspace.
func WriteFileTool(workDir string) *Tool {
	return &Tool{
		Schema: llm.ToolSchema{
			Name:        "write_file",
			Description: "Write content to a file. Path is relative to the workspace. Creates parent directories automatically.",
			Parameters: map[string]any{
				"type": "object",
				"properties": map[string]any{
					"path":    map[string]any{"type": "string", "description": "File path to write"},
					"content": map[string]any{"type": "string", "description": "Content to write"},
				},
				"required": []string{"path", "content"},
			},
		},
		Handler: func(ctx context.Context, args map[string]any) (string, error) {
			path, _ := args["path"].(string)
			content, _ := args["content"].(string)
			full, err := resolvePath(workDir, path)
			if err != nil {
				return "", err
			}
			os.MkdirAll(filepath.Dir(full), 0755)
			if err := os.WriteFile(full, []byte(content), 0644); err != nil {
				return "", err
			}
			return fmt.Sprintf("Written %d bytes to %s", len(content), path), nil
		},
	}
}

// ListFilesTool lists files in a workspace directory.
func ListFilesTool(workDir string) *Tool {
	return &Tool{
		Schema: llm.ToolSchema{
			Name:        "list_files",
			Description: "List files in a directory. Path is relative to workspace.",
			Parameters: map[string]any{
				"type": "object",
				"properties": map[string]any{
					"path": map[string]any{"type": "string", "description": "Directory path (default: '.')"},
				},
				"required": []string{},
			},
		},
		Handler: func(ctx context.Context, args map[string]any) (string, error) {
			path, _ := args["path"].(string)
			if path == "" {
				path = "."
			}
			full, err := resolvePath(workDir, path)
			if err != nil {
				return "", err
			}
			entries, err := os.ReadDir(full)
			if err != nil {
				return "", err
			}
			var lines []string
			for _, e := range entries {
				info, _ := e.Info()
				if info == nil {
					continue
				}
				typ := "file"
				if e.IsDir() {
					typ = "dir "
				}
				lines = append(lines, fmt.Sprintf("%s  %6d  %s", typ, info.Size(), e.Name()))
			}
			if len(lines) == 0 {
				return "(empty directory)", nil
			}
			return strings.Join(lines, "\n"), nil
		},
	}
}

// WebFetchTool fetches a URL and returns plain text content.
func WebFetchTool() *Tool {
	client := &http.Client{Timeout: 20 * time.Second}
	return &Tool{
		Schema: llm.ToolSchema{
			Name:        "web_fetch",
			Description: "Fetch a URL and return its text content. Useful for reading documentation or web pages.",
			Parameters: map[string]any{
				"type": "object",
				"properties": map[string]any{
					"url": map[string]any{"type": "string", "description": "URL to fetch"},
				},
				"required": []string{"url"},
			},
		},
		Handler: func(ctx context.Context, args map[string]any) (string, error) {
			url, _ := args["url"].(string)
			if url == "" {
				return "", fmt.Errorf("url is required")
			}

			req, err := http.NewRequestWithContext(ctx, "GET", url, nil)
			if err != nil {
				return "", err
			}
			req.Header.Set("User-Agent", "CYNAPSE-Agent/1.0")

			resp, err := client.Do(req)
			if err != nil {
				return "", err
			}
			defer resp.Body.Close()

			body, err := io.ReadAll(io.LimitReader(resp.Body, 32*1024)) // 32KB limit
			if err != nil {
				return "", err
			}

			return fmt.Sprintf("Status: %d\n\n%s", resp.StatusCode, string(body)), nil
		},
	}
}

// MemoryReplaceTool allows the agent to update MEMORY.md.
// The fn parameter is a callback to the persona manager.
func MemoryReplaceTool(writeFile func(name, content string) error) *Tool {
	return &Tool{
		Schema: llm.ToolSchema{
			Name:        "memory_replace",
			Description: "Replace the contents of MEMORY.md with updated long-term memory. Use this to save important facts you want to remember.",
			Parameters: map[string]any{
				"type": "object",
				"properties": map[string]any{
					"content": map[string]any{"type": "string", "description": "New content for MEMORY.md"},
				},
				"required": []string{"content"},
			},
		},
		Handler: func(ctx context.Context, args map[string]any) (string, error) {
			content, _ := args["content"].(string)
			if err := writeFile("MEMORY.md", content); err != nil {
				return "", err
			}
			return "MEMORY.md updated successfully.", nil
		},
	}
}

// DailyLogAppendTool lets the agent add entries to today's log.
func DailyLogAppendTool(appendLog func(entry string) error) *Tool {
	return &Tool{
		Schema: llm.ToolSchema{
			Name:        "daily_log_append",
			Description: "Append an entry to today's daily interaction log. Use this to record important events, decisions, or observations.",
			Parameters: map[string]any{
				"type": "object",
				"properties": map[string]any{
					"entry": map[string]any{"type": "string", "description": "Log entry to append"},
				},
				"required": []string{"entry"},
			},
		},
		Handler: func(ctx context.Context, args map[string]any) (string, error) {
			entry, _ := args["entry"].(string)
			if err := appendLog(entry); err != nil {
				return "", err
			}
			return "Log entry appended.", nil
		},
	}
}

// SoulReplaceTool lets the agent update its SOUL.md (personality / tone).
func SoulReplaceTool(writeFile func(name, content string) error) *Tool {
	return &Tool{
		Schema: llm.ToolSchema{
			Name:        "soul_replace",
			Description: "Update SOUL.md — the file that defines your personality, tone, and communication style.",
			Parameters: map[string]any{
				"type": "object",
				"properties": map[string]any{
					"content": map[string]any{"type": "string", "description": "New content for SOUL.md"},
				},
				"required": []string{"content"},
			},
		},
		Handler: func(ctx context.Context, args map[string]any) (string, error) {
			content, _ := args["content"].(string)
			if err := writeFile("SOUL.md", content); err != nil {
				return "", err
			}
			return "SOUL.md updated.", nil
		},
	}
}

// UserReplaceTool lets the agent update its USER.md (profile of the human).
func UserReplaceTool(writeFile func(name, content string) error) *Tool {
	return &Tool{
		Schema: llm.ToolSchema{
			Name:        "user_replace",
			Description: "Update USER.md — a profile of the user with their preferences, background, and important facts about them.",
			Parameters: map[string]any{
				"type": "object",
				"properties": map[string]any{
					"content": map[string]any{"type": "string", "description": "New content for USER.md"},
				},
				"required": []string{"content"},
			},
		},
		Handler: func(ctx context.Context, args map[string]any) (string, error) {
			content, _ := args["content"].(string)
			if err := writeFile("USER.md", content); err != nil {
				return "", err
			}
			return "USER.md updated.", nil
		},
	}
}

// MemorySearchTool wraps the SQLite store search.
func MemorySearchTool(search func(query string, limit int) (string, error)) *Tool {
	return &Tool{
		Schema: llm.ToolSchema{
			Name:        "memory_search",
			Description: "Search your long-term memory store using full-text search.",
			Parameters: map[string]any{
				"type": "object",
				"properties": map[string]any{
					"query": map[string]any{"type": "string", "description": "Search query"},
					"limit": map[string]any{"type": "integer", "description": "Max results (default 5)"},
				},
				"required": []string{"query"},
			},
		},
		Handler: func(ctx context.Context, args map[string]any) (string, error) {
			query, _ := args["query"].(string)
			limit := 5
			if v, ok := args["limit"].(float64); ok {
				limit = int(v)
			}
			return search(query, limit)
		},
	}
}

// ─── Profile builder ──────────────────────────────────────────────────────────

// BuildProfile returns a registry populated according to the tool profile setting.
func BuildProfile(profile, workDir string, timeoutSec int,
	writeFile func(name, content string) error,
	appendLog func(entry string) error,
	searchMemory func(query string, limit int) (string, error),
) *Registry {

	r := NewRegistry(workDir, timeoutSec)

	// Always available
	r.Register(MemoryReplaceTool(writeFile))
	r.Register(DailyLogAppendTool(appendLog))
	r.Register(UserReplaceTool(writeFile))
	r.Register(SoulReplaceTool(writeFile))
	r.Register(MemorySearchTool(searchMemory))
	r.Register(ReadFileTool(workDir))

	switch strings.ToLower(profile) {
	case "full":
		r.Register(BashTool(workDir))
		r.Register(WriteFileTool(workDir))
		r.Register(ListFilesTool(workDir))
		r.Register(WebFetchTool())
	case "standard":
		r.Register(WriteFileTool(workDir))
		r.Register(ListFilesTool(workDir))
		r.Register(WebFetchTool())
	case "minimal":
		// Only memory tools (already added above)
	default:
		// Default to standard
		r.Register(WriteFileTool(workDir))
		r.Register(ListFilesTool(workDir))
		r.Register(WebFetchTool())
	}

	return r
}

// ─── Helpers ─────────────────────────────────────────────────────────────────

// resolvePath safely resolves a relative path within the workspace
func resolvePath(workDir, rel string) (string, error) {
	// Get absolute paths
	absWorkDir, err := filepath.Abs(workDir)
	if err != nil {
		return "", fmt.Errorf("getting absolute workspace: %w", err)
	}

	// Join and clean the path
	joined := filepath.Join(workDir, rel)
	absResolved, err := filepath.Abs(joined)
	if err != nil {
		return "", fmt.Errorf("getting absolute path: %w", err)
	}

	// CRITICAL: Verify resolved path is still within workspace
	// This prevents directory traversal attacks like "../../etc/passwd"
	if !strings.HasPrefix(absResolved, absWorkDir+string(filepath.Separator)) && absResolved != absWorkDir {
		return "", fmt.Errorf("path escapes workspace: %s not within %s", absResolved, absWorkDir)
	}

	return absResolved, nil
}
