package agent

import (
	"fmt"
	"strings"

	"github.com/Alartist40/cynapse-mini/internal/config"
	"github.com/Alartist40/cynapse-mini/internal/llm"
	"github.com/Alartist40/cynapse-mini/internal/memory"
)

// Agent is a lightweight agent that processes user input and generates responses
type Agent struct {
	deviceID string
	llm      llm.Client
	store    *memory.LightweightStore
	cfg      *config.Config
}

// New creates a new lightweight agent
func New(
	deviceID string,
	llmClient llm.Client,
	store *memory.LightweightStore,
	cfg *config.Config,
) *Agent {
	return &Agent{
		deviceID: deviceID,
		llm:      llmClient,
		store:    store,
		cfg:      cfg,
	}
}

// ProcessStreaming processes user input and streams the response
func (a *Agent) ProcessStreaming(input string, onChunk func(string)) error {
	// Save user message
	a.store.Save(memory.Message{
		Role:    "user",
		Content: input,
	})

	// Build minimal context (only recent messages)
	context := a.buildContext()

	// Stream response from LLM
	fullResponse := ""
	err := a.llm.StreamChat(
		a.cfg.LLM.Provider,
		a.cfg.LLM.Model,
		context,
		func(chunk string) {
			fullResponse += chunk
			onChunk(chunk)
		},
	)

	if err != nil {
		return err
	}

	// Add newline after response
	onChunk("\n")

	// Save assistant response
	a.store.Save(memory.Message{
		Role:    "assistant",
		Content: fullResponse,
	})

	return nil
}

// buildContext builds the context from recent messages
func (a *Agent) buildContext() []map[string]string {
	// Get recent messages (only keep 20 in context)
	recent := a.store.GetRecent(20)

	context := make([]map[string]string, 0, len(recent))
	for _, msg := range recent {
		context = append(context, map[string]string{
			"role":    msg.Role,
			"content": msg.Content,
		})
	}

	return context
}

// ProcessSync processes user input and returns full response at once
// Use this for commands that need the full response immediately
func (a *Agent) ProcessSync(input string) (string, error) {
	// Save user message
	a.store.Save(memory.Message{
		Role:    "user",
		Content: input,
	})

	// Build context
	context := a.buildContext()

	// Get response from LLM
	response, err := a.llm.Chat(
		a.cfg.LLM.Provider,
		a.cfg.LLM.Model,
		context,
	)

	if err != nil {
		return "", err
	}

	// Save response
	a.store.Save(memory.Message{
		Role:    "assistant",
		Content: response,
	})

	return response, nil
}

// GetSummary returns a brief summary of the conversation
func (a *Agent) GetSummary() string {
	recent := a.store.GetRecent(5)

	if len(recent) == 0 {
		return "No conversation yet"
	}

	summary := fmt.Sprintf("Last %d messages:\n", len(recent))
	for _, msg := range recent {
		label := "User"
		if msg.Role == "assistant" {
			label = "Agent"
		}

		content := msg.Content
		if len(content) > 80 {
			content = content[:80] + "..."
		}

		summary += fmt.Sprintf("  [%s] %s\n", label, strings.ReplaceAll(content, "\n", " "))
	}

	return summary
}

// ProcessCommand processes special commands
func (a *Agent) ProcessCommand(cmd string) string {
	switch cmd {
	case "status":
		return "CYNAPSE Mini is running normally\n"

	case "stats":
		stats := a.store.Statistics()
		return fmt.Sprintf("Memory Statistics:\n  Total messages: %d\n  Cached in memory: %d/%d\n",
			stats["total_messages"],
			stats["memory_cached_messages"],
			stats["memory_limit"],
		)

	default:
		return "Unknown command: " + cmd
	}
}
