// Package octopus implements container escape detection and defense.
package octopus

import (
	"context"
	"fmt"
	"os"
	"os/exec"
	"strings"

	"github.com/Alartist40/cynapse/internal/core"
)

// Neuron implements the Octopus container security neuron.
type Neuron struct{}

func New() *Neuron { return &Neuron{} }

func (n *Neuron) ID() string             { return "octopus" }
func (n *Neuron) Name() string           { return "Octopus — Container Escape Detection" }
func (n *Neuron) Capabilities() []string { return []string{"detect_escape", "audit_container", "check_privileges"} }

func (n *Neuron) Execute(ctx context.Context, task core.Task) (core.Result, error) {
	switch task.Operation {
	case "detect_escape":
		findings := n.detectEscapeVectors()
		if len(findings) == 0 {
			return core.Result{Success: true, Output: "🐙 No container escape vectors detected."}, nil
		}
		return core.Result{
			Success: true,
			Output:  fmt.Sprintf("🐙 Found %d potential escape vectors:\n%s", len(findings), strings.Join(findings, "\n")),
			Details: map[string]string{"risk_count": fmt.Sprintf("%d", len(findings))},
		}, nil

	case "audit_container":
		report := n.auditContainer()
		return core.Result{Success: true, Output: report}, nil

	case "check_privileges":
		privs := n.checkPrivileges()
		return core.Result{Success: true, Output: privs}, nil

	default:
		return core.Result{}, fmt.Errorf("octopus: unknown operation %s", task.Operation)
	}
}

func (n *Neuron) detectEscapeVectors() []string {
	var findings []string

	// Check if running in a container
	if _, err := os.Stat("/.dockerenv"); err == nil {
		findings = append(findings, "  ⚠️  Running inside Docker container")
	}

	// Check for privileged mode
	if data, err := os.ReadFile("/proc/1/cgroup"); err == nil {
		if strings.Contains(string(data), "docker") || strings.Contains(string(data), "containerd") {
			findings = append(findings, "  ℹ️  Container runtime detected in cgroups")
		}
	}

	// Check for Docker socket mount
	if _, err := os.Stat("/var/run/docker.sock"); err == nil {
		findings = append(findings, "  🔴 Docker socket mounted — HIGH RISK escape vector")
	}

	// Check for SYS_ADMIN capability
	if data, err := os.ReadFile("/proc/self/status"); err == nil {
		if strings.Contains(string(data), "CapEff:\t0000003fffffffff") {
			findings = append(findings, "  🔴 Full capabilities detected — privileged container")
		}
	}

	// Check for writable /proc/sysrq-trigger
	if fi, err := os.Stat("/proc/sysrq-trigger"); err == nil {
		if fi.Mode().Perm()&0200 != 0 {
			findings = append(findings, "  🔴 Writable /proc/sysrq-trigger — escape possible")
		}
	}

	return findings
}

func (n *Neuron) auditContainer() string {
	var lines []string
	lines = append(lines, "🐙 Container Security Audit")
	lines = append(lines, strings.Repeat("─", 40))

	// User check
	if os.Geteuid() == 0 {
		lines = append(lines, "  🔴 Running as root")
	} else {
		lines = append(lines, "  ✅ Non-root user")
	}

	// Namespace checks
	if data, err := os.ReadFile("/proc/self/cgroup"); err == nil {
		lines = append(lines, fmt.Sprintf("  📦 Cgroup: %s", strings.TrimSpace(string(data[:min(100, len(data))]))))
	}

	// Mount check
	if out, err := exec.Command("mount").Output(); err == nil {
		mountCount := strings.Count(string(out), "\n")
		lines = append(lines, fmt.Sprintf("  📁 Mount points: %d", mountCount))
	}

	return strings.Join(lines, "\n")
}

func (n *Neuron) checkPrivileges() string {
	var lines []string
	lines = append(lines, "🔑 Privilege Report:")

	lines = append(lines, fmt.Sprintf("  UID: %d  EUID: %d", os.Getuid(), os.Geteuid()))
	lines = append(lines, fmt.Sprintf("  GID: %d  EGID: %d", os.Getgid(), os.Getegid()))

	if data, err := os.ReadFile("/proc/self/status"); err == nil {
		for _, line := range strings.Split(string(data), "\n") {
			if strings.HasPrefix(line, "Cap") {
				lines = append(lines, "  "+strings.TrimSpace(line))
			}
		}
	}

	return strings.Join(lines, "\n")
}

func min(a, b int) int {
	if a < b {
		return a
	}
	return b
}
