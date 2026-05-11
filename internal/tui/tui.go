package tui

import (
	"context"
	"fmt"
	"strings"
	"time"

	tea "github.com/charmbracelet/bubbletea"
	"github.com/charmbracelet/lipgloss"
	"github.com/Alartist40/cynapse/internal/agent"
	"github.com/Alartist40/cynapse/internal/config"
	"github.com/Alartist40/cynapse/internal/llm"
)

// ─── Colors ───────────────────────────────────────────────────────────────────

var (
	purple = lipgloss.Color("#9b59b6")
	orange = lipgloss.Color("#e67e22")
	bg     = lipgloss.Color("#0a0e14")
	dim    = lipgloss.Color("#4a5568")
	bright = lipgloss.Color("#e4e7eb")
)

// ─── Styles ───────────────────────────────────────────────────────────────────

var (
	heroLargeStyle = lipgloss.NewStyle().
			Foreground(purple).
			Bold(true).
			Align(lipgloss.Center)

	heroSmallStyle = lipgloss.NewStyle().
			Foreground(purple).
			Bold(true)

	inputBoxStyle = lipgloss.NewStyle().
			BorderStyle(lipgloss.RoundedBorder()).
			BorderForeground(purple).
			Padding(0, 1)

	promptStyle = lipgloss.NewStyle().
			Foreground(purple).
			Bold(true)

	userMsgStyle = lipgloss.NewStyle().
			Foreground(bright).
			Bold(true)

	assistantMsgStyle = lipgloss.NewStyle().
				Foreground(dim)

	systemMsgStyle = lipgloss.NewStyle().
			Foreground(orange)

	statusBarStyle = lipgloss.NewStyle().
			Foreground(dim)

	menuStyle = lipgloss.NewStyle().
			BorderStyle(lipgloss.RoundedBorder()).
			BorderForeground(purple).
			Padding(0, 1)

	menuItemStyle = lipgloss.NewStyle().
			Foreground(dim).
			PaddingLeft(1)

	menuItemSelectedStyle = lipgloss.NewStyle().
				Foreground(purple).
				Bold(true).
				PaddingLeft(0)

	cursorStyle = lipgloss.NewStyle().
			Background(bright).
			Foreground(bg)
)

// ─── Messages ─────────────────────────────────────────────────────────────────

type agentResponseMsg struct {
	content string
	err     error
	elapsed time.Duration
	tokens  int
}

type agentStreamChunkMsg struct {
	chunk string
}

type agentStreamDoneMsg struct {
	elapsed time.Duration
	tokens  int
}

type modelListMsg struct {
	models []string
	err    error
}

// ─── Model ────────────────────────────────────────────────────────────────────

type Model struct {
	agent     *agent.Agent
	cfg       *config.Config
	llmClient llm.Client

	input       string
	cursor      int
	messages    []message
	showMenu    bool
	menuItems   []menuItem
	menuCursor  int
	width       int
	height      int
	waitingResp bool
	models      []string
	lastElapsed time.Duration
	lastTokens  int
	active      bool

	// Request cancellation
	cancelFunc   context.CancelFunc
	currentModel string

	// Streaming
	spinnerIndex     int
	streamingContent string
	streamStartTime  time.Time
	streamChunks     <-chan string
	streamErrors     <-chan error
}

type message struct {
	role    string
	content string
	time    time.Time
}

type tickMsg time.Time

func tick() tea.Cmd {
	return tea.Tick(time.Millisecond*100, func(t time.Time) tea.Msg {
		return tickMsg(t)
	})
}

type menuItem struct {
	label  string
	action func(*Model) tea.Cmd
}

func NewModel(ag *agent.Agent, cfg *config.Config, llmCli llm.Client) Model {
	return Model{
		agent:     ag,
		cfg:       cfg,
		llmClient: llmCli,
		messages:  []message{},
		menuItems: buildMenu(),
	}
}

func buildMenu() []menuItem {
	return []menuItem{
		{"Status", cmdStatus},
		{"Models", cmdModels},
		{"Memory", cmdMemory},
		{"Heartbeat", cmdHeartbeat},
		{"Clear", cmdClear},
		{"Help", cmdHelp},
		{"Quit", cmdQuit},
	}
}

