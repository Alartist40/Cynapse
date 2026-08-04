//! The chat TUI application (milestone 6).
//!
//! ratatui-based interactive chat, faithful to the Go Bubble Tea TUI:
//! an idle hero screen, an active chat view with streaming responses,
//! slash commands, a Ctrl+K command menu, and an in-chat confirmation
//! prompt that implements the `confirm::Prompter` protocol so gated
//! bash/web commands can ask the operator for a decision mid-turn.
//!
//! Threading model: crossterm events are read on a dedicated thread
//! and forwarded over a tokio channel; the agent's streaming turn runs
//! in a spawned task; confirmation requests cross back over another
//! channel pair. The main loop `tokio::select!`s on all three.

use std::sync::mpsc as stdmpsc;
use std::sync::Arc;
use std::time::{Duration, Instant};

use anyhow::{anyhow, Context as _, Result};
use crossterm::event::{Event, KeyCode, KeyEvent, KeyModifiers, MouseEventKind};
use crossterm::execute;
use crossterm::terminal::{
    disable_raw_mode, enable_raw_mode, EnterAlternateScreen, LeaveAlternateScreen,
};
use ratatui::backend::CrosstermBackend;
use ratatui::layout::{Alignment, Constraint, Layout, Rect};
use ratatui::style::{Color, Modifier, Style};
use ratatui::text::{Line, Span, Text};
use ratatui::widgets::{Block, Borders, Paragraph};
use ratatui::{Frame, Terminal};
use unicode_width::UnicodeWidthStr;

use cynapse_core::agent::Agent;
use cynapse_core::approval;
use cynapse_core::attachments;
use cynapse_core::config::Config;
use cynapse_core::confirm::{self, Allowlist, Decision, Resolver, Section};
use cynapse_core::llm::{self, Attachment as LlmAttachment};
use cynapse_core::netguard;
use cynapse_core::persona::Persona;
use cynapse_core::session::Manager;
use cynapse_core::tools::build_profile;

// ─── Palette (matches the Go lipgloss styles) ────────────────────────────────

const PURPLE: Color = Color::Rgb(0x9b, 0x59, 0xb6);
const ORANGE: Color = Color::Rgb(0xe6, 0x7e, 0x22);
const DIM: Color = Color::Rgb(0x4a, 0x55, 0x68);
const BRIGHT: Color = Color::Rgb(0xe4, 0xe7, 0xeb);

const HERO: &str = "\
  ██████╗██╗   ██╗███╗   ██╗ █████╗ ██████╗ ███████╗███████╗\n\
 ██╔════╝╚██╗ ██╔╝████╗  ██║██╔══██╗██╔══██╗██╔════╝██╔════╝\n\
 ██║      ╚████╔╝ ██╔██╗ ██║███████║██████╔╝███████╗█████╗  \n\
 ██║       ╚██╔╝  ██║╚██╗██║██╔══██║██╔═══╝ ╚════██║██╔══╝  \n\
 ╚██████╗   ██║   ██║ ╚████║██║  ██║██║     ███████║███████╗\n\
  ╚═════╝   ╚═╝   ╚═╝  ╚═══╝╚═╝  ╚═╝╚═╝     ╚══════╝╚══════╝";

const SPINNER: [&str; 10] = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"];

// ─── Chat messages ───────────────────────────────────────────────────────────

#[derive(Debug, Clone)]
enum UiMsg {
    User(String),
    Assistant(String),
    Tool(String),
    ToolResult(String),
    System(String),
}

// ─── TUI⇄tool confirm bridge ────────────────────────────────────────────────

/// Envelope sent from a blocking tool thread to the UI event loop.
pub struct ConfirmMsg {
    pub req: confirm::Request,
    pub reply: stdmpsc::SyncSender<Result<confirm::Resolved, String>>,
}

/// `confirm::Prompter` backed by a channel to the TUI event loop. The
/// UI shows the question card and forwards the operator's D/O/S/A (or
/// secret line) back to the blocked tool thread.
#[derive(Clone)]
pub struct TuiPrompter {
    tx: tokio::sync::mpsc::UnboundedSender<ConfirmMsg>,
}

pub fn new_prompter() -> (TuiPrompter, tokio::sync::mpsc::UnboundedReceiver<ConfirmMsg>) {
    let (tx, rx) = tokio::sync::mpsc::unbounded_channel();
    (TuiPrompter { tx }, rx)
}

impl confirm::Prompter for TuiPrompter {
    fn ask(&self, r: &confirm::Request) -> Result<confirm::Resolved> {
        let (reply_tx, reply_rx) = stdmpsc::sync_channel(1);
        let msg = ConfirmMsg {
            req: r.clone(),
            reply: reply_tx,
        };
        self.tx
            .send(msg)
            .map_err(|_| anyhow!("TUI prompter is not connected"))?;
        match reply_rx.recv() {
            Ok(Ok(res)) => Ok(res),
            Ok(Err(e)) => Err(anyhow!("{e}")),
            Err(_) => Ok(confirm::Resolved {
                decision: Decision::Decline,
                input: String::new(),
                remembered_rule: String::new(),
            }),
        }
    }
}

/// Format the in-chat confirmation card, mirroring the Go TUI.
fn format_confirm_card(r: &confirm::Request) -> String {
    let mut b = format!("\n⚠  {}\n", r.title);
    for line in r.detail.lines() {
        b.push_str(&format!("    {line}\n"));
    }
    b.push_str("\n  [");
    let keys = confirm_keys(r.is_sensitive());
    for (i, k) in keys.iter().enumerate() {
        if i > 0 {
            b.push_str(" / ");
        }
        b.push_str(&format!("{}) {}", short_letter(*k), option_label(*k)));
    }
    b.push_str("]\n");
    if r.secret {
        b.push_str("  (input is hidden — the value you type goes only to this command)\n");
    }
    b
}

fn short_letter(d: Decision) -> &'static str {
    match d {
        Decision::Decline => "D",
        Decision::AllowOnce => "O",
        Decision::AllowSection => "S",
        Decision::AllowAlways => "A",
    }
}

fn option_label(d: Decision) -> &'static str {
    match d {
        Decision::Decline => "Decline",
        Decision::AllowOnce => "Allow once",
        Decision::AllowSection => "Allow this section",
        Decision::AllowAlways => "Always allow",
    }
}

