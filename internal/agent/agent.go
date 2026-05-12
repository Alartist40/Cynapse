package agent

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"strings"
	"time"

	"github.com/Alartist40/cynapse/internal/api"
	"github.com/Alartist40/cynapse/internal/config"
	"github.com/Alartist40/cynapse/internal/llm"
	"github.com/Alartist40/cynapse/internal/mcp"
	"github.com/Alartist40/cynapse/internal/memory"
	"github.com/Alartist40/cynapse/internal/session"
	"github.com/Alartist40/cynapse/internal/tools"
)

const maxToolIterations = 10

var graphAPIServer *api.Server

type Agent struct {
	deviceID string
	llm      llm.Client
	persona  *memory.Persona
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
		persona.Search,
	)

	return &Agent{
		deviceID: deviceID,
		llm:      llmClient,
		persona:  persona,
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

// StartGraphServer starts the knowledge graph web UI server.
// Safe to call multiple times — reuses the existing server.
func (a *Agent) StartGraphServer(ctx context.Context) (string, error) {
	if graphAPIServer != nil {
		return graphAPIServer.URL(), nil
	}
	graphAPIServer = api.NewServer(a.persona.Graph(), a.persona.Store())
	return graphAPIServer.Start(ctx)
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
		SystemPrompt: a.persona.CompileSystemPrompt(userMsg),
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
		a.persona.SaveFact(decision.SaveFact, decision.SaveFactTags)
		log.Printf("[AGENT:%s] saved memory: %s", a.deviceID, truncate(decision.SaveFact, 80))
	}

	if strings.TrimSpace(decision.DailyLog) != "" {
		a.persona.AppendDailyLog(decision.DailyLog)
	}
}

func (a *Agent) ProcessMessageStream(ctx context.Context, userInput string) (<-chan string, <-chan error) {
	chunks := make(chan string, 10)
	errors := make(chan error, 1)

	go func() {
		defer close(chunks)
		defer close(errors)

		sess, err := a.sessions.Get(a.deviceID)
		if err != nil {
			errors <- fmt.Errorf("getting session: %w", err)
			return
		}

		sess.Append(session.Entry{Role: llm.RoleUser, Content: userInput})

		if sess.Len() > a.cfg.Memory.MaxSessionMessages {
			sess.Compact(a.cfg.Memory.MaxSessionMessages / 2)
		}

		allTools := a.tools.Schemas()
		allTools = append(allTools, a.mcp.AllTools()...)

		for iter := 0; iter < maxToolIterations; iter++ {
			// Call LLM with streaming
			llmChunks, llmErrors := a.llm.ChatStream(ctx, &llm.Request{
				SystemPrompt: a.persona.CompileSystemPrompt(userInput),
				Messages:     sess.Recent(60),
				Tools:        allTools,
				MaxTokens:    a.cfg.LLM.MaxTokens,
				Temperature:  a.cfg.LLM.Temperature,
			})

			fullResponse := ""
			// Forward chunks
			for {
				select {
				case chunk, ok := <-llmChunks:
					if !ok {
						llmChunks = nil
					} else {
						fullResponse += chunk
						chunks <- chunk
					}
				case err := <-llmErrors:
					if err != nil {
						errors <- err
						return
					}
					llmErrors = nil
				case <-ctx.Done():
					errors <- ctx.Err()
					return
				}
				if llmChunks == nil && llmErrors == nil {
					break
				}
			}

			// Check if fullResponse contains tool calls
			var toolCalls []llm.ToolCall
			if err := json.Unmarshal([]byte(fullResponse), &toolCalls); err == nil && len(toolCalls) > 0 {
				// It's a tool call!
				sess.Append(session.Entry{Role: llm.RoleAssistant, ToolCalls: toolCalls})

				for _, tc := range toolCalls {
					chunks <- fmt.Sprintf("\n🔧 Executing: %s...\n", tc.Name)
					result, execErr := a.executeTool(ctx, tc)
					content := result
					if execErr != nil {
						content = "Error: " + execErr.Error()
					}
					sess.Append(session.Entry{Role: llm.RoleTool, ToolCallID: tc.ID, Content: content})
					chunks <- fmt.Sprintf("✅ Result from %s received.\n", tc.Name)
				}
				// Loop back for next turn
				continue
			}

			// No tool calls, finish
			if fullResponse != "" {
				sess.Append(session.Entry{Role: llm.RoleAssistant, Content: fullResponse})
				go a.selfImproveFork(userInput, fullResponse)
			}
			return
		}

		chunks <- "\n⚠️ (agent reached tool iteration limit)\n"
	}()

	return chunks, errors
}

func truncate(s string, n int) string {
	if len(s) <= n {
		return s
	}
	return s[:n] + "..."
}