func (m Model) Init() tea.Cmd {
	return nil
}

func (m Model) Update(msg tea.Msg) (tea.Model, tea.Cmd) {
	switch msg := msg.(type) {
	case tea.WindowSizeMsg:
		m.width = msg.Width
		m.height = msg.Height
		return m, nil

	case tea.KeyMsg:
		return m.handleKey(msg)

	case tickMsg:
		if m.waitingResp && m.streamingContent == "" {
			m.spinnerIndex++
			return m, tick()
		}
		return m, nil

	case agentResponseMsg:
		m.waitingResp = false
		if msg.err != nil {
			m.addSystemMsg(fmt.Sprintf("Error: %v", msg.err))
		}
		return m, nil

	case agentStreamChunkMsg:
		m.streamingContent += msg.chunk
		return m, m.listenForChunks()

	case agentStreamDoneMsg:
		m.waitingResp = false
		m.lastElapsed = msg.elapsed
		m.lastTokens = msg.tokens
		m.addAssistantMsg(m.streamingContent)
		m.streamingContent = ""
		return m, nil

	case modelListMsg:
		if msg.err != nil {
			m.addSystemMsg(fmt.Sprintf("Failed to load models: %v", msg.err))
			m.showMenu = false
			m.restoreMainMenu()
		} else {
			m.models = msg.models
			m.showModelsMenu()
		}
		return m, nil
	}

	return m, nil
}

func (m Model) handleKey(msg tea.KeyMsg) (tea.Model, tea.Cmd) {
	// Menu navigation
	if m.showMenu {
		switch msg.String() {
		case "up", "k":
			if m.menuCursor > 0 {
				m.menuCursor--
			}
			return m, nil
		case "down", "j":
			if m.menuCursor < len(m.menuItems)-1 {
				m.menuCursor++
			}
			return m, nil
		case "enter":
			if m.menuCursor < len(m.menuItems) {
				item := m.menuItems[m.menuCursor]
				
				// Close menu before executing action
				m.showMenu = false
				m.menuCursor = 0
				m.input = ""
				m.restoreMainMenu()
				
				return m, item.action(&m)
			}
			return m, nil
		case "esc":
			m.showMenu = false
			m.menuCursor = 0
			m.restoreMainMenu()
			return m, nil
		}
		return m, nil
	}

	// Input handling
	switch msg.String() {
	case "ctrl+c":
		if m.waitingResp {
			if m.cancelFunc != nil {
				m.cancelFunc()
			}
			m.waitingResp = false
			m.addSystemMsg("⚠ Request cancelled")
			return m, nil
		}
		if m.cancelFunc != nil {
			m.cancelFunc()
		}
		return m, tea.Quit

	case "enter":
		if m.input == "" {
			return m, nil
		}

		// Prevent sending while already waiting
		if m.waitingResp {
			m.addSystemMsg("⏳ Please wait for current response to complete")
			return m, nil
		}

		// Send to agent
		userInput := m.input
		m.addUserMsg(userInput)
		m.input = ""
		m.cursor = 0
		m.waitingResp = true
		m.spinnerIndex = 0

		var cmds []tea.Cmd
		if !m.active {
			m.active = true
			cmds = append(cmds, tea.ClearScreen)
		}

		cmds = append(cmds, m.sendToAgent(userInput), tick())
		return m, tea.Batch(cmds...)

	case "backspace":
		if len(m.input) > 0 && m.cursor > 0 {
			m.input = m.input[:m.cursor-1] + m.input[m.cursor:]
			m.cursor--
			// Close menu if we backspace the /
			if m.input == "" {
				m.showMenu = false
				m.restoreMainMenu()
			}
		}
		return m, nil

	case "left":
		if m.cursor > 0 {
			m.cursor--
		}
		return m, nil

	case "right":
		if m.cursor < len(m.input) {
			m.cursor++
		}
		return m, nil

	case "ctrl+k":
		m.showMenu = !m.showMenu
		if m.showMenu {
			m.restoreMainMenu()
		}
		return m, nil

	case "home", "ctrl+a":
		m.cursor = 0
		return m, nil

	case "end", "ctrl+e":
		m.cursor = len(m.input)
		return m, nil

	case "delete":
		if m.cursor < len(m.input) {
			m.input = m.input[:m.cursor] + m.input[m.cursor+1:]
		}
		return m, nil

	default:
		// Regular character input
		if len(msg.String()) == 1 {
			// Bounds check before slicing
			if m.cursor < 0 {
				m.cursor = 0
			}
			if m.cursor > len(m.input) {
				m.cursor = len(m.input)
			}
			m.input = m.input[:m.cursor] + msg.String() + m.input[m.cursor:]
			m.cursor++
		}
		return m, nil
	}
}