fn confirm_keys(sensitive: bool) -> Vec<Decision> {
    if sensitive {
        vec![Decision::Decline, Decision::AllowOnce, Decision::AllowSection]
    } else {
        vec![Decision::Decline, Decision::AllowOnce, Decision::AllowSection, Decision::AllowAlways]
    }
}

fn key_to_decision(c: char) -> Option<Decision> {
    match c.to_ascii_lowercase() {
        'd' | 'n' => Some(Decision::Decline),
        'o' | 'y' => Some(Decision::AllowOnce),
        's' => Some(Decision::AllowSection),
        'a' => Some(Decision::AllowAlways),
        _ => None,
    }
}

/// System-message echo of what the operator picked.
fn resolved_echo(c: char, req: &confirm::Request) -> String {
    let label = match c.to_ascii_lowercase() {
        'd' | 'n' => "declined".to_string(),
        'o' | 'y' => "allowed once".to_string(),
        's' => "allowed for this section".to_string(),
        'a' => format!("always allowed — wrote rule: {}", req.rule_key),
        _ => "?".to_string(),
    };
    if req.is_sensitive() && matches!(c.to_ascii_lowercase(), 'a') {
        return "→ allowed once (sensitive; 'always' refused, secret not persisted)\n".to_string();
    }
    let mut msg = format!("→ {label}\n");
    if label.contains("always") && !req.is_sensitive() {
        msg.push_str(
            "  (this command will not prompt again until you remove its rule from\n   ~/.cynapse/allowlist)\n",
        );
    }
    msg
}

// ─── Menu ───────────────────────────────────────────────────────────────────

#[derive(Clone)]
enum MenuAction {
    Status,
    Models,
    Clear,
    Help,
    Quit,
    Back,
    SelectModel(String),
}

#[derive(Clone)]
struct MenuItem {
    label: String,
    action: MenuAction,
}

fn main_menu() -> Vec<MenuItem> {
    vec![
        MenuItem { label: "Status".into(), action: MenuAction::Status },
        MenuItem { label: "Models".into(), action: MenuAction::Models },
        MenuItem { label: "Clear".into(), action: MenuAction::Clear },
        MenuItem { label: "Help".into(), action: MenuAction::Help },
        MenuItem { label: "Quit".into(), action: MenuAction::Quit },
    ]
}

fn help_text() -> &'static str {
    "CYNAPSE Commands:
  Ctrl+K         Open command menu
  Status         System status
  Models         Switch Ollama models
  Clear          Reset to idle screen
  Quit           Exit

Attachments:
  /attach <file>      Attach a file from workspace
  /attachments        List pending attachments
  /clear-attach       Clear all attachments
  /compress           Force context compression to DENDRITE

Memory:
  /memory <query>     Full-text search the DENDRITE graph

Allowlist:
  /allowed             Show allowlist subcommands
  /allowed list        Show all persisted rules
  /allowed forget <r>  Remove one rule
  /allowed clear       Remove every rule

Confirmation prompt (in-chat, automatic):
  When the agent wants to run a flagged command the chat shows
  ⚠  Run shell command?  with [D) Decline / O) Allow once /
  S) Allow this section / A) Always allow].  Press the letter.

Type naturally to chat with the agent."
}

// ─── Confirm prompt state ───────────────────────────────────────────────────

struct ConfirmState {
    req: confirm::Request,
    reply: stdmpsc::SyncSender<Result<confirm::Resolved, String>>,
}

fn allowed_help() -> &'static str {
    "📃 allowlist subcommands:
    /allowed list                 show all rules persisted
    /allowed forget <rule>        remove one rule
    /allowed clear                remove every rule

Rules are stored in ~/.cynapse/allowlist, one per line.  Each line
is the rule key the gate matched against.  Removing a line
tightens policy again — the operator is the source of truth."
}

// ─── App ────────────────────────────────────────────────────────────────────

struct App {
    agent: Arc<Agent>,
    cfg: Config,
    allowlist: Arc<Allowlist>,
    llm_client: Arc<dyn llm::LlmClient>,

    messages: Vec<UiMsg>,
    input: String,
    cursor: usize,
    active: bool,
    quit: bool,

    busy: bool,
    streaming: String,
    spinner: usize,
    stream_start: Instant,
    last_elapsed: Option<Duration>,
    last_tokens: usize,

    menu_open: bool,
    menu_items: Vec<MenuItem>,
    menu_cursor: usize,

    confirm: Option<ConfirmState>,
    secret_buffer: String,
    pending_attachments: Vec<LlmAttachment>,

    chunks: Option<tokio::sync::mpsc::UnboundedReceiver<String>>,
    errors: Option<tokio::sync::mpsc::UnboundedReceiver<anyhow::Error>>,
    events_rx: tokio::sync::mpsc::UnboundedReceiver<Event>,
    confirm_rx: tokio::sync::mpsc::UnboundedReceiver<ConfirmMsg>,

    chat_scroll: usize,
    follow: bool,
    width: u16,
    height: u16,
}

impl App {
    fn new(
        agent: Arc<Agent>,
        cfg: Config,
        allowlist: Arc<Allowlist>,
        llm_client: Arc<dyn llm::LlmClient>,
        events_rx: tokio::sync::mpsc::UnboundedReceiver<Event>,
        confirm_rx: tokio::sync::mpsc::UnboundedReceiver<ConfirmMsg>,
    ) -> App {
        App {
            agent,
            cfg,
            allowlist,
            llm_client,
            messages: Vec::new(),
            input: String::new(),
            cursor: 0,
            active: false,
            quit: false,
            busy: false,
            streaming: String::new(),
            spinner: 0,
            stream_start: Instant::now(),
            last_elapsed: None,
            last_tokens: 0,
            menu_open: false,
            menu_items: main_menu(),
            menu_cursor: 0,
            confirm: None,
            secret_buffer: String::new(),
            pending_attachments: Vec::new(),
            chunks: None,
            errors: None,
            events_rx,
            confirm_rx,
            chat_scroll: 0,
            follow: true,
            width: 0,
            height: 0,
        }
    }

    fn current_model(&self) -> String {
        let m = self.llm_client.current_model();
        if m.is_empty() {
            self.cfg.llm.model.clone()
        } else {
            m
        }
    }

    // ── Event handling ──────────────────────────────────────────────────────

