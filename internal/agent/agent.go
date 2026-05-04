package agent

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"strings"
	"time"

	"github.com/yourusername/cynapse/internal/config"
	"github.com/yourusername/cynapse/internal/llm"
	"github.com/yourusername/cynapse/internal/mcp"
	"github.com/yourusername/cynapse/internal/memory"
	"github.com/yourusername/cynapse/internal/session"
	"github.com/yourusername/cynapse/internal/tools"
)

const maxToolIterations = 10

type Agent struct {
	deviceID string
	llm      llm.Client
	persona  *memory.Persona
	memStore *memory.Store
	sessions *session.Manager
	tools    *tools.Registry
	mcp      *mcp.Manager
	curator  *memory.Curator
	cfg      *config.Config
}

func New(
	deviceID string,
	llmClient llm.Client,
	persona *memory.Persona,
	store *memory.Store,
	sessions *session.Manager,
	mcpMgr *mcp.Manager,
	cfg *config.Config,
) *Agent {
	reg := tools.BuildProfile(
		cfg.Tools.Profile,
		cfg.Tools.WorkDir,
		cfg.Tools.TimeoutSeconds,
		persona.WriteFile,
		persona.AppendDailyLog,
		func(query string, limit int) (string, error) {
			entries, err := store.Search(deviceID, query, limit)
			if err != nil {
				return "", err
			}
			if len(entries) == 0 {
				return "(no memories found)", nil
			}
			var lines []string
			for _, e := range entries {
				lines = append(lines, fmt.Sprintf("[%s] %s", e.Time.Format("2006-01-02"), e.Fact))
			}
			return strings.Join(lines, "\n"), nil
		},
	)

	return &Agent{
		deviceID: deviceID,
		llm:      llmClient,
		persona:  persona,
		memStore: store,
		sessions: sessions,
		tools:    reg,
		mcp:      mcpMgr,
		curator:  memory.NewCurator(persona, llmClient, cfg.Memory.HeartbeatIntervalHours),
		cfg:      cfg,
	}
}

func (a *Agent) StartCurator(ctx context.Context) {
	a.curator.Start(ctx)
}

func (a *Agent) TriggerHeartbeat(ctx context.Context) error {
	return a.curator.RunMaintenance(ctx)
}

// ProcessMessage handles one user turn. Returns the final text response.
func (a *Agent) ProcessMessage(ctx context.Context, userMsg string) (string, error) {
	sess, err := a.sessions.Get(a.deviceID)
	if err != nil {
		return "", fmt.Errorf("getting session: %w", err)
	}

	sess.Append(session.Entry{Role: llm.RoleUser, Content: userMsg})

	if sess.Len() > a.cfg.Memory.MaxSessionMessages {
		sess.Compact(a.cfg.Memory.MaxSessionMessages / 2)
	}

	allTools := a.tools.Schemas()
	allTools = append(allTools, a.mcp.AllTools()...)

	req := &llm.Request{
		SystemPrompt: a.persona.CompileSystemPrompt(),
		Messages:     sess.Recent(60),
		Tools:        allTools,
		MaxTokens:    a.cfg.LLM.MaxTokens,
		Temperature:  a.cfg.LLM.Temperature,
	}

	finalResponse := ""
	for iter := 0; iter < maxToolIterations; iter++ {
		resp, err := a.llm.Chat(ctx, req)
		if err != nil {
			return "", fmt.Errorf("LLM error: %w", err)
		}

		if len(resp.ToolCalls) == 0 {
			finalResponse = resp.Content
			break
		}

		req.Messages = append(req.Messages, llm.Message{
			Role:      llm.RoleAssistant,
			ToolCalls: resp.ToolCalls,
		})
		sess.Append(session.Entry{Role: llm.RoleAssistant, ToolCalls: resp.ToolCalls})

		for _, tc := range resp.ToolCalls {
			result, execErr := a.executeTool(ctx, tc)
			content := result
			if execErr != nil {
				content = "Error: " + execErr.Error()
			}
			msg := llm.Message{Role: llm.RoleTool, ToolCallID: tc.ID, Content: content}
			req.Messages = append(req.Messages, msg)
			sess.Append(session.Entry{Role: llm.RoleTool, Content: content})
		}
	}

	if finalResponse == "" {
		finalResponse = "(agent reached tool iteration limit)"
	}

	sess.Append(session.Entry{Role: llm.RoleAssistant, Content: finalResponse})

	go a.selfImproveFork(userMsg, finalResponse)

	return finalResponse, nil
}

func (a *Agent) executeTool(ctx context.Context, tc llm.ToolCall) (string, error) {
	log.Printf("[AGENT:%s] tool=%s args=%s", a.deviceID, tc.Name, truncate(string(tc.Arguments), 120))

	result, handled, err := a.mcp.Execute(ctx, tc.Name, tc.Arguments)
	if handled {
		return result, err
	}
	return a.tools.Execute(ctx, tc.Name, tc.Arguments)
}

// selfImproveFork runs after each turn in the background.
// It asks the LLM whether anything worth saving happened.
func (a *Agent) selfImproveFork(userMsg, agentResponse string) {
	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()

	promptText := "Review this conversation turn.\n\nUser: " + userMsg + "\n\nAssistant: " + agentResponse + "\n\nDecide:\n1. Is there a fact worth saving to long-term memory? If yes, provide it.\n2. Should the USER.md profile be updated?\n3. What is a good one-line summary for the daily log?\n\nRespond in JSON only:\n{\"save_fact\":\"\",\"save_fact_tags\":\"\",\"update_user\":false,\"daily_log\":\"\"}"

	resp, err := a.llm.Chat(ctx, &llm.Request{
		SystemPrompt: "You are a memory curator. Respond only with the requested JSON.",
		Messages:     []llm.Message{{Role: llm.RoleUser, Content: promptText}},
		MaxTokens:    300,
		Temperature:  0.2,
	})
	if err != nil {
		return
	}

	content := strings.TrimSpace(resp.Content)
	// Strip markdown fences if present
	content = strings.TrimPrefix(content, "```json")
	content = strings.TrimPrefix(content, "```")
	content = strings.TrimSuffix(content, "```")
	content = strings.TrimSpace(content)

	var decision struct {
		SaveFact    string `json:"save_fact"`
		SaveFactTags string `json:"save_fact_tags"`
		UpdateUser  bool   `json:"update_user"`
		DailyLog    string `json:"daily_log"`
	}
	if err := json.Unmarshal([]byte(content), &decision); err != nil {
		return
	}

	if strings.TrimSpace(decision.SaveFact) != "" {
		a.memStore.Save(a.deviceID, decision.SaveFact, userMsg, decision.SaveFactTags)
		log.Printf("[AGENT:%s] saved memory: %s", a.deviceID, truncate(decision.SaveFact, 80))
	}

	if strings.TrimSpace(decision.DailyLog) != "" {
		a.persona.AppendDailyLog(decision.DailyLog)
	}
}

func truncate(s string, n int) string {
	if len(s) <= n {
		return s
	}
	return s[:n] + "..."
}