func (m Model) View() string {
	var content string
	if m.active {
		content = m.renderActive()
	} else {
		content = m.renderIdle()
	}
	return lipgloss.Place(m.width, m.height, lipgloss.Left, lipgloss.Top, content)
}

func (m Model) renderIdle() string {
	var b strings.Builder

	heroHeight := 8
	paddingTop := (m.height - heroHeight - 10) / 2
	if paddingTop < 0 {
		paddingTop = 0
	}

	for i := 0; i < paddingTop; i++ {
		b.WriteString("\n")
	}

	hero := `
  ██████╗██╗   ██╗███╗   ██╗ █████╗ ██████╗ ███████╗███████╗
 ██╔════╝╚██╗ ██╔╝████╗  ██║██╔══██╗██╔══██╗██╔════╝██╔════╝
 ██║      ╚████╔╝ ██╔██╗ ██║███████║██████╔╝███████╗█████╗  
 ██║       ╚██╔╝  ██║╚██╗██║██╔══██║██╔═══╝ ╚════██║██╔══╝  
 ╚██████╗   ██║   ██║ ╚████║██║  ██║██║     ███████║███████╗
  ╚═════╝   ╚═╝   ╚═╝  ╚═══╝╚═╝  ╚═╝╚═╝     ╚══════╝╚══════╝
`
	b.WriteString(heroLargeStyle.Width(m.width).Render(hero))
	b.WriteString("\n")

	hint := "Type Ctrl+K to open menu"
	hintStyle := lipgloss.NewStyle().Foreground(dim).Align(lipgloss.Center)
	b.WriteString(hintStyle.Width(m.width).Render(hint))
	b.WriteString("\n")

	remainingHeight := m.height - paddingTop - heroHeight - 10
	for i := 0; i < remainingHeight; i++ {
		b.WriteString("\n")
	}

	// Dropdown menu (appears above input)
	if m.showMenu {
		b.WriteString(m.renderDropdownMenu())
		b.WriteString("\n")
	}

	statusLeft := fmt.Sprintf("Model: %s", m.cfg.LLM.Model)
	b.WriteString(statusBarStyle.Render(statusLeft))
	b.WriteString("\n")

	prompt := promptStyle.Render("> ")

	var inputContent string
	if m.cursor < len(m.input) {
		inputContent = m.input[:m.cursor] + cursorStyle.Render(string(m.input[m.cursor])) + m.input[m.cursor+1:]
	} else {
		inputContent = m.input + cursorStyle.Render(" ")
	}
	b.WriteString(inputBoxStyle.Width(m.width - 4).Render(prompt + inputContent))

	return b.String()
}