    async fn on_event(&mut self, ev: Event) -> Result<bool> {
        match ev {
            Event::Key(k) => self.handle_key(k).await?,
            Event::Resize(w, h) => {
                self.width = w;
                self.height = h;
            }
            Event::Mouse(m) => match m.kind {
                MouseEventKind::ScrollUp => {
                    self.follow = false;
                    self.chat_scroll = self.chat_scroll.saturating_sub(3);
                }
                MouseEventKind::ScrollDown => {
                    self.follow = false;
                    self.chat_scroll = self.chat_scroll.saturating_add(3);
                }
                _ => {}
            },
            _ => {}
        }
        Ok(self.quit)
    }

    fn on_tick(&mut self) {
        if self.busy && self.streaming.is_empty() {
            self.spinner = (self.spinner + 1) % SPINNER.len();
        }
    }

    async fn handle_key(&mut self, key: KeyEvent) -> Result<()> {
        if self.menu_open {
            match key.code {
                KeyCode::Up | KeyCode::Char('k') if key.modifiers.is_empty() => {
                    if self.menu_cursor > 0 {
                        self.menu_cursor -= 1;
                    }
                }
                KeyCode::Down | KeyCode::Char('j') if key.modifiers.is_empty() => {
                    if self.menu_cursor + 1 < self.menu_items.len() {
                        self.menu_cursor += 1;
                    }
                }
                KeyCode::Enter => self.run_menu_action().await,
                KeyCode::Esc => self.close_menu(),
                _ => {}
            }
            return Ok(());
        }

        if self.confirm.is_some() {
            self.handle_confirm_key(key);
            return Ok(());
        }

        match key.code {
            KeyCode::Char('c') if key.modifiers.contains(KeyModifiers::CONTROL) => {
                self.quit = true;
            }
            KeyCode::Enter => self.submit().await,
            KeyCode::Backspace => self.backspace(),
            KeyCode::Left => {
                if self.cursor > 0 {
                    self.cursor -= 1;
                }
            }
            KeyCode::Right => {
                if self.cursor < self.input.chars().count() {
                    self.cursor += 1;
                }
            }
            KeyCode::PageUp => {
                self.follow = false;
                self.chat_scroll = self.chat_scroll.saturating_add(10);
            }
            KeyCode::PageDown => {
                self.chat_scroll = self.chat_scroll.saturating_sub(10);
                if self.chat_scroll == 0 {
                    self.follow = true;
                }
            }
            KeyCode::Char('k') if key.modifiers.contains(KeyModifiers::CONTROL) => {
                self.toggle_menu();
            }
            KeyCode::Esc => {
                self.quit = true;
            }
            KeyCode::Char(c) if key.modifiers == KeyModifiers::NONE || key.modifiers.contains(KeyModifiers::SHIFT) => {
                let byte_idx = self
                    .input
                    .char_indices()
                    .nth(self.cursor)
                    .map(|(i, _)| i)
                    .unwrap_or(self.input.len());
                self.input.insert(byte_idx, c);
                self.cursor += 1;
            }
            _ => {}
        }
        Ok(())
    }

    fn backspace(&mut self) {
        if self.cursor == 0 {
            return;
        }
        let byte_idx = self
            .input
            .char_indices()
            .nth(self.cursor - 1)
            .map(|(i, _)| i)
            .unwrap_or(0);
        self.input.remove(byte_idx);
        self.cursor -= 1;
        if self.input.is_empty() {
            self.close_menu();
        }
    }

    fn toggle_menu(&mut self) {
        self.menu_open = !self.menu_open;
        if self.menu_open {
            self.restore_main_menu();
        }
    }

    fn close_menu(&mut self) {
        self.menu_open = false;
        self.menu_cursor = 0;
        self.restore_main_menu();
    }

    fn restore_main_menu(&mut self) {
        self.menu_items = main_menu();
        self.menu_cursor = 0;
    }

    async fn run_menu_action(&mut self) {
        let Some(item) = self.menu_items.get(self.menu_cursor).cloned() else {
            return;
        };
        self.menu_open = false;
        self.menu_cursor = 0;
        self.input.clear();
        self.cursor = 0;
        match item.action {
            MenuAction::Status => {
                let msg = format!(
                    "Provider: {} | Model: {} | Memory: Active | Agent: Ready",
                    self.cfg.llm.provider,
                    self.current_model()
                );
                self.messages.push(UiMsg::System(msg));
            }
            MenuAction::Models => {
                if !self.cfg.llm.provider.eq_ignore_ascii_case("ollama") {
                    self.messages
                        .push(UiMsg::System("Model switching only available for Ollama".to_string()));
                    return;
                }
                self.menu_items = vec![MenuItem {
                    label: "Loading models…".into(),
                    action: MenuAction::Back,
                }];
                self.menu_cursor = 0;
                self.menu_open = true;
                match llm::list_ollama_models(&self.cfg.llm.ollama_base_url).await {
                    Ok(models) => {
                        let mut items: Vec<MenuItem> = models
                            .into_iter()
                            .map(|m| MenuItem {
                                label: m.clone(),
                                action: MenuAction::SelectModel(m),
                            })
                            .collect();
                        items.push(MenuItem { label: "← Back".into(), action: MenuAction::Back });
                        self.menu_items = items;
                        self.menu_cursor = 0;
                    }
                    Err(e) => {
                        self.menu_open = false;
                        self.messages
                            .push(UiMsg::System(format!("Failed to load models: {e}")));
                        self.restore_main_menu();
                    }
                }
            }
            MenuAction::SelectModel(name) => {
                self.llm_client.set_model(&name);
                self.cfg.llm.model = name.clone();
                self.messages
                    .push(UiMsg::System(format!("Switched to Ollama model: {name}")));
                self.restore_main_menu();
            }
            MenuAction::Clear => {
                self.messages.clear();
                self.active = false;
                self.follow = true;
            }
            MenuAction::Help => {
                self.messages.push(UiMsg::System(help_text().to_string()));
            }
            MenuAction::Quit => {
                self.quit = true;
            }
            MenuAction::Back => {
                self.restore_main_menu();
            }
        }
    }

    // ── Sending ─────────────────────────────────────────────────────────────

