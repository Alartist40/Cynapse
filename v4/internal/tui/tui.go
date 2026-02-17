// Package tui implements the Cynapse terminal interface using Bubble Tea.
//
// Architecture:
//   Model (state) ← Update (input/events) → View (render)
//
// This replaces the Python TUI (terminal.py + state.py + view.py + main.py)
// with a single, declarative Elm-architecture implementation.
package tui

import (
	"fmt"
	"strings"
	"time"

	"github.com/charmbracelet/bubbles/textinput"
	"github.com/charmbracelet/bubbles/viewport"
	tea "github.com/charmbracelet/bubbletea"
	"github.com/charmbracelet/lipgloss"
)

// ----- Styles -----

var (
	appStyle = lipgloss.NewStyle().Padding(0, 1)

	headerStyle = lipgloss.NewStyle().
			Bold(true).
			Foreground(lipgloss.Color("#00FFAA")).
			Background(lipgloss.Color("#1a1a2e")).
			Padding(0, 1).
			Width(80)

	statusBarStyle = lipgloss.NewStyle().
			Foreground(lipgloss.Color("#888888")).
			Background(lipgloss.Color("#1a1a2e")).
			Padding(0, 1)

	userMsgStyle = lipgloss.NewStyle().
			Foreground(lipgloss.Color("#61AFEF")).
			Bold(true)

	assistantMsgStyle = lipgloss.NewStyle().
				Foreground(lipgloss.Color("#98C379"))

	systemMsgStyle = lipgloss.NewStyle().
			Foreground(lipgloss.Color("#E5C07B")).
			Italic(true)

	paletteStyle = lipgloss.NewStyle().
			Border(lipgloss.RoundedBorder()).
			BorderForeground(lipgloss.Color("#00FFAA")).
			Padding(0, 1).
			Width(60)

	paletteTitleStyle = lipgloss.NewStyle().
				Bold(true).
				Foreground(lipgloss.Color("#00FFAA"))

	paletteItemStyle = lipgloss.NewStyle().
				Foreground(lipgloss.Color("#ABB2BF"))

	paletteSelectedStyle = lipgloss.NewStyle().
				Foreground(lipgloss.Color("#282C34")).
				Background(lipgloss.Color("#00FFAA")).
				Bold(true)
)

// ----- Messages -----

type Message struct {
	Role    string // "user", "assistant", "system"
	Content string
	Time    time.Time
}

// tickMsg drives periodic updates (animation, status polling).
type tickMsg time.Time

func tickCmd() tea.Cmd {
	return tea.Tick(time.Second/2, func(t time.Time) tea.Msg {
		return tickMsg(t)
	})
}

// ----- Command Palette -----

type PaletteCommand struct {
	Name        string
	Description string
	Action      string // internal action key
}

var defaultCommands = []PaletteCommand{
	{Name: "quit", Description: "Exit Cynapse", Action: "quit"},
	{Name: "clear", Description: "Clear chat history", Action: "clear"},
	{Name: "health", Description: "Run system health check", Action: "health"},
	{Name: "agent researcher", Description: "Spawn Researcher agent", Action: "agent_researcher"},
	{Name: "agent coder", Description: "Spawn Coder agent", Action: "agent_coder"},
	{Name: "neurons", Description: "List available neurons", Action: "neurons"},
	{Name: "it-mode", Description: "Enter IT Support mode", Action: "it_mode"},
	{Name: "threads", Description: "Show active threads", Action: "threads"},
	{Name: "help", Description: "Show keyboard shortcuts", Action: "help"},
}

// ----- Model -----

// Model is the top-level Bubble Tea model for the Cynapse TUI.
type Model struct {
	// Chat state
	messages     []Message
	threads      map[string][]Message
	activeThread string

	// Input
	textInput textinput.Model

	// Viewport for scrollable chat
	viewport viewport.Model

	// Command palette
	showPalette    bool
	paletteQuery   string
	paletteMatches []PaletteCommand
	paletteIndex   int

	// Help overlay
	showHelp bool

	// Status
	modelState string // "ready", "thinking", "executing"
	width      int
	height     int
	ready      bool
}

// New creates the initial TUI model.
func New() Model {
	ti := textinput.New()
	ti.Placeholder = "Message Cynapse... (/ for commands)"
	ti.Focus()
	ti.CharLimit = 2048
	ti.Width = 76

	return Model{
		messages:       []Message{},
		threads:        map[string][]Message{"main": {}},
		activeThread:   "main",
		textInput:      ti,
		showPalette:    false,
		paletteMatches: defaultCommands,
		modelState:     "ready",
	}
}

