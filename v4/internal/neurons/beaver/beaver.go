// Package beaver implements the natural-language firewall rule generator.
package beaver

import (
	"context"
	"fmt"
	"regexp"
	"strconv"
	"strings"

	"github.com/Alartist40/cynapse/internal/core"
)

// Rule represents a single firewall rule.
type Rule struct {
	Action   string `json:"action"`
	Protocol string `json:"protocol"`
	Port     int    `json:"port"`
	Source   string `json:"source"`
	Dest     string `json:"dest,omitempty"`
	IPTables string `json:"iptables"`
	NFT      string `json:"nft"`
}

// Neuron implements the Beaver firewall generator neuron.
type Neuron struct {
	backend string // "iptables" or "nftables"
}

func New(backend string) *Neuron {
	if backend == "" {
		backend = "iptables"
	}
	return &Neuron{backend: backend}
}

func (n *Neuron) ID() string             { return "beaver" }
func (n *Neuron) Name() string           { return "Beaver — Firewall Generator" }
func (n *Neuron) Capabilities() []string { return []string{"generate_rules", "parse_query", "list_rules"} }

func (n *Neuron) Execute(ctx context.Context, task core.Task) (core.Result, error) {
	switch task.Operation {
	case "generate_rules":
		query := task.Params["query"]
		rules, err := n.fromNaturalLanguage(query)
		if err != nil {
			return core.Result{Success: false, Output: err.Error()}, nil
		}
		var lines []string
		for _, r := range rules {
			if n.backend == "nftables" {
				lines = append(lines, r.NFT)
			} else {
				lines = append(lines, r.IPTables)
			}
		}
		return core.Result{
			Success: true,
			Output:  strings.Join(lines, "\n"),
			Details: map[string]string{"count": fmt.Sprintf("%d", len(rules)), "backend": n.backend},
		}, nil

	default:
		return core.Result{}, fmt.Errorf("beaver: unknown operation %s", task.Operation)
	}
}

var (
	portRe   = regexp.MustCompile(`(?i)port\s+(\d+)`)
	sourceRe = regexp.MustCompile(`(?i)from\s+(\S+)`)
	protoRe  = regexp.MustCompile(`(?i)(tcp|udp)`)
)

func (n *Neuron) fromNaturalLanguage(query string) ([]Rule, error) {
	lower := strings.ToLower(query)

	action := "DROP"
	if strings.Contains(lower, "allow") || strings.Contains(lower, "accept") {
		action = "ACCEPT"
	}

	protocol := "tcp"
	if m := protoRe.FindString(query); m != "" {
		protocol = strings.ToLower(m)
	}

	port := 0
	if m := portRe.FindStringSubmatch(query); len(m) > 1 {
		port, _ = strconv.Atoi(m[1])
	}

	source := "0.0.0.0/0"
	if m := sourceRe.FindStringSubmatch(query); len(m) > 1 {
		source = m[1]
	}

	// Security: Strict validation of extracted parameters
	if !isValidIP(source) && source != "any" {
		source = "0.0.0.0/0" // Fallback to safe default
	}

	rule := Rule{
		Action:   action,
		Protocol: protocol,
		Port:     port,
		Source:   source,
	}

	// Generate iptables syntax
	portFlag := ""
	if port > 0 {
		portFlag = fmt.Sprintf(" --dport %d", port)
	}
	rule.IPTables = fmt.Sprintf("iptables -A INPUT -p %s -s %s%s -j %s",
		protocol, source, portFlag, action)

	// Generate nftables syntax
	nftPort := ""
	if port > 0 {
		nftPort = fmt.Sprintf(" %s dport %d", protocol, port)
	}
	nftAction := strings.ToLower(action)
	rule.NFT = fmt.Sprintf("nft add rule inet filter input ip saddr %s%s %s",
		source, nftPort, nftAction)

	return []Rule{rule}, nil
}

// Security: Helper for IP/CIDR validation
func isValidIP(s string) bool {
	// Simple check for allowed characters in IP/CIDR
	match, _ := regexp.MatchString(`^[\d\. /]+$`, s)
	if !match {
		return false
	}
	// Try parsing it
	if strings.Contains(s, "/") {
		// CIDR
		return regexp.MustCompile(`^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}/\d{1,2}$`).MatchString(s)
	}
	// Single IP
	return regexp.MustCompile(`^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$`).MatchString(s)
}