    async fn submit(&mut self) {
        if self.input.trim().is_empty() || self.busy {
            return;
        }
        let input = self.input.clone();
        if input.trim_start().starts_with('/') {
            self.handle_slash(&input).await;
            return;
        }

        let mut display = input.clone();
        if !self.pending_attachments.is_empty() {
            let names: Vec<String> = self
                .pending_attachments
                .iter()
                .map(|a| format!("{} ({})", a.filename, a.kind))
                .collect();
            display = format!("{input} 📎[{}]", names.join(", "));
        }
        self.messages.push(UiMsg::User(display));
        self.input.clear();
        self.cursor = 0;
        self.busy = true;
        self.streaming.clear();
        self.stream_start = Instant::now();
        self.spinner = 0;
        self.follow = true;
        self.chat_scroll = 0;

        let atts = std::mem::take(&mut self.pending_attachments);
        let (chunks, errors) = self.agent.process_message_stream(&input, atts).await;
        self.chunks = Some(chunks);
        self.errors = Some(errors);
    }

    async fn handle_slash(&mut self, input: &str) {
        let trimmed = input.trim();
        if let Some(rest) = trimmed.strip_prefix("/attach ") {
            let filename = rest.trim();
            let workdir = if self.cfg.tools.work_dir.is_empty() {
                "./workspace"
            } else {
                &self.cfg.tools.work_dir
            };
            match attachments::find_in_workspace(filename, workdir) {
                Ok(path) => match attachments::load(&path) {
                    Ok(att) => {
                        self.pending_attachments.push(LlmAttachment {
                            kind: att.kind.as_str().to_string(),
                            filename: att.filename.clone(),
                            mime: att.mime.clone(),
                            content: att.content.clone(),
                        });
                        self.messages.push(UiMsg::System(format!(
                            "📎 Attached: {} ({})",
                            att.filename,
                            att.kind.as_str()
                        )));
                    }
                    Err(e) => self
                        .messages
                        .push(UiMsg::System(format!("⚠ Failed to load attachment: {e}"))),
                },
                Err(e) => self.messages.push(UiMsg::System(format!("⚠ Cannot attach: {e}"))),
            }
            self.input.clear();
            self.cursor = 0;
            return;
        }

        match trimmed {
            "/clear-attach" => {
                self.pending_attachments.clear();
                self.messages.push(UiMsg::System("📎 Cleared all attachments".to_string()));
            }
            "/attachments" => {
                if self.pending_attachments.is_empty() {
                    self.messages.push(UiMsg::System("📎 No pending attachments".to_string()));
                } else {
                    let names: Vec<String> = self
                        .pending_attachments
                        .iter()
                        .map(|a| format!("{} ({})", a.filename, a.kind))
                        .collect();
                    self.messages
                        .push(UiMsg::System(format!("📎 Pending: {}", names.join(", "))));
                }
            }
            "/compress" => match self.agent.compress_now() {
                Ok((turns, saved)) => {
                    if turns == 0 && saved == 0 {
                        self.messages.push(UiMsg::System(
                            "🗜  Nothing to compress — session is already below threshold."
                                .to_string(),
                        ));
                    } else {
                        self.messages.push(UiMsg::System(format!(
                            "🗜  Compressed {turns} turn(s) into DENDRITE, saved ~{saved} tokens."
                        )));
                    }
                }
                Err(e) => self.messages.push(UiMsg::System(format!("⚠ Compress: {e}"))),
            },
            "/help" => {
                self.messages.push(UiMsg::System(help_text().to_string()));
            }
            "/clear" => {
                self.messages.clear();
                self.follow = true;
                self.messages.push(UiMsg::System("Chat cleared.".to_string()));
            }
            _ if trimmed.starts_with("/allowed") => self.handle_allowed(trimmed),
            _ if trimmed.starts_with("/memory") => self.handle_memory(trimmed),
            _ => {
                self.messages
                    .push(UiMsg::System(format!("Unknown command: {trimmed}")));
            }
        }
        self.input.clear();
        self.cursor = 0;
    }

    fn handle_allowed(&mut self, input: &str) {
        let parts: Vec<&str> = input.split_whitespace().collect();
        if parts.len() < 2 {
            self.messages.push(UiMsg::System(allowed_help().to_string()));
            return;
        }
        match parts[1] {
            "list" | "ls" => {
                let rules = self.allowlist.snapshot();
                if rules.is_empty() {
                    self.messages
                        .push(UiMsg::System("📃 ~/.cynapse/allowlist is empty.".to_string()));
                } else {
                    let mut msg = format!("📃 ~/.cynapse/allowlist ({} rules):\n", rules.len());
                    for r in &rules {
                        msg.push_str(&format!("    {r}\n"));
                    }
                    self.messages.push(UiMsg::System(msg));
                }
            }
            "forget" | "rm" => {
                if parts.len() < 3 {
                    self.messages
                        .push(UiMsg::System("Usage: /allowed forget <rule>".to_string()));
                    return;
                }
                let mut key = parts[2..].join(" ");
                if !key.contains(':') {
                    key = format!("bash:{key}");
                }
                match self.allowlist.forget(&key) {
                    Ok(_) => self.messages.push(UiMsg::System(format!("🗑  Removed rule: {key}"))),
                    Err(e) => self
                        .messages
                        .push(UiMsg::System(format!("⚠ Forget failed: {e}"))),
                }
            }
            "clear" => {
                let rules = self.allowlist.snapshot();
                let count = rules.len();
                for r in &rules {
                    if let Err(e) = self.allowlist.forget(r) {
                        self.messages
                            .push(UiMsg::System(format!("⚠ Forget failed on {r}: {e}")));
                        return;
                    }
                }
                let remaining = self.allowlist.snapshot().len();
                self.messages
                    .push(UiMsg::System(format!("🗑  Cleared {} rules.", count - remaining)));
            }
            _ => {
                self.messages.push(UiMsg::System(allowed_help().to_string()));
            }
        }
    }

