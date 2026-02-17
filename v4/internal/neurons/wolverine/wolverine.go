// Package wolverine implements RAG-based security audit and log analysis.
package wolverine

import (
	"context"
	"fmt"
	"os"
	"path/filepath"
	"regexp"
	"strings"

	"github.com/Alartist40/cynapse/internal/core"
)

// Finding represents a security audit finding.
type Finding struct {
	Severity string `json:"severity"` // "critical", "high", "medium", "low", "info"
	Category string `json:"category"`
	Message  string `json:"message"`
	File     string `json:"file,omitempty"`
	Line     int    `json:"line,omitempty"`
}

// Neuron implements the Wolverine RAG audit neuron.
type Neuron struct {
	patterns map[string][]*regexp.Regexp
}

func New() *Neuron {
	n := &Neuron{
		patterns: make(map[string][]*regexp.Regexp),
	}
	n.loadPatterns()
	return n
}

func (n *Neuron) ID() string             { return "wolverine" }
func (n *Neuron) Name() string           { return "Wolverine — RAG Security Audit" }
func (n *Neuron) Capabilities() []string { return []string{"audit_file", "audit_dir", "search_secrets", "analyze_logs"} }

func (n *Neuron) Execute(ctx context.Context, task core.Task) (core.Result, error) {
	switch task.Operation {
	case "audit_file":
		path := task.Params["path"]
		findings := n.auditFile(path)
		return n.formatFindings(findings), nil

	case "audit_dir":
		dir := task.Params["dir"]
		findings := n.auditDirectory(ctx, dir)
		return n.formatFindings(findings), nil

	case "search_secrets":
		dir := task.Params["dir"]
		if dir == "" {
			dir = "."
		}
		findings := n.searchSecrets(ctx, dir)
		return n.formatFindings(findings), nil

	case "analyze_logs":
		path := task.Params["path"]
		analysis := n.analyzeLogs(path)
		return core.Result{Success: true, Output: analysis}, nil

	default:
		return core.Result{}, fmt.Errorf("wolverine: unknown operation %s", task.Operation)
	}
}

func (n *Neuron) loadPatterns() {
	n.patterns["secrets"] = compilePatterns([]string{
		`(?i)(?:password|passwd|pwd)\s*[:=]\s*\S+`,
		`(?i)(?:api[_-]?key|apikey)\s*[:=]\s*\S+`,
		`(?i)(?:secret[_-]?key|secret)\s*[:=]\s*\S+`,
		`(?i)(?:access[_-]?token|auth[_-]?token)\s*[:=]\s*\S+`,
		`(?:AKIA|ABIA|ACCA|ASIA)[0-9A-Z]{16}`, // AWS keys
		`ghp_[0-9a-zA-Z]{36}`,                   // GitHub PAT
		`sk-[0-9a-zA-Z]{48}`,                    // OpenAI key
	})

	n.patterns["vulnerabilities"] = compilePatterns([]string{
		`(?i)eval\s*\(`,
		`(?i)exec\s*\(`,
		`(?i)os\.system\s*\(`,
		`(?i)subprocess\.call\s*\(`,
		`(?i)pickle\.loads?\s*\(`,
		`(?i)yaml\.load\s*\(`,       // unsafe YAML load
		`(?i)__import__\s*\(`,
	})
}

func (n *Neuron) auditFile(path string) []Finding {
	data, err := os.ReadFile(path)
	if err != nil {
		return []Finding{{Severity: "info", Category: "error", Message: fmt.Sprintf("Cannot read: %v", err)}}
	}

	var findings []Finding
	lines := strings.Split(string(data), "\n")

	for i, line := range lines {
		for cat, patterns := range n.patterns {
			for _, p := range patterns {
				if p.MatchString(line) {
					sev := "medium"
					if cat == "secrets" {
						sev = "critical"
					}
					findings = append(findings, Finding{
						Severity: sev,
						Category: cat,
						Message:  fmt.Sprintf("Pattern match: %s", p.String()),
						File:     path,
						Line:     i + 1,
					})
				}
			}
		}
	}

	return findings
}