func (m Model) renderActive() string {
	var b strings.Builder

	smallLogo := " CYNAPSE"
	b.WriteString(heroSmallStyle.Render(smallLogo))
	b.WriteString("\n")
	b.WriteString(strings.Repeat("─", m.width))
	b.WriteString("\n\n")

	maxMessages := m.height - 10
	start := 0
	if len(m.messages) > maxMessages {
		start = len(m.messages) - maxMessages
	}

	for _, msg := range m.messages[start:] {
		switch msg.role {
		case "user":
			b.WriteString(userMsgStyle.Render("You: "))
			b.WriteString(msg.content)
		case "assistant":
			b.WriteString(assistantMsgStyle.Render("CYNAPSE: "))
			b.WriteString(msg.content)
		case "tool":
			b.WriteString(lipgloss.NewStyle().Foreground(orange).Render("🔧 Tool: "))
			b.WriteString(lipgloss.NewStyle().Foreground(dim).Render(msg.content))
		case "system":
			b.WriteString(systemMsgStyle.Render("● "))
			b.WriteString(systemMsgStyle.Render(msg.content))
		}
		b.WriteString("\n\n")
	}

	if m.waitingResp {
		if m.streamingContent != "" {
			b.WriteString(assistantMsgStyle.Render("CYNAPSE: "))
			b.WriteString(m.streamingContent)
			b.WriteString("\n\n")
		} else {
			frames := []string{"⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"}
			frame := frames[m.spinnerIndex%len(frames)]
			b.WriteString(lipgloss.NewStyle().Foreground(orange).Render(fmt.Sprintf("  %s thinking...", frame)))
			b.WriteString("\n\n")
		}
	}

	currentLines := strings.Count(b.String(), "\n")
	for i := currentLines; i < m.height-10; i++ {
		b.WriteString("\n")
	}

	// Dropdown menu (appears above input)
	if m.showMenu {
		b.WriteString(m.renderDropdownMenu())
		b.WriteString("\n")
	}

	statusLeft := fmt.Sprintf("Model: %s", m.cfg.LLM.Model)
	statusRight := ""
	if m.lastElapsed > 0 {
		statusRight = fmt.Sprintf("⏱ %dms", m.lastElapsed.Milliseconds())
		if m.lastTokens > 0 {
			statusRight += fmt.Sprintf(" | 🪙 %d tokens", m.lastTokens)
		}
	}
	statusBar := statusLeft
	if statusRight != "" {
		padding := m.width - len(statusLeft) - len(statusRight) - 2
		if padding > 0 {
			statusBar += strings.Repeat(" ", padding) + statusRight
		}
	}
	b.WriteString(statusBarStyle.Render(statusBar))
	b.WriteString("\n")

	prompt := promptStyle.Render("> ")

	var inputContent string
	if m.cursor < len(m.input) {
		inputContent = m.input[:m.cursor] + cursorStyle.Render(string(m.input[m.cursor])) + m.input[m.cursor+1:]
	} else {
		inputContent = m.input + cursorStyle.Render(" ")
	}
	b.WriteString(inputBoxStyle.Width(m.width - 4).Render(prompt + inputContent))

	return b.String()
}

func (m Model) renderDropdownMenu() string {
	var items []string
	for i, item := range m.menuItems {
		if i == m.menuCursor {
			items = append(items, menuItemSelectedStyle.Render("▸ "+item.label))
		} else {
			items = append(items, menuItemStyle.Render("  "+item.label))
		}
	}
	return menuStyle.Render(strings.Join(items, "\n"))
}

func (m *Model) showModelsMenu() {
	var modelItems []menuItem
	for _, modelName := range m.models {
		name := modelName
		modelItems = append(modelItems, menuItem{
			label: name,
			action: func(m *Model) tea.Cmd {
				// Cancel in-flight request if switching models
				if m.waitingResp && m.cancelFunc != nil {
					m.cancelFunc()
					m.waitingResp = false
					m.addSystemMsg("⚠ Cancelled previous request")
				}

				m.cfg.LLM.Model = name
				m.showMenu = false
				m.input = ""
				m.addSystemMsg(fmt.Sprintf("Switched to model: %s", name))
				m.restoreMainMenu()
				return nil
			},
		})
	}
	modelItems = append(modelItems, menuItem{"← Back", func(m *Model) tea.Cmd {
		m.restoreMainMenu()
		m.menuCursor = 0
		return nil
	}})
	m.menuItems = modelItems
	m.showMenu = true
	m.menuCursor = 0
}

func (m *Model) restoreMainMenu() {
	m.menuItems = buildMenu()
	m.menuCursor = 0
}

// ─── Commands ─────────────────────────────────────────────────────────────────

func (m *Model) sendToAgent(input string) tea.Cmd {
	// Cancel any in-flight request
	if m.cancelFunc != nil {
		m.cancelFunc()
	}

	// Create new cancellable context
	ctx, cancel := context.WithTimeout(context.Background(), 180*time.Second)
	m.cancelFunc = cancel
	m.currentModel = m.cfg.LLM.Model
	m.streamStartTime = time.Now()

	chunks, errs := m.agent.ProcessMessageStream(ctx, input)
	m.streamChunks = chunks
	m.streamErrors = errs

	return m.listenForChunks()
}