    fn handle_memory(&mut self, input: &str) {
        let query = input
            .strip_prefix("/memory")
            .unwrap_or("")
            .trim()
            .to_string();
        if query.is_empty() {
            self.messages
                .push(UiMsg::System("Usage: /memory <query>".to_string()));
            return;
        }
        match cynapse_core::dendrite::DendriteStore::open(&self.cfg.memory.dendrite_db_path) {
            Ok(store) => match store.fts_search(&query, 10) {
                Ok(ids) => {
                    if ids.is_empty() {
                        self.messages.push(UiMsg::System(format!(
                            "🔎 No memories found for \"{query}\"."
                        )));
                        return;
                    }
                    let graph = cynapse_core::dendrite::Dendrite::new();
                    let _ = store.load_all(&graph);
                    let mut msg = format!("🔎 {} match(es) for \"{query}\":\n", ids.len());
                    for id in ids.iter().take(5) {
                        if let Some(node) = graph.get(id) {
                            let content: String = node
                                .content
                                .chars()
                                .take(140)
                                .collect();
                            msg.push_str(&format!(
                                "    • [{}] {} — {}\n",
                                node.node_type.label(),
                                node.title,
                                content
                            ));
                        }
                    }
                    self.messages.push(UiMsg::System(msg));
                }
                Err(e) => self.messages.push(UiMsg::System(format!("⚠ Search failed: {e}"))),
            },
            Err(e) => self.messages.push(UiMsg::System(format!("⚠ Cannot open DENDRITE: {e}"))),
        }
    }

    // ── Streaming ───────────────────────────────────────────────────────────

    fn on_chunk(&mut self, chunk: &str) {
        let t = chunk.trim();
        if let Some(rest) = t.strip_prefix("[tool result]") {
            self.messages.push(UiMsg::ToolResult(rest.trim().to_string()));
            return;
        }
        if let Some(rest) = t.strip_prefix("[tool]") {
            self.messages.push(UiMsg::Tool(rest.trim().to_string()));
            return;
        }
        self.streaming.push_str(chunk);
    }

    fn finalize_stream(&mut self) {
        if !self.busy {
            return;
        }
        self.busy = false;
        let content = std::mem::take(&mut self.streaming);
        if !content.is_empty() {
            self.last_tokens = llm::estimate_tokens_chars(&content);
            self.messages.push(UiMsg::Assistant(content));
        }
        self.last_elapsed = Some(self.stream_start.elapsed());
        self.chunks = None;
        self.errors = None;
        self.follow = true;
        if self.confirm.is_some() {
            self.resolve_confirm(confirm::Resolved {
                decision: Decision::Decline,
                input: String::new(),
                remembered_rule: String::new(),
            });
            self.messages
                .push(UiMsg::System("⏹ Turn ended; pending confirmation cancelled.".to_string()));
        }
    }

    fn on_stream_error(&mut self, e: anyhow::Error) {
        self.busy = false;
        self.streaming.clear();
        self.chunks = None;
        self.errors = None;
        self.messages.push(UiMsg::System(format!("Error: {e}")));
        if self.confirm.is_some() {
            self.resolve_confirm(confirm::Resolved {
                decision: Decision::Decline,
                input: String::new(),
                remembered_rule: String::new(),
            });
        }
    }

    // ── Confirm prompt handling ─────────────────────────────────────────────

    fn on_confirm_request(&mut self, msg: ConfirmMsg) {
        let card = format_confirm_card(&msg.req);
        self.messages.push(UiMsg::System(card));
        self.confirm = Some(ConfirmState { req: msg.req, reply: msg.reply });
        self.secret_buffer.clear();
        self.follow = true;
    }

    fn resolve_confirm(&mut self, res: confirm::Resolved) {
        if let Some(cs) = self.confirm.take() {
            let _ = cs.reply.send(Ok(res));
        }
        self.secret_buffer.clear();
    }

    fn handle_confirm_key(&mut self, key: KeyEvent) {
        let Some(cs) = self.confirm.as_ref() else {
            return;
        };
        let req = cs.req.clone();
        let secret = req.secret;
        let sensitive = req.is_sensitive();

        if secret {
            match key.code {
                KeyCode::Enter => {
                    let input = std::mem::take(&mut self.secret_buffer);
                    self.resolve_confirm(confirm::Resolved {
                        decision: Decision::AllowOnce,
                        input,
                        remembered_rule: String::new(),
                    });
                    self.messages.push(UiMsg::System("🔒 (secret received)".to_string()));
                }
                KeyCode::Esc => {
                    self.resolve_confirm(confirm::Resolved {
                        decision: Decision::Decline,
                        input: String::new(),
                        remembered_rule: String::new(),
                    });
                    self.messages.push(UiMsg::System("🔒 (cancelled)".to_string()));
                }
                KeyCode::Backspace => {
                    self.secret_buffer.pop();
                }
                KeyCode::Char('c') if key.modifiers.contains(KeyModifiers::CONTROL) => {
                    self.resolve_confirm(confirm::Resolved {
                        decision: Decision::Decline,
                        input: String::new(),
                        remembered_rule: String::new(),
                    });
                }
                KeyCode::Char(c) if !key.modifiers.contains(KeyModifiers::CONTROL) => {
                    self.secret_buffer.push(c);
                }
                _ => {}
            }
            return;
        }

        if let KeyCode::Char(c) = key.code {
            if let Some(decision) = key_to_decision(c) {
                self.messages.push(UiMsg::System(resolved_echo(c, &req)));
                let decision =
                    if sensitive && decision == Decision::AllowAlways { Decision::AllowOnce } else { decision };
                self.resolve_confirm(confirm::Resolved {
                    decision,
                    input: String::new(),
                    remembered_rule: if decision == Decision::AllowAlways {
                        req.rule_key.clone()
                    } else {
                        String::new()
                    },
                });
            }
        }
    }

    // ── Rendering ───────────────────────────────────────────────────────────

    fn draw(&mut self, f: &mut Frame) {
        let area = f.area();
        self.width = area.width;
        self.height = area.height;
        self.active = !self.messages.is_empty();
        if self.active {
            self.render_active(f, area);
        } else {
            self.render_idle(f, area);
        }
    }