func (n *Neuron) auditDirectory(ctx context.Context, dir string) []Finding {
	var allFindings []Finding

	filepath.Walk(dir, func(path string, info os.FileInfo, err error) error {
		if err != nil || info.IsDir() {
			return nil
		}
		select {
		case <-ctx.Done():
			return ctx.Err()
		default:
		}

		// Skip binary and large files
		if info.Size() > 1<<20 { // 1MB
			return nil
		}
		ext := filepath.Ext(path)
		if !isTextFile(ext) {
			return nil
		}

		findings := n.auditFile(path)
		allFindings = append(allFindings, findings...)
		return nil
	})

	return allFindings
}

func (n *Neuron) searchSecrets(ctx context.Context, dir string) []Finding {
	var findings []Finding

	filepath.Walk(dir, func(path string, info os.FileInfo, err error) error {
		if err != nil || info.IsDir() || info.Size() > 1<<20 {
			return nil
		}
		select {
		case <-ctx.Done():
			return ctx.Err()
		default:
		}

		if !isTextFile(filepath.Ext(path)) {
			return nil
		}

		data, err := os.ReadFile(path)
		if err != nil {
			return nil
		}

		lines := strings.Split(string(data), "\n")
		for i, line := range lines {
			for _, p := range n.patterns["secrets"] {
				if p.MatchString(line) {
					findings = append(findings, Finding{
						Severity: "critical",
						Category: "secret",
						Message:  "Potential secret/credential exposed",
						File:     path,
						Line:     i + 1,
					})
				}
			}
		}
		return nil
	})

	return findings
}

func (n *Neuron) analyzeLogs(path string) string {
	data, err := os.ReadFile(path)
	if err != nil {
		return fmt.Sprintf("Cannot read log file: %v", err)
	}

	lines := strings.Split(string(data), "\n")
	errors := 0
	warnings := 0
	for _, line := range lines {
		lower := strings.ToLower(line)
		if strings.Contains(lower, "error") || strings.Contains(lower, "fail") {
			errors++
		}
		if strings.Contains(lower, "warn") {
			warnings++
		}
	}

	return fmt.Sprintf("📊 Log Analysis: %s\n  Total lines: %d\n  Errors: %d\n  Warnings: %d",
		path, len(lines), errors, warnings)
}

func (n *Neuron) formatFindings(findings []Finding) core.Result {
	if len(findings) == 0 {
		return core.Result{Success: true, Output: "✅ No security issues found."}
	}

	var lines []string
	critical, high, medium, low := 0, 0, 0, 0
	for _, f := range findings {
		icon := "ℹ️"
		switch f.Severity {
		case "critical":
			icon = "🔴"
			critical++
		case "high":
			icon = "🟠"
			high++
		case "medium":
			icon = "🟡"
			medium++
		case "low":
			icon = "🟢"
			low++
		}
		loc := ""
		if f.File != "" {
			loc = fmt.Sprintf(" (%s:%d)", f.File, f.Line)
		}
		lines = append(lines, fmt.Sprintf("  %s [%s] %s%s", icon, strings.ToUpper(f.Severity), f.Message, loc))
	}

	summary := fmt.Sprintf("🐺 Audit: %d findings (🔴%d 🟠%d 🟡%d 🟢%d)\n\n%s",
		len(findings), critical, high, medium, low, strings.Join(lines, "\n"))

	return core.Result{
		Success: critical == 0 && high == 0,
		Output:  summary,
		Details: map[string]string{
			"total":    fmt.Sprintf("%d", len(findings)),
			"critical": fmt.Sprintf("%d", critical),
		},
	}
}

func compilePatterns(raw []string) []*regexp.Regexp {
	var compiled []*regexp.Regexp
	for _, p := range raw {
		compiled = append(compiled, regexp.MustCompile(p))
	}
	return compiled
}

func isTextFile(ext string) bool {
	textExts := map[string]bool{
		".py": true, ".go": true, ".js": true, ".ts": true, ".java": true,
		".rb": true, ".rs": true, ".c": true, ".h": true, ".cpp": true,
		".sh": true, ".bash": true, ".zsh": true,
		".yaml": true, ".yml": true, ".json": true, ".toml": true, ".ini": true,
		".md": true, ".txt": true, ".env": true, ".cfg": true, ".conf": true,
		".xml": true, ".html": true, ".css": true,
	}
	return textExts[strings.ToLower(ext)]
}