func (m *Model) listenForChunks() tea.Cmd {
	return func() tea.Msg {
		select {
		case chunk, ok := <-m.streamChunks:
			if !ok {
				// Stream complete
				elapsed := time.Since(m.streamStartTime)
				tokens := len(m.streamingContent) / 4
				return agentStreamDoneMsg{elapsed: elapsed, tokens: tokens}
			}
			// Got a chunk - return it
			return agentStreamChunkMsg{chunk: chunk}
			
		case err, ok := <-m.streamErrors:
			if ok && err != nil {
				// Got an error
				return agentResponseMsg{err: err}
			}
			// Error channel closed, check chunks again
			select {
			case chunk, ok := <-m.streamChunks:
				if !ok {
					elapsed := time.Since(m.streamStartTime)
					tokens := len(m.streamingContent) / 4
					return agentStreamDoneMsg{elapsed: elapsed, tokens: tokens}
				}
				return agentStreamChunkMsg{chunk: chunk}
			default:
				// Both closed
				elapsed := time.Since(m.streamStartTime)
				tokens := len(m.streamingContent) / 4
				return agentStreamDoneMsg{elapsed: elapsed, tokens: tokens}
			}
		}
	}
}

func cmdStatus(m *Model) tea.Cmd {
	m.showMenu = false
	m.input = ""
	m.addSystemMsg(fmt.Sprintf("Provider: %s | Model: %s | Memory: Active | Agent: Ready", m.cfg.LLM.Provider, m.cfg.LLM.Model))
	return nil
}

func cmdModels(m *Model) tea.Cmd {
	if strings.ToLower(m.cfg.LLM.Provider) != "ollama" {
		m.showMenu = false
		m.input = ""
		m.addSystemMsg("Model switching only available for Ollama")
		return nil
	}

	// Show loading state
	m.menuItems = []menuItem{
		{"Loading models...", func(m *Model) tea.Cmd { return nil }},
	}
	m.menuCursor = 0

	// Fetch models async
	return func() tea.Msg {
		models, err := llm.ListOllamaModels(m.cfg.LLM.OllamaBaseURL)
		return modelListMsg{models: models, err: err}
	}
}

func cmdMemory(m *Model) tea.Cmd {
	m.showMenu = false
	m.input = ""
	m.addSystemMsg("Memory: Persona files in ./data/persona/ | SQLite store active | Heartbeat curator running")
	return nil
}

func cmdHeartbeat(m *Model) tea.Cmd {
	m.showMenu = false
	m.input = ""
	m.addSystemMsg("Running heartbeat curator...")
	return func() tea.Msg {
		ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
		defer cancel()
		start := time.Now()
		err := m.agent.TriggerHeartbeat(ctx)
		elapsed := time.Since(start)
		if err != nil {
			return agentResponseMsg{content: "", err: err, elapsed: elapsed}
		}
		return agentResponseMsg{content: "Heartbeat complete. MEMORY.md updated.", err: nil, elapsed: elapsed}
	}
}

func cmdClear(m *Model) tea.Cmd {
	m.showMenu = false
	m.input = ""
	m.messages = []message{}
	m.active = false
	m.addSystemMsg("Chat cleared. Back to idle state.")
	return tea.ClearScreen
}

func cmdHelp(m *Model) tea.Cmd {
	m.showMenu = false
	m.input = ""
	help := `CYNAPSE Commands:
  Ctrl+K      Open command menu
  Status      System status
  Models      Switch Ollama models
  Memory      View memory info
  Heartbeat   Run memory curator
  Clear       Reset to idle screen
  Quit        Exit

Type naturally to chat with the agent.`
	m.addSystemMsg(help)
	return nil
}

func cmdQuit(m *Model) tea.Cmd {
	if m.cancelFunc != nil {
		m.cancelFunc()
	}
	return tea.Quit
}

func (m *Model) addUserMsg(content string) {
	m.messages = append(m.messages, message{role: "user", content: content, time: time.Now()})
}

func (m *Model) addAssistantMsg(content string) {
	m.messages = append(m.messages, message{role: "assistant", content: content, time: time.Now()})
}

func (m *Model) addSystemMsg(content string) {
	m.messages = append(m.messages, message{role: "system", content: content, time: time.Now()})
}