    fn render_idle(&mut self, f: &mut Frame, area: Rect) {
        let menu_h = if self.menu_open { self.menu_height() } else { 0 };
        let layout = Layout::vertical([
            Constraint::Min(6),
            Constraint::Length(menu_h),
            Constraint::Length(1),
            Constraint::Length(3),
        ])
        .split(area);

        let hero_y = layout[0]
            .y
            .saturating_add(layout[0].height.saturating_sub(6) / 2)
            .saturating_sub(2);
        let hero = Paragraph::new(Text::from(HERO))
            .style(Style::default().fg(PURPLE).add_modifier(Modifier::BOLD))
            .alignment(Alignment::Center);
        f.render_widget(hero, Rect::new(area.x, hero_y, area.width, 6));

        let hint = Paragraph::new(Line::from(Span::styled(
            "Type Ctrl+K to open menu, or start typing to chat",
            Style::default().fg(DIM),
        )))
        .alignment(Alignment::Center);
        f.render_widget(hint, Rect::new(area.x, hero_y.saturating_add(7), area.width, 1));

        self.render_menu_overlay(f, layout[1]);
        self.render_status_bar(f, layout[2]);
        self.render_input(f, layout[3]);
    }

    fn render_active(&mut self, f: &mut Frame, area: Rect) {
        let menu_h = if self.menu_open { self.menu_height() } else { 0 };
        let layout = Layout::vertical([
            Constraint::Length(1),
            Constraint::Length(1),
            Constraint::Min(3),
            Constraint::Length(menu_h),
            Constraint::Length(1),
            Constraint::Length(3),
        ])
        .split(area);

        let logo = Paragraph::new(Line::from(Span::styled(
            " CYNAPSE",
            Style::default().fg(PURPLE).add_modifier(Modifier::BOLD),
        )));
        f.render_widget(logo, layout[0]);

        let rule = Paragraph::new(Line::from(Span::styled(
            "─".repeat(area.width as usize),
            Style::default().fg(DIM),
        )));
        f.render_widget(rule, layout[1]);

        let lines = self.chat_lines(layout[2].width as usize);
        let total = lines.len();
        let viewport = layout[2].height as usize;
        let scroll = if self.follow {
            total.saturating_sub(viewport)
        } else {
            self.chat_scroll.min(total.saturating_sub(viewport))
        };
        self.chat_scroll = scroll;

        let chat = Paragraph::new(Text::from(lines))
            .style(Style::default().fg(BRIGHT))
            .scroll((scroll as u16, 0));
        f.render_widget(chat, layout[2]);

        self.render_menu_overlay(f, layout[3]);
        self.render_status_bar(f, layout[4]);
        self.render_input(f, layout[5]);
    }

    fn menu_height(&self) -> u16 {
        (self.menu_items.len() as u16).min(24).saturating_add(2)
    }

    fn render_menu_overlay(&mut self, f: &mut Frame, area: Rect) {
        if !self.menu_open || area.height == 0 {
            return;
        }
        let menu_w = area.width.min(44);
        let box_area = Rect {
            x: area.x + area.width.saturating_sub(menu_w),
            y: area.y,
            width: menu_w,
            height: area.height,
        };
        let mut lines = Vec::new();
        for (i, item) in self.menu_items.iter().enumerate() {
            if i == self.menu_cursor {
                lines.push(Line::from(Span::styled(
                    format!("▸ {}", item.label),
                    Style::default().fg(PURPLE).add_modifier(Modifier::BOLD),
                )));
            } else {
                lines.push(Line::from(Span::styled(
                    format!("  {}", item.label),
                    Style::default().fg(DIM),
                )));
            }
        }
        let menu = Paragraph::new(lines)
            .block(Block::default().borders(Borders::ALL).border_style(Style::default().fg(PURPLE)));
        f.render_widget(menu, box_area);
    }

    fn render_status_bar(&mut self, f: &mut Frame, area: Rect) {
        let left = format!("Model: {}", self.current_model());
        let mut right = String::new();
        if let Some(elapsed) = self.last_elapsed {
            right = format!("⏱ {}ms", elapsed.as_millis());
            if self.last_tokens > 0 {
                right.push_str(&format!(" | 🪙 {} tokens", self.last_tokens));
            }
        }
        if let Some(cs) = &self.confirm {
            if !right.is_empty() {
                right.push_str("  |  ");
            }
            if cs.req.secret {
                right.push_str(&format!("secret: {}", "*".repeat(self.secret_buffer.len())));
            } else {
                right.push_str("[D] Decline [O] Once [S] Section [A] Always");
            }
        }
        let left_w = left.width();
        let mut bar = left;
        if !right.is_empty() {
            let pad = (area.width as usize)
                .saturating_sub(left_w + right.width() + 2)
                .max(1);
            bar.push_str(&" ".repeat(pad));
            bar.push_str(&right);
        }
        let status = Paragraph::new(Line::from(Span::styled(bar, Style::default().fg(DIM))));
        f.render_widget(status, area);
    }

    fn render_input(&mut self, f: &mut Frame, area: Rect) {
        let len = self.input.chars().count();
        if self.cursor > len {
            self.cursor = len;
        }
        let byte_idx = self
            .input
            .char_indices()
            .nth(self.cursor)
            .map(|(i, _)| i)
            .unwrap_or(self.input.len());
        let mut shown = String::from("> ");
        shown.push_str(&self.input[..byte_idx]);
        shown.push('█');
        shown.push_str(&self.input[byte_idx..]);
        let input = Paragraph::new(Line::from(Span::raw(shown)))
            .block(Block::default().borders(Borders::ALL).border_style(Style::default().fg(PURPLE)));
        f.render_widget(input, area);
    }

    /// Build the chat text, pre-wrapped to `width` so the scroll
    /// offset is exact (Paragraph is rendered without re-wrapping).
    fn chat_lines(&self, width: usize) -> Vec<Line<'static>> {
        let width = if width == 0 { 1 } else { width };
        let mut lines: Vec<Line<'static>> = Vec::new();
        let user_p = Style::default().fg(BRIGHT).add_modifier(Modifier::BOLD);
        let asst_p = Style::default().fg(BRIGHT);
        let tool_p = Style::default().fg(ORANGE);
        let toolres_p = Style::default().fg(DIM);
        let sys_p = Style::default().fg(ORANGE);