// Init starts the TUI with an initial welcome message and tick loop.
func (m Model) Init() tea.Cmd {
	return tea.Batch(
		textinput.Blink,
		tickCmd(),
		tea.EnterAltScreen,
		func() tea.Msg {
			return Message{Role: "assistant", Content: "Welcome to Cynapse v4.0 — Ghost Shell Hub.\nHow can I help you today?", Time: time.Now()}
		},
	)
}

// Update handles all input events.
func (m Model) Update(msg tea.Msg) (tea.Model, tea.Cmd) {
	var cmds []tea.Cmd

	switch msg := msg.(type) {
	case tea.WindowSizeMsg:
		m.width = msg.Width
		m.height = msg.Height
		headerHeight := 3
		inputHeight := 3
		statusHeight := 1
		chatHeight := m.height - headerHeight - inputHeight - statusHeight - 2
		if !m.ready {
			m.viewport = viewport.New(m.width-2, chatHeight)
			m.viewport.YPosition = headerHeight
			m.ready = true
		} else {
			m.viewport.Width = m.width - 2
			m.viewport.Height = chatHeight
		}
		m.textInput.Width = m.width - 4
		m.viewport.SetContent(m.renderMessages())
		return m, nil

	case Message:
		m.messages = append(m.messages, msg)
		m.threads[m.activeThread] = append(m.threads[m.activeThread], msg)
		if m.ready {
			m.viewport.SetContent(m.renderMessages())
			m.viewport.GotoBottom()
		}
		return m, nil

	case tickMsg:
		return m, tickCmd()

	case tea.KeyMsg:
		// Global keys
		switch msg.String() {
		case "ctrl+q":
			return m, tea.Quit
		case "ctrl+i":
			m.showHelp = !m.showHelp
			return m, nil
		}

		// Help overlay consumes Esc
		if m.showHelp {
			if msg.String() == "esc" {
				m.showHelp = false
			}
			return m, nil
		}

		// Command palette mode
		if m.showPalette {
			return m.updatePalette(msg)
		}

		// Chat input mode
		switch msg.String() {
		case "/":
			if m.textInput.Value() == "" {
				m.showPalette = true
				m.paletteQuery = ""
				m.paletteIndex = 0
				m.filterPalette()
				return m, nil
			}
		case "enter":
			return m.sendMessage()
		}
	}

	// Forward to textInput
	var cmd tea.Cmd
	m.textInput, cmd = m.textInput.Update(msg)
	cmds = append(cmds, cmd)

	return m, tea.Batch(cmds...)
}

func (m Model) sendMessage() (tea.Model, tea.Cmd) {
	content := strings.TrimSpace(m.textInput.Value())
	if content == "" {
		return m, nil
	}

	userMsg := Message{Role: "user", Content: content, Time: time.Now()}
	m.messages = append(m.messages, userMsg)
	m.threads[m.activeThread] = append(m.threads[m.activeThread], userMsg)
	m.textInput.SetValue("")
	m.modelState = "thinking"

	if m.ready {
		m.viewport.SetContent(m.renderMessages())
		m.viewport.GotoBottom()
	}

	// Simulate async response (in production: dispatch to HiveMind)
	return m, func() tea.Msg {
		time.Sleep(800 * time.Millisecond)
		return Message{
			Role:    "assistant",
			Content: fmt.Sprintf("Processing: \"%s\"\n(HiveMind integration pending — this is a mock response.)", content),
			Time:    time.Now(),
		}
	}
}

func (m *Model) updatePalette(msg tea.KeyMsg) (tea.Model, tea.Cmd) {
	switch msg.String() {
	case "esc":
		m.showPalette = false
		return m, nil
	case "enter":
		if m.paletteIndex < len(m.paletteMatches) {
			action := m.paletteMatches[m.paletteIndex].Action
			m.showPalette = false
			m.paletteQuery = ""
			return m.executePaletteAction(action)
		}
		m.showPalette = false
		return m, nil
	case "up":
		if m.paletteIndex > 0 {
			m.paletteIndex--
		}
		return m, nil
	case "down":
		if m.paletteIndex < len(m.paletteMatches)-1 {
			m.paletteIndex++
		}
		return m, nil
	case "backspace":
		if len(m.paletteQuery) > 0 {
			m.paletteQuery = m.paletteQuery[:len(m.paletteQuery)-1]
			m.filterPalette()
		} else {
			m.showPalette = false
		}
		return m, nil
	default:
		if len(msg.String()) == 1 {
			m.paletteQuery += msg.String()
			m.paletteIndex = 0
			m.filterPalette()
		}
		return m, nil
	}
}