        for m in &self.messages {
            let (prefix, style): (&str, Style) = match m {
                UiMsg::User(_) => ("You: ", user_p),
                UiMsg::Assistant(_) => ("CYNAPSE: ", asst_p),
                UiMsg::Tool(_) => ("🔧 Tool: ", tool_p),
                UiMsg::ToolResult(_) => ("✓ ", toolres_p),
                UiMsg::System(_) => ("● ", sys_p),
            };
            let content = match m {
                UiMsg::User(c) | UiMsg::Assistant(c) | UiMsg::Tool(c) | UiMsg::ToolResult(c) | UiMsg::System(c) => c,
            };
            let prefix_w = prefix.width();
            let body_w = width.saturating_sub(prefix_w).max(1);
            let wrapped = wrap_text(content, body_w);
            if wrapped.is_empty() {
                lines.push(Line::from(vec![Span::styled(prefix.to_string(), style)]));
            } else {
                for (i, w) in wrapped.iter().enumerate() {
                    if i == 0 {
                        lines.push(Line::from(vec![
                            Span::styled(prefix.to_string(), style),
                            Span::styled(w.clone(), style),
                        ]));
                    } else {
                        lines.push(Line::from(vec![Span::styled(w.clone(), style)]));
                    }
                }
            }
            lines.push(Line::from(""));
            lines.push(Line::from(""));
        }

        if self.busy {
            if !self.streaming.is_empty() {
                let body_w = width.saturating_sub("CYNAPSE: ".width()).max(1);
                let wrapped = wrap_text(&self.streaming, body_w);
                for (i, w) in wrapped.iter().enumerate() {
                    if i == 0 {
                        lines.push(Line::from(vec![
                            Span::styled("CYNAPSE: ", asst_p),
                            Span::styled(w.clone(), asst_p),
                        ]));
                    } else {
                        lines.push(Line::from(vec![Span::styled(w.clone(), asst_p)]));
                    }
                }
            } else {
                let frame = SPINNER[self.spinner % SPINNER.len()];
                lines.push(Line::from(Span::styled(
                    format!("  {frame} thinking..."),
                    Style::default().fg(ORANGE),
                )));
            }
            lines.push(Line::from(""));
            lines.push(Line::from(""));
        }

        lines
    }
}

// ─── Word wrap (exact, pre-render) ──────────────────────────────────────────

/// Wrap `s` into lines each of display width `<= width`, breaking on
/// whitespace and hard-breaking over-long words. Used to pre-wrap the
/// chat text so the Paragraph scroll offset is exact.
fn wrap_text(s: &str, width: usize) -> Vec<String> {
    if width == 0 || s.is_empty() {
        return if s.is_empty() { vec![String::new()] } else { Vec::new() };
    }
    let mut out: Vec<String> = Vec::new();
    let mut line = String::new();
    let mut line_w = 0usize;

    for word in s.split_inclusive(char::is_whitespace) {
        let word_w = word.width();
        if line_w + word_w <= width {
            line.push_str(word);
            line_w += word_w;
        } else if line_w == 0 {
            // The word alone exceeds the width: hard-split it.
            let mut cur = String::new();
            let mut cur_w = 0usize;
            for ch in word.chars() {
                let cw = ch.to_string().width();
                if cur_w + cw > width && !cur.is_empty() {
                    out.push(std::mem::take(&mut cur));
                    cur_w = 0;
                }
                cur.push(ch);
                cur_w += cw;
            }
            if !cur.is_empty() {
                out.push(cur);
            }
        } else {
            out.push(std::mem::take(&mut line));
            line.push_str(word);
            line_w = word_w;
        }
    }
    if !line.is_empty() {
        out.push(line);
    }
    if out.is_empty() {
        out.push(String::new());
    }
    out
}

// ─── Bootstrap ──────────────────────────────────────────────────────────────

/// Resolve the effective config: cwd `config.yaml`, then
/// `~/.cynapse/config.yaml` (the Go home config), then defaults.
fn resolve_config() -> Result<Config> {
    if std::path::Path::new("config.yaml").exists() {
        return cynapse_core::config::load(std::path::Path::new("config.yaml"));
    }
    if let Ok(home) = std::env::var("HOME") {
        let go_path = std::path::PathBuf::from(home).join(".cynapse").join("config.yaml");
        if go_path.exists() {
            return cynapse_core::config::load(&go_path);
        }
    }
    Ok(Config::default())
}

fn allowlist_path() -> std::path::PathBuf {
    if let Ok(home) = std::env::var("HOME") {
        std::path::PathBuf::from(home).join(".cynapse").join("allowlist")
    } else {
        std::path::PathBuf::from(".cynapse_allowlist")
    }
}

/// Assemble the Agent from config, exactly like `cmd/cynapse/main.go`
/// (device id, persona, sessions, resolver with allowlist + TUI
/// prompter, effective approval/net policies, tools profile).
fn build_agent(
    session_key: Option<&str>,
    prompter: TuiPrompter,
) -> Result<(Arc<Agent>, Config, Arc<Allowlist>, Arc<dyn llm::LlmClient>)> {
    let cfg = resolve_config()?;
    let device_id = session_key
        .filter(|s| !s.is_empty())
        .unwrap_or("cynapse_tui_01")
        .to_string();

    std::fs::create_dir_all(&cfg.tools.work_dir).ok();
    std::fs::create_dir_all(&cfg.models.models_dir).ok();

    let client = llm::new(&cfg.llm)?;

    let persona = Arc::new(Persona::new(
        &device_id,
        std::path::Path::new(&cfg.memory.persona_path),
        std::path::Path::new(&cfg.memory.defaults_path),
        std::path::Path::new(&cfg.memory.dendrite_db_path),
    )?);
    let sessions = Arc::new(Manager::new_with_mode(&cfg.memory.sessions_path, cfg.session_file_mode())?);

    let allowlist = Arc::new(Allowlist::load(&allowlist_path())?);
    let section = Arc::new(Section::new(&format!("agent:{device_id}")));
    let resolver = Arc::new(Resolver {
        allowlist: Some(allowlist.clone()),
        section: Some(section),
        prompter: Some(Arc::new(prompter)),
    });

    let approval_policy = match cfg.effective_approval_policy() {
        "trust-local" => approval::trust_local_policy(),
        "strict" => approval::Policy {
            prompt_at: approval::Severity::Info,
            deny_at: approval::Severity::Danger,
        },
        _ => approval::default_policy(),
    };
    let net_policy = match cfg.effective_net_policy() {
        cynapse_core::config::NetPolicy::LocalDev => netguard::local_dev_policy(),
        _ => netguard::secure_default(),
    };

    let tools = build_profile(
        &cfg.tools.profile,
        &cfg.tools.work_dir,
        cfg.tools.timeout_seconds,
        persona.clone(),
        approval_policy,
        net_policy,
        Some(resolver),
    );

    let agent = Arc::new(Agent::new(
        device_id,
        client.clone(),
        persona,
        sessions,
        tools,
        cfg.clone(),
    ));
    Ok((agent, cfg, allowlist, client))
}

// ─── Run loop ───────────────────────────────────────────────────────────────

async fn recv_opt<T>(
    rx: &mut Option<tokio::sync::mpsc::UnboundedReceiver<T>>,
) -> Option<Option<T>> {
    match rx {
        Some(r) => Some(r.recv().await),
        None => std::future::pending().await,
    }
}

/// Entrypoint for the interactive chat TUI.
///
/// `session_key` selects which persisted session to open ("" = new,
/// defaulting to the Go device id `cynapse_tui_01`).
pub async fn run(session_key: Option<String>) -> Result<()> {
    let (prompter, confirm_rx) = new_prompter();
    let (agent, cfg, allowlist, client) = build_agent(session_key.as_deref(), prompter)?;
    run_with(agent, cfg, allowlist, client, confirm_rx).await
}

async fn run_with(
    agent: Arc<Agent>,
    cfg: Config,
    allowlist: Arc<Allowlist>,
    llm_client: Arc<dyn llm::LlmClient>,
    confirm_rx: tokio::sync::mpsc::UnboundedReceiver<ConfirmMsg>,
) -> Result<()> {
    enable_raw_mode().context("enabling raw mode")?;
    let mut stdout = std::io::stdout();
    execute!(stdout, EnterAlternateScreen).context("entering alternate screen")?;
    let backend = CrosstermBackend::new(stdout);
    let mut terminal = Terminal::new(backend).context("creating terminal")?;
    terminal.hide_cursor().ok();

    let result = run_loop(&mut terminal, agent, cfg, allowlist, llm_client, confirm_rx).await;

    terminal.show_cursor().ok();
    disable_raw_mode().ok();
    execute!(terminal.backend_mut(), LeaveAlternateScreen).ok();
    result
}

async fn run_loop<B: ratatui::backend::Backend>(
    terminal: &mut Terminal<B>,
    agent: Arc<Agent>,
    cfg: Config,
    allowlist: Arc<Allowlist>,
    llm_client: Arc<dyn llm::LlmClient>,
    confirm_rx: tokio::sync::mpsc::UnboundedReceiver<ConfirmMsg>,
) -> Result<()> {
    let (events_tx, events_rx) = tokio::sync::mpsc::unbounded_channel::<Event>();
    {
        let tx = events_tx.clone();
        std::thread::spawn(move || loop {
            match crossterm::event::read() {
                Ok(ev) => {
                    if tx.send(ev).is_err() {
                        break;
                    }
                }
                Err(_) => break,
            }
        });
    }

    let mut app = App::new(agent, cfg, allowlist, llm_client, events_rx, confirm_rx);
    let mut tick = tokio::time::interval(Duration::from_millis(100));

    loop {
        terminal
            .draw(|f| app.draw(f))
            .map_err(|e| anyhow!("draw failed: {e}"))?;
        if app.quit {
            break;
        }
        tokio::select! {
            _ = tick.tick() => {
                app.on_tick();
            }
            ev = app.events_rx.recv() => match ev {
                Some(ev) => {
                    if app.on_event(ev).await? {
                        break;
                    }
                }
                None => break,
            },
            cmsg = app.confirm_rx.recv() => match cmsg {
                Some(c) => app.on_confirm_request(c),
                None => {}
            },
            chunk = recv_opt(&mut app.chunks) => match chunk {
                Some(Some(c)) => app.on_chunk(&c),
                Some(None) => app.finalize_stream(),
                None => {}
            },
            err = recv_opt(&mut app.errors) => match err {
                Some(Some(e)) => app.on_stream_error(e),
                _ => {}
            },
        }
    }
    Ok(())
}

// ─── Tests ──────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn wrap_text_breaks_on_words() {
        let out = wrap_text("hello world foo", 10);
        assert_eq!(out, vec!["hello ", "world foo"]);
    }

    #[test]
    fn wrap_text_hard_splits_long_words() {
        let out = wrap_text("abcdefghijklmnop", 6);
        assert_eq!(out, vec!["abcdef", "ghijkl", "mnop"]);
    }

    #[test]
    fn wrap_text_empty_is_single_line() {
        assert_eq!(wrap_text("", 10), vec![String::new()]);
        assert!(wrap_text("x", 0).is_empty() || wrap_text("x", 0) == vec![String::new()]);
    }

    #[test]
    fn confirm_card_hides_always_for_sensitive() {
        let mut req = confirm::Request {
            kind: "sudo".into(),
            title: "Password?".into(),
            detail: "sudo -S ls".into(),
            options: Default::default(),
            secret: true,
            prompt: "Password:".into(),
            rule_key: "sudo:ls".into(),
            scope: String::new(),
        };
        let card = format_confirm_card(&req);
        assert!(card.contains("D) Decline"));
        assert!(card.contains("O) Allow once"));
        assert!(card.contains("S) Allow this section"));
        assert!(!card.contains("A) Always allow"));
        req.kind = "bash".into();
        req.secret = false;
        let card2 = format_confirm_card(&req);
        assert!(card2.contains("A) Always allow"));
    }

    #[test]
    fn key_mapping_covers_aliases() {
        assert_eq!(key_to_decision('D'), Some(Decision::Decline));
        assert_eq!(key_to_decision('n'), Some(Decision::Decline));
        assert_eq!(key_to_decision('y'), Some(Decision::AllowOnce));
        assert_eq!(key_to_decision('S'), Some(Decision::AllowSection));
        assert_eq!(key_to_decision('a'), Some(Decision::AllowAlways));
        assert_eq!(key_to_decision('x'), None);
    }

    #[test]
    fn resolved_echo_flags_sensitive_always() {
        let mut req = confirm::Request {
            kind: "sudo".into(),
            title: "t".into(),
            detail: String::new(),
            options: Default::default(),
            secret: true,
            prompt: String::new(),
            rule_key: "sudo:x".into(),
            scope: String::new(),
        };
        let msg = resolved_echo('a', &req);
        assert!(msg.contains("sensitive"));
        req.kind = "bash".into();
        req.secret = false;
        let msg2 = resolved_echo('a', &req);
        assert!(msg2.contains("always allowed"));
    }
}