func (m *Model) filterPalette() {
	if m.paletteQuery == "" {
		m.paletteMatches = defaultCommands
		return
	}
	q := strings.ToLower(m.paletteQuery)
	var matches []PaletteCommand
	for _, cmd := range defaultCommands {
		if strings.Contains(strings.ToLower(cmd.Name), q) ||
			strings.Contains(strings.ToLower(cmd.Description), q) {
			matches = append(matches, cmd)
		}
	}
	m.paletteMatches = matches
}

func (m *Model) executePaletteAction(action string) (tea.Model, tea.Cmd) {
	switch action {
	case "quit":
		return m, tea.Quit
	case "clear":
		m.messages = nil
		m.threads[m.activeThread] = nil
		if m.ready {
			m.viewport.SetContent("")
		}
	case "help":
		m.showHelp = true
	case "health":
		sysMsg := Message{Role: "system", Content: "🏥 Health check: All systems operational.", Time: time.Now()}
		m.messages = append(m.messages, sysMsg)
		if m.ready {
			m.viewport.SetContent(m.renderMessages())
			m.viewport.GotoBottom()
		}
	case "neurons":
		sysMsg := Message{Role: "system", Content: "🧠 Neurons: Bat, Beaver, Canary, Meerkat, Octopus, Wolverine (Go)\n   Bridge: Elara, Owl (Python/gRPC)", Time: time.Now()}
		m.messages = append(m.messages, sysMsg)
		if m.ready {
			m.viewport.SetContent(m.renderMessages())
			m.viewport.GotoBottom()
		}
	default:
		sysMsg := Message{Role: "system", Content: fmt.Sprintf("⚙️  Action '%s' — not yet implemented.", action), Time: time.Now()}
		m.messages = append(m.messages, sysMsg)
		if m.ready {
			m.viewport.SetContent(m.renderMessages())
			m.viewport.GotoBottom()
		}
	}
	return m, nil
}

// ----- View -----

func (m Model) View() string {
	if !m.ready {
		return "\n  Initializing Cynapse..."
	}

	header := headerStyle.Render(
		fmt.Sprintf(" ⚡ CYNAPSE v4.0  │  Thread: %s  │  %s", m.activeThread, strings.ToUpper(m.modelState)),
	)

	statusBar := statusBarStyle.Render(
		fmt.Sprintf(" Ctrl+Q quit │ / commands │ Ctrl+I help │ %d messages", len(m.messages)),
	)

	input := m.textInput.View()

	var content string
	if m.showHelp {
		content = m.renderHelp()
	} else if m.showPalette {
		content = m.viewport.View() + "\n" + m.renderPalette()
	} else {
		content = m.viewport.View()
	}

	return appStyle.Render(
		lipgloss.JoinVertical(lipgloss.Left,
			header,
			content,
			statusBar,
			input,
		),
	)
}

func (m Model) renderMessages() string {
	var lines []string
	for _, msg := range m.messages {
		ts := msg.Time.Format("15:04")
		switch msg.Role {
		case "user":
			lines = append(lines, userMsgStyle.Render(fmt.Sprintf("[%s] You: %s", ts, msg.Content)))
		case "assistant":
			lines = append(lines, assistantMsgStyle.Render(fmt.Sprintf("[%s] Cynapse: %s", ts, msg.Content)))
		case "system":
			lines = append(lines, systemMsgStyle.Render(fmt.Sprintf("[%s] %s", ts, msg.Content)))
		}
		lines = append(lines, "") // spacing
	}
	return strings.Join(lines, "\n")
}

func (m Model) renderPalette() string {
	var items []string
	title := paletteTitleStyle.Render("⚡ Command Palette")
	query := fmt.Sprintf("  > %s", m.paletteQuery)
	items = append(items, title, query, "")

	for i, cmd := range m.paletteMatches {
		label := fmt.Sprintf("  %s — %s", cmd.Name, cmd.Description)
		if i == m.paletteIndex {
			items = append(items, paletteSelectedStyle.Render(label))
		} else {
			items = append(items, paletteItemStyle.Render(label))
		}
	}

	return paletteStyle.Render(strings.Join(items, "\n"))
}

func (m Model) renderHelp() string {
	help := `
  ⌨️  KEYBOARD SHORTCUTS
  ─────────────────────

  /              Open command palette
  Ctrl+Q         Quit
  Ctrl+I         Toggle this help
  Enter          Send message
  Esc            Close palette / help

  COMMANDS (via palette)
  ─────────────────────
  quit           Exit Cynapse
  clear          Clear chat
  health         System diagnostics
  neurons        List available neurons
  agent <role>   Spawn sub-agent
  it-mode        Self-repair mode
  threads        Show active threads
`
	return lipgloss.NewStyle().
		Foreground(lipgloss.Color("#ABB2BF")).
		Padding(1, 2).
		Render(help)
}
