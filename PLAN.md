# cynapse-rs — Rust Rewrite of Cynapse (Detailed Plan)

Status: **DRAFT — awaiting user approval before any code is written.**
Date: 2026-08-04

---

## 0. Goal & Non-Goals

**Goal:** Recreate the cynapse AI agent (currently Go + Bubble Tea at
`/home/xander/Documents/portfolio/cynapse/`) as a Rust workspace, architected the
way jcode (`/home/xander/Documents/reference/jcode/`) is, so it is:

- **Fast** to start and render (target: sub-50ms first frame; streaming never
  blocks the UI).
- **Lightweight** — minimal dependency tree, low RSS. No heavy optional stacks
  compiled in unless requested.
- **A better TUI** than the current Bubble Tea layout: jcode-style layout with a
  proper input box, streaming buffer, status bar, memory panel, and a
  session/memory menu — not the current "type + enter" hero screen.
- **Feature-compatible at v1** with the current cynapse for the core daily
  workflow (chat, DENDRITE memory, sessions, tools, safety stack, Ollama).

**Preservation requirement (CRITICAL):** the live DENDRITE graph data must
survive and keep working. Location: `/home/xander/Documents/portfolio/cynapse/data/dendrite.db`
(8 nodes: identity, user, agents, soul, tools, memory_notes, id, heartbeat),
plus sessions JSONL, persona markdown files, and `~/.cynapse/config.yaml`.
The plan below keeps those files byte-compatible — the Rust binary reads/writes
the **same** paths and **same** on-disk formats, so no migration is needed and
the two implementations can be swapped freely.

**Non-goals for v1** (explicitly deferred to v2+):
- Local model registry + HuggingFace downloads (`cynapse model ...`)
- MCP client
- Synapses
- Local HTTP + D3 graph explorer API server
- Local ONNX embeddings (jcode-embedding / tract) — designed in as an optional
  feature flag from the start, but not compiled by default.
- Multi-provider breadth: v1 ships Ollama + OpenAI-compatible (SSE streaming)
  + Anthropic-style SSE (kept because the wire logic already exists in the Go
  source); Gemini/local/leafcutter providers are deferred.

---

## 0.5. Jcode reference architecture (what we copy, what we leave)

Jcode (read via subagent + manual inspection; full readme at
`/home/xander/Documents/reference/jcode/README.md`, ~880 lines) is a single
Rust binary organized as an 80+-crate workspace (`Cargo.toml` workspace with
~80 members under `crates/`). Key observations:

**Confirmed via subagent reads + manual inspection:**

- **TUI stack:** `ratatui 0.30` + `crossterm 0.29` (the de-facto Rust combo).
  Not custom. Same stack jcode uses — we match.
- **Foundation crate:** `jcode-base` — described in its lib.rs as "downward-
  closed set of modules that the upper server/tool/agent layer depends on:
  provider, auth, config, session, message, memory, telemetry." Our `cynapse-
  core` mirrors this pattern.
- **App core:** `jcode-app-core/src/agent/` is split into 15 focused files
  (compaction, environment, inline_tail, interrupts, messages, prompting,
  provider, response_recovery, status, streaming, tools, turn_execution,
  turn_loops, turn_streaming_mpsc, utils). Lesson: the agent IS a directory
  of cooperating modules, not one file.
- **Tool abstraction:** `async_trait`-based Tool trait, `ToolOutput { output,
  title, metadata, images }`. Image data is base64 inline. Tools are
  registered into a manager; the agent invokes by name.
- **Streaming:** the agent reads from a `tokio::sync::mpsc::Receiver<StreamItem>`
  where `StreamItem` is an enum (`Text(String) | ToolCalls(Vec<ToolCall>) | Done`).
  Cleaner than Go's `(<-chan string, <-chan error)` — we adopt the enum pattern.
- **Memory:** jcode has its own `MemoryGraph` with `Edge`, `EdgeKind`,
  `GRAPH_VERSION`. Closer to DENDRITE than I initially thought, but DENDRITE
  is more sophisticated (wiki-links, placeholder auto-wiring, persona
  integration, stopword filtering, type priorities). **Decision: port
  DENDRITE verbatim; do NOT copy jcode's MemoryGraph.**
- **Compaction:** `jcode-compaction-core` with `DEFAULT_TOKEN_BUDGET=200_000`,
  `COMPACTION_THRESHOLD=0.80`. We use Cynapse's smaller 4096/6000 model
  because that's what DENDRITE assumes; jcode's 200k is Claude-specific.
- **Provider crates:** 18+ providers (`provider-anthropic`, `provider-openai`,
  `provider-gemini`, `provider-bedrock`, `provider-copilot`, etc.) all behind
  one trait in `provider-core`. The pattern is: one provider = one crate.
  **We adopt this with a feature flag per provider** (see §2).
- **CLI:** 30+ subcommands under `src/cli/commands/`. Way more than we need.
  We start with 4-5 (chat, config, memory, version, — model/synapse stubs).
- **Workspace `[profile.release]`** tuned: `opt-level=1, debug=0, lto=thin`,
  plus per-crate `opt-level=3` overrides for hot TUI crates in dev builds.
  We copy this pattern.

**What we deliberately leave behind:**
- jcode-desktop2 (Electron/Tauri shell) — out of scope.
- jcode-telemetry-worker + telemetry crates — out of scope for v1.
- jcode-selfdev-types — internal dev workflow, not user-facing.
- jcode-ios / sdk — platform-specific, out of scope.
- jcode's swarm/multi-agent system — far beyond Cynapse's v1 scope.
- jcode's harness API + TypeScript SDK — server-mode feature, deferred.

**Architectural pattern to mirror:** the monorepo of small crates with
clear layering (`base` → `app-core` → `tui`). Even though we use 3 crates
not 80, the *pattern* is what matters: foundation depends on nothing,
orchestration depends on foundation, presentation depends on both.

---

## 1. Decisions (user-confirmed)

1. **Location:** new dir `/home/xander/Documents/portfolio/cynapse-rs/`. The Go
   repo stays untouched as reference + safety net.
2. **Crate architecture:** Lean 3-crate workspace (mirrors jcode's layering,
   not its 80-crate sprawl):
   - root `cynapse` crate — CLI parsing + `main()`, re-exports the core.
   - `crates/cynapse-core` — all non-presentation logic (config, dendrite,
     session, agent, providers, tools, safety stack).
   - `crates/cynapse-tui` — ratatui presentation layer.
3. **V1 scope:** Core + DENDRITE (see §0).
4. **Semantic memory:** deferred; v1 = FTS5 lexical + graph recall.

---

## 2. Workspace Layout

```
cynapse-rs/
├── Cargo.toml              # [workspace] + shared profile settings
├── rust-toolchain.toml     # pinned stable toolchain (edition 2024)
├── PLAN.md                 # this file
├── src/                    # root binary crate (cli + main)
│   ├── main.rs
│   └── cli.rs              # arg parsing + dispatch
├── crates/
│   ├── cynapse-core/       # lib "cynapse_core"
│   │   └── src/
│   │       ├── lib.rs
│   │       ├── config.rs         # YAML config load/save
│   │       ├── dendrite.rs       # in-memory graph + wikilink/tag parsing
│   │       ├── dendrite_store.rs # rusqlite persistence + FTS5
│   │       ├── dendrite_context.rs # system-prompt assembler
│   │       ├── session.rs        # JSONL session manager
│   │       ├── compressor.rs     # context → DENDRITE compaction
│   │       ├── persona.rs        # persona files + SaveFact/AppendDailyLog
│   │       ├── agent.rs          # tool loop + circuit breaker + curator
│   │       ├── llm/              # provider traits + impls
│   │       │   ├── mod.rs        # Message/Role/ToolCall/ToolSchema/Request
│   │       │   ├── ollama.rs     # NDJSON streaming
│   │       │   └── openai.rs     # SSE streaming (incl. anthropic-compatible)
│   │       ├── tools.rs          # Tool/Registry/BuildProfile + handlers
│   │       ├── approval.rs       # bash severity rules + Policy
│   │       ├── confirm.rs        # Decision/Request/Allowlist/Resolver
│   │       ├── netguard.rs       # SSRF policy
│   │       ├── redact.rs         # secret regex redaction
│   │       └── attachments.rs    # file → Attachment
│   └── cynapse-tui/         # lib "cynapse_tui"
│       └── src/
│           ├── lib.rs
│           ├── app.rs            # main loop + state machine
│           ├── input.rs          # text input widget
│           ├── messages.rs       # scrollback buffer
│           ├── status.rs         # status bar
│           ├── menus.rs          # model/session/memory menus
│           ├── theme.rs          # cynapse color palette
│           └── stream.rs         # streaming buffer bridging agent→UI
```

Feature flags on `cynapse-core` (forwarded from root):
- `default = ["ollama", "openai"]`
- `embeddings` (future) — gate for jcode-style local embeddings
- `pdf` — enables `pdftotext` subprocess path in attachments (already exec-based, cheap)
- `test-support` — pub test helpers (mirrors jcode's pattern)

---

## 3. Dependencies (minimal, justified)

Root `cynapse` crate:
- `clap` (derive) — CLI (jcode uses clap; cynapse currently hand-rolls).
- `anyhow` — error handling.
- `tokio` — async runtime (jcode uses multi-thread tokio).

`cynapse-core`:
- `tokio` (rt-multi-thread, fs, io-std, io-util, macros, net, process, sync, time, signal)
- `serde` + `serde_json` (serialization; matches Go JSON usage)
- `serde_yaml` (config.yaml — replaces gopkg.in/yaml.v3)
- `rusqlite` with `bundled` feature (SQLite + FTS5 compiled in; replaces mattn/go-sqlite3)
- `reqwest` (default-features=false; rustls-tls; HTTP to Ollama/OpenAI) — or lighter
  `ureq`/`hyper`. **Decision point:** reqwest matches jcode; ureq is smaller.
  Chosen: **reqwest with rustls** for SSE streaming ease (see §10).
- `regex`, `chrono` (with serde), `dirs`, `rand`, `thiserror` (or manual errors).

`cynapse-tui`:
- `ratatui` (0.30, jcode's choice) + `crossterm` (0.29, event-stream feature)
- `unicode-width` (text width), `tokio` (re-export), `anyhow`

**Explicitly avoided:** mattn/go-sqlite3 analogues that link system sqlite (use
`bundled`), Bubble Tea/Lipgloss (replaced by ratatui), heavy image libs.

---

## 4. DENDRITE — the critical port (byte-compatible with live data)

### 4.1 `dendrite.rs` — in-memory graph (verbatim port)

Port `internal/memory/dendrite.go` 1:1. I read this file verbatim. Key
semantics that MUST be preserved exactly:

**`Upsert(id, title, content, node_type, tags) -> &Node`** — this is the
load-bearing algorithm. The Go code does ALL of the following under one mutex:
1. `now = unix_seconds()`
2. `links = parse_links(content)` (always; tag/user-supplied tags ignored if
   user passed `nil` — then `tags = parse_tags(content)`)
3. **Backlink cleanup**: if id already exists, for each `old.links[i]`,
   remove `id` from `target.backlinks`.
4. Create or update node in-place; preserve `created_at` on update.
5. Update fields: title, content, type, tags, links, updated_at = now.
6. **Backlink wiring**: for each new link target:
   - If target doesn't exist: create PLACEHOLDER node with type `Custom`,
     title = id, created_at = now, updated_at = now.
   - Append `id` to `target.backlinks` if not already present (set semantics).
7. Spawn all `on_change` callbacks as goroutines (`go fn()`). In Rust: use
   `tokio::spawn` or `std::thread::spawn` — pick one and document.
8. Return `&node`.

**`Neighbors(id)`** — 1-hop: links + backlinks, deduplicated, original node excluded.

**`Neighbors2Hop(id)`** — explicit 2-hop (links ∪ backlinks of each 1-hop neighbor). Implemented as two nested loops (not BFS) for predictability.

**`Neighbors3Hop(id)`** — proper BFS with depth ≤ 3, queue of `(id, depth)`.

**`Search(query)`** — case-insensitive substring on title OR content, or
case-insensitive tag membership (`contains_str_fold`). Returns ALL matches
(no limit) — scoring happens in `dendrite_context::score`.

**`ByTag(tag)`** — case-insensitive tag membership.

**Parsing helpers (private):**
- `link_pattern = r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]"` — captures target before
  optional `|display`, calls `to_node_id` (trim → lowercase → spaces→`_`).
- `tag_pattern = r"#([A-Za-z0-9_-]+)"`.
- Both maintain insertion order while deduplicating.

**Concurrency:** Go uses `sync.RWMutex`. In Rust use `std::sync::RwLock<NodeMap>`
(read-heavy) or `parking_lot::RwLock` (faster, no poison). Decision:
**`parking_lot`** — single small dep, well-known, faster under contention.

**`OnChange(fn)`** registration model: list of boxed `Fn() + Send + Sync`.
Notify spawns each asynchronously to avoid blocking the writer.

Below is the data model:

```rust
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub enum NodeType { Identity, Person, Concept, Project, Event, Memory, Custom }
// serde = lowercase strings: identity|person|concept|project|event|memory|custom

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Node {
    pub id: String,
    pub title: String,
    pub content: String,
    pub r#type: NodeType,
    pub tags: Vec<String>,
    pub links: Vec<String>,      // outgoing [[links]], lowercase_underscore ids
    pub backlinks: Vec<String>,  // auto-maintained
    pub created_at: i64,         // unix seconds (Go time.Now().Unix())
    pub updated_at: i64,
}
```

- `Dendrite { nodes: HashMap<String, Node>, onChange: Vec<Box<dyn Fn() + Send>> }`
  — `OnChange(fn)`, `notify()` (spawn callback off the writer, matching Go).
- Parsing regexes (port verbatim):
  - links: `\[\[([^\]|]+)(?:\|[^\]]+)?\]\]` → `toNodeID` (trim, lowercase,
    spaces→underscore)
  - tags: `#([A-Za-z0-9_-]+)`
- Operations (all mutex-guarded — use `std::sync::Mutex` + parking_lot? **Decision:
  `parking_lot::Mutex`** (lighter, no poison) — or std. Choose **std Mutex** to
  keep deps minimal): `Upsert(id,title,content,node_type,tags)` — recomputes
  links from content if tags not given, rewires backlinks (removes old, adds
  new, creates placeholder nodes for missing targets), updates UpdatedAt.
  `Delete`, `Get`, `All` (sorted by UpdatedAt desc), `Neighbors`,
  `Neighbors2Hop`, `Neighbors3Hop` (BFS, depth 3), `Search` (case-insensitive
  substring over title/content/tags), `ByTag`, `Len`.

### 4.2 `dendrite_store.rs` — SQLite persistence (CRITICAL: byte-compatible)

Port `internal/memory/dendrite_store.go`. Open with **identical** pragmas:
- `rusqlite::Connection::open(path)` then:
  - `PRAGMA journal_mode=WAL;`
  - `PRAGMA busy_timeout=5000;`
  - single connection (matches `SetMaxOpenConns(1)`); wrap in `Arc<Mutex<>>`.

`migrate()` executes the **exact same DDL** (so an existing DB with the old
schema opens cleanly):

```sql
CREATE TABLE IF NOT EXISTS dendrite_nodes (
    id         TEXT PRIMARY KEY,
    title      TEXT NOT NULL,
    content    TEXT NOT NULL DEFAULT '',
    type       TEXT NOT NULL DEFAULT 'custom',
    tags       TEXT NOT NULL DEFAULT '[]',
    links      TEXT NOT NULL DEFAULT '[]',
    backlinks  TEXT NOT NULL DEFAULT '[]',
    created_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_dendrite_updated ON dendrite_nodes(updated_at DESC);
CREATE VIRTUAL TABLE IF NOT EXISTS dendrite_fts USING fts5(
    id UNINDEXED, title, content, tags, tokenize='porter unicode61');
CREATE TRIGGER IF NOT EXISTS dendrite_nodes_ai AFTER INSERT ON dendrite_nodes
    BEGIN INSERT INTO dendrite_fts(id,title,content,tags)
    VALUES (new.id,new.title,new.content,new.tags); END;
CREATE TRIGGER IF NOT EXISTS dendrite_nodes_au AFTER UPDATE ON dendrite_nodes
    BEGIN DELETE FROM dendrite_fts WHERE id=old.id;
    INSERT INTO dendrite_fts(id,title,content,tags)
    VALUES (new.id,new.title,new.content,new.tags); END;
CREATE TRIGGER IF NOT EXISTS dendrite_nodes_ad AFTER DELETE ON dendrite_nodes
    BEGIN DELETE FROM dendrite_fts WHERE id=old.id; END;
```

- FTS5-detection fallback: if `CREATE VIRTUAL TABLE ... fts5` errors, create
  `dendrite_fts_fallback` and use LIKE search (port `hasFTS5` bool). rusqlite
  bundled ships FTS5, but keep the fallback for parity.
- `Save(node)` — transaction: `INSERT ... ON CONFLICT(id) DO UPDATE SET ...`
  (same column set; **note: Go does NOT update created_at on conflict** — match
  that exactly). Plus fallback FTS sync when !hasFTS5.
- `Delete(id)`, `LoadAll(kg)` (hydrate directly into node map, skip backlink
  recompute — backlinks are stored), `FTSSearch(query, limit)` (`WHERE
  dendrite_fts MATCH ? ORDER BY rank LIMIT ?`; fallback `LIKE`), `Close`.
- **JSON columns:** tags/links/backlinks stored as JSON arrays (`serde_json`).

### 4.3 `dendrite_context.rs` — system-prompt assembler (verbatim port)

Port `internal/memory/dendrite_context.go` — exact algorithm. I read this file
verbatim; here is the exact behavior to mirror:

**Constants (do not change):**
- `default_max_tokens = 6000`
- `core_node_budget = 0.40` (40% of token budget for core identity)
- `context_node_budget = 0.60` (60% for conversation-relevant)
- `cache_ttl = 5 minutes`

**`BuildPrompt(user_message, max_tokens) -> String` cache semantics (CRITICAL):**
- If `user_message` is non-empty → ALWAYS recompute, mark dirty=false, return.
- Else if `!dirty && now - cached_at < TTL && cached_prompt != ""` → return cached.
- Else: set dirty=false BEFORE calling `assemble`, compute, cache, return.
- Rationale: dirty=false is set before assemble so concurrent OnChange
  goroutines trigger fresh recompute on the NEXT call, not the current one.

**`assemble(user_message, max_tokens)`:**
1. Compute `core_budget = (max_tokens as f32 * 0.40) as i32`.
2. For each core ID in `["identity", "soul", "agents", "tools"]` (fixed order):
   - Format `part = "## {title}\n\n{content}"`
   - `cost = part.len() / 4` (`estimate_tokens`, chars→tokens)
   - If `used + cost > core_budget` → break
   - Append, add to `used`.
3. If user_message is non-empty:
   - Call `find_relevant(user_message)` (see below).
   - Call `score(candidates, user_message)` → sort desc by score.
   - For each scored node: skip if in core_ids; format part; break on token cap.
4. Else (no user message): walk `graph.all()` (sorted UpdatedAt desc), skip
   core IDs, append parts until token cap.
5. Join with `"\n\n---\n\n"`. Return `""` if no parts.

**`find_relevant(user_message) -> Vec<&Node>` (3-tier union, dedup by id):**
1. FTS5 top-20 → for each id, add node + 1-hop neighbors (`Neighbors`).
2. Full-query `Search(user_message)` → add node + 1-hop neighbors.
3. Word-by-word: `words = user_message.to_lowercase().split_whitespace()`.
   For each word with `len >= 3` and `!is_stop_word(word)`:
   - `Search(word)` → add node + 1-hop neighbors.
   - `ByTag(word)` → add node (no neighbors for tag matches).

**`score(nodes, query) -> Vec<ScoredNode>` (sort desc):**
```
score = 0.0
if title_lower.contains(query_lower)  →  +15.0
score += content_lower.matches(query_lower).count() as f64 * 2.0
// Recency: linear decay over 7 days, max +5
age_days = (now - updated_at) / 86400
if age_days < 7.0  →  + (7.0 - age_days) * (5.0 / 7.0)
// Connectivity
score += (links.len() + backlinks.len()) as f64 * 0.3
// Node type priority
match node_type {
  Identity → +10
  Person   → +5
  Project  → +3
  _        → +0
}
```

**Stopword list (port VERBATIM from `dendrite_context.go:200-223`):**
~95 common English stopwords. A test fixture must encode the exact set so a
missing word fails the test. Don't paraphrase.

**`estimate_tokens(text) = text.len() / 4` (chars, not bytes — use `.chars().count()` in Rust).**

**Verification step (build-check):** after milestone 2, run a Rust test that
loads the real `/home/xander/Documents/portfolio/cynapse/data/dendrite.db` and
asserts `BuildPrompt` output equals the Go implementation's output for a fixed
message. This is how we prove DENDRITE parity without running Go.

---

## 5. Session Manager (JSONL, byte-compatible)

Port `internal/session/manager.go`:
- `Entry { role: Role, content: String, tool_call_id: Option<String>,
  tool_calls: Vec<ToolCall>, images: Vec<String>, attachments: Vec<Attachment>,
  ts: i64 }` — serde `rename_all` to match JSON keys: `role`, `content`,
  `tool_call_id`, `tool_calls`, `images`, `attachments`, `ts`.
- JSONL file `<base>/<sanitized_key>.jsonl` (sanitize: alnum + `-` `_`, else `_`).
- `Append` opens with `O_APPEND|O_CREATE|O_WRONLY`, mode 0644 (or 0600 in
  strict security mode), writes `json + '\n'` (single write).
- `Recent(n)`, `Entries()` (snapshot clone), `Replace` (temp `.replace` file +
  rename), `Compact(keep)` (temp `.compacting` + fsync + rename), `Len`.
- `Manager` lazily loads per key; in-memory map + RwLock.

This keeps `data/sessions/cynapse_tui_01.jsonl` readable/writable identically.

---

## 6. Config (YAML, byte-compatible)

Port `internal/config/config.go` 1:1 with serde (serde_yaml). All fields with
`yaml:"..."` tags:
- `gateway: {address, auth_token}`
- `llm: {provider, model, anthropic_key, openai_key, gemini_key,
  openai_base_url, ollama_base_url, llama_server_path, leafcutter_path,
  local_gpu_layers, local_context_size, local_threads, models_dir, max_tokens,
  temperature, max_retries}`
- `memory: {persona_path, sessions_path, db_path, dendrite_db_path,
  defaults_path, heartbeat_interval_hours, max_session_messages}`
- `tools: {profile, allow, deny, work_dir, timeout_seconds}`
- `mcp: {enabled, servers: [{name, command, args, env}]}` (parsed for compat,
  unused in v1)
- `models: {models_dir, use_ollama, use_llama_server, hf_token}` (parsed,
  mostly unused in v1)
- `security: {mode, redact_secrets: Option<bool>, net_policy, approval_policy}`
- `backup_keep: i32`
- Defaults identical to Go `defaults()` (provider "ollama", model "qwen2.5",
  ollama_base_url http://localhost:11434, max_tokens 4096, temperature 0.7,
  max_retries 3, memory defaults `./data/persona` etc., tools profile
  "standard"/work_dir `./workspace`/timeout 30, mcp enabled true).
- `applyEnv` overrides: ANTHROPIC_API_KEY, OPENAI_API_KEY, OPENAI_BASE_URL,
  GEMINI_API_KEY, OLLAMA_BASE_URL, CYNAPSE_PROVIDER, CYNAPSE_MODEL,
  CYNAPSE_ADDRESS, CYNAPSE_AUTH_TOKEN, HF_TOKEN.
- Helper methods ported: `EffectiveRedaction()`, `EffectiveSecurityMode()`,
  `SessionFileMode()` (0644/0600), `CreateDefault` (0600 file, 0700 dirs).

**Path resolution note:** The Go binary uses `~/.cynapse/` for config
(`getHomeDir()` → `$HOME/.cynapse`), while memory/session paths default to
`./data/...` relative to CWD (that's why the live data lives in the repo's
`data/`). The Rust binary must replicate **exactly** this: config at
`~/.cynapse/config.yaml`, but if `memory.dendrite_db_path` is a relative path,
resolve relative to **CWD** (not config dir). Keep Go's exact semantics.

---

## 7. Persona & Curator

- `persona.rs`: device dir under `memory.persona_path/<device_id>/` containing
  AGENTS.md, USER.md, MEMORY.md, HEARTBEAT.md, SOUL.md, TOOLS.md, IDENTITY.md.
  `SaveFact(fact, tags)` → upsert a DENDRITE node; `AppendDailyLog(entry)` →
  append to today's `DAILYLOG-YYYY-MM-DD.md` (Go behavior: check exact format in
  `memory.go` when porting — mark as a **to-verify-detail**).
- `CompileSystemPrompt(userMsg)` — combines persona MD files + DENDRITE context
  (Go builds persona prompt; confirm exact assembly in `memory.go` — mark
  to-verify).
- `Curator` heartbeat: runs maintenance every `heartbeat_interval_hours`; on
  trigger runs `selfImproveFork`-style LLM review + daily log append. Port from
  `memory.go`/`agent.go`.

**To-verify during implementation** (I have not yet read `internal/memory/memory.go`
in full): exact `SaveFact` node creation, daily-log filename format, and
`CompileSystemPrompt` assembly. These are flagged in the plan so the build step
reads them first.

---

## 8. LLM Providers (wire-compatible)

### 8.1 Shared types (`llm/mod.rs`)

```rust
pub enum Role { System, User, Assistant, Tool }           // serde lowercase
pub struct ToolCall { pub id: String, pub name: String, pub arguments: serde_json::Value }
pub struct ToolSchema { pub name: String, pub description: String, pub parameters: serde_json::Value }
pub struct Attachment { pub r#type: String /*image|text|pdf|binary*/, pub filename: String, pub mime: String, pub content: String }
pub struct Message { role, content, tool_call_id: Option<String>, tool_calls: Vec<ToolCall>, images: Vec<String>, attachments: Vec<Attachment> }
pub struct Request { system_prompt: String, messages: Vec<Message>, tools: Vec<ToolSchema>, max_tokens: i32, temperature: f64 }
pub struct Response { content: String, tool_calls: Vec<ToolCall>, usage: Usage }
pub struct Usage { input_tokens: i32, output_tokens: i32 }

pub trait Provider: Send + Sync {
    fn provider(&self) -> &str;
    async fn chat(&self, req: &Request) -> Result<Response>;
    async fn chat_stream(&self, req: &Request) -> Result<StreamEventStream>;
    // or return (mpsc::Receiver<String>, mpsc::Receiver<Result<(),Error>>) to
    // mirror Go's (<-chan string, <-chan error)
}
```

Streaming interface decision: Go returns `(<-chan string, <-chan error)` with a
special final chunk = JSON `[]ToolCall` to signal tool calls. Port this
**exactly** so the agent loop logic is a 1:1 translation: the stream yields text
chunks and one terminal JSON tool-call chunk. (Alternative: proper enum
`StreamItem::Text(String) | StreamItem::ToolCalls(Vec<ToolCall>) | Done` — cleaner
Rust; keep the Go channel shape inside providers, expose the enum to the agent.)

### 8.2 Ollama (NDJSON streaming) — port `ollamaClient`

- `POST {base}/api/chat`, body:
  ```json
  { "model": ..., "messages": [{role, content, images?}], "tools": [...],
    "stream": true, "options": { "num_predict": max_tokens, "temperature": ... } }
  ```
- System prompt → prepended `{"role":"system"}` message (Go does this).
- Attachments: image→`images[]`; text/pdf→inline `\n\n[Attachment: name]\n` + content.
- Tool schema shape: OpenAI `{"type":"function","function":{name,description,parameters}}`.
- Stream: NDJSON lines; each `{"message":{"content":"...","tool_calls":[...]},"done":bool}`;
  content → text chunk; `tool_calls` accumulated; on `done:true` emit JSON
  `[]ToolCall` chunk and close.
- Non-stream `chat` returns `prompt_eval_count`/`eval_count` as usage.
- `ListOllamaModels(base_url)` → `GET /api/tags` for the TUI Models menu.

### 8.3 OpenAI-compatible (SSE streaming) — port `openaiClient`

- `POST {base}/chat/completions` with `Authorization: Bearer`, `stream:true`,
  `Accept: text/event-stream`.
- Parse `data: {...}` lines; `[DONE]` terminator; accumulate `delta.tool_calls`
  by index (id/name/arguments); emit text chunks; end with JSON `[]ToolCall`
  chunk if tool calls were seen.
- Also used for Anthropic-shaped OpenAI endpoints? — No: the Go code has a
  separate `anthropicClient` (messages API, `x-api-key` +
  `anthropic-version: 2023-06-01`, content blocks + `partial_json` deltas).
  **Scope call:** v1 ships Ollama + OpenAI-compatible. Keep Anthropic client in
  core but behind a feature flag `anthropic` (off by default) so we don't carry
  dead code — OR include it since it's a direct port. Chosen: **include
  `openai` and `ollama` in default; put `anthropic` behind a feature flag** to
  keep the default dep-free and match "ollama+OpenAI-compatible" scope.

---

## 9. Agent loop, Tools, Safety Stack (ports)

### 9.1 `agent.rs`

- `maxToolIterations = 10`.
- `CircuitBreaker`: state closed→open(N failures)→half-open(after cooldown)→closed.
  Default `newCircuitBreaker(3, 30s)`.
- `ProcessMessage` / `ProcessMessageStream`: append user → auto-compress →
  compact if `Len > MaxSessionMessages` (keep last half) → build Request
  (`CompileSystemPrompt`, `Recent(60)`, all tool schemas incl. future MCP) →
  loop: if `!cb.Allow()` error; call provider; success records cb; if no tool
  calls → final; else append assistant ToolCalls msg, execute each tool
  (MCP first, then registry — in v1 registry only), append tool results (redact
  if enabled), repeat.
- Tool-chunk detection (`parseToolCallChunk`): chunk starts with `[` and parses
  as `[]ToolCall` → tool phase (prints `\n[tool] name\n` … `[tool result] name\n`
  to stream) — port verbatim.
- `selfImproveFork`: background 30s-capped LLM JSON decision
  `{save_fact, save_fact_tags, update_user, daily_log}` → `SaveFact` /
  `AppendDailyLog`. Port fence-stripping + `extractJSON` fallback.
- `StartGraphServer` → **deferred** (v2 API server); v1 menu "DENDRITE" shows a
  TUI memory panel instead.

### 9.2 `tools.rs`

- `Tool { schema: ToolSchema, handler: Arc<dyn Fn(Context, serde_json::Value) -> Result<String,String>> }`.
- `Confirmer` trait = `confirm::Resolver::check` — nil Confirmer → auto-decline
  Warn+, auto-reject Danger+.
- `BashTool(work_dir, approval_policy, confirmer)`:
  - `approval::Inspect(cmd).evaluate(policy)`; if denied → BLOCKED message;
    if require_confirm → build `confirm::Request{Kind: bash|sudo,
    Title:"Run shell command?", Detail: cmd, RuleKey: BashRuleKey(cmd),
    Scope:"bash:cmd", Secret: needs_sudo_secret}`; on AllowAlways → remember;
    sudo → `sudo -S -p '' bash -c <trimmed>` with password on stdin.
  - Run `bash -c` with work_dir, 256KB output cap, `(no output)` when empty,
    exit-error formatting.
- `ReadFileTool` / `WriteFileTool` / `ListFilesTool` (path traversal guard
  `resolvePath` — abs join + prefix check).
- `WebFetchTool(net_policy)` — SSRF check via netguard, 20s timeout, 32KB body
  limit, UA `CYNAPSE-Agent/1.0`.
- Memory tools (writeFile/appendLog/search callbacks): `memory_replace`,
  `daily_log_append`, `user_replace`, `soul_replace`, `memory_search`.
- `BuildProfile(profile, work_dir, timeout_sec, approval_policy, net_policy,
  confirm, persona callbacks)` — always registers memory tools + read_file;
  `standard` adds write_file/list_files/web_fetch; `full` adds bash; `minimal`
  = memory tools only. Port the switch verbatim.

### 9.3 `approval.rs`

Port `internal/approval/approval.go`:
- `Severity: None=0, Info=1, Warn=2, Danger=3, Critical=4`.
- Full regex rule table (mkfs, dd-of-dev, chmod-777-root, wipefs, rm-rf-root,
  rm-rf-glob, rm-rf, find-delete, shred-recursive, truncate-target, forkbomb,
  while-true-zombie, curl-pipe-shell, nc-reverse, bash-dev-tcp, ssh-option,
  pip-install, npm-install-global, git-push-force, curl-head, wget-head,
  ssh-no-cmd) — port regexes verbatim.
- `Inspect(raw)` (cleanupShell first: `\\\n`→` `, CRLF→` `, newline→` `,
  collapse fields) → worst severity. `Decision{allow, severity, reason,
  rule_name, require_confirm}`. `Policy{prompt_at, deny_at}` with
  `DefaultPolicy{Warn,Danger}`, `TrustLocalPolicy{Critical+1,Critical}`.
  `Evaluate`: severity ≥ deny → deny; ≥ prompt → allow+confirm; else allow.

### 9.4 `confirm.rs`

Port `internal/confirm/confirm.go`:
- `Decision: Decline|AllowOnce|AllowSection|AllowAlways` (+ shortcuts D/O/S/A).
- `Request{kind, title, detail, options, secret, prompt, rule_key, scope}`;
  `is_sensitive()` kinds `password|sudo|keyring` → no AllowAlways.
- `Allowlist` file `~/.cynapse/allowlist` (one rule per line; comments `#`;
  header written on flush; mode 0600); `Remember/Forget/Snapshot`.
- `Section` per-scope allowed map (`agent:<device>`).
- `Resolver.check`: nil→Decline; allowlist hit→AllowAlways; section hit→
  AllowSection; else Prompter.ask; AllowAlways→Remember; AllowSection→Section.
- `RuleKey` builders: `BashRuleKey` (strip `\\\n`, collapse fields, prefix
  `bash:`), `SSHRuleKey`, `DownloadRuleKey`, `SudoRuleKey`.
- `Prompter` trait: `StdinPrompter` (default; used outside TUI) + TUI message
  bridge (like Go `ConfirmUI`).

### 9.5 `netguard.rs`

Port `internal/netguard/netguard.go`: `Policy{allow_loopback, allow_private,
allow_metadata, allow_non_http, allow_cleartext_http}`; `SecureDefault` (all
false), `LocalDevPolicy` (loopback/private/cleartext true); `Check(url)` —
parse URL, scheme gate, host DNS resolve + per-IP classify (loopback,
link-local, multicast, unspecified, private, metadata 169.254.x.x); reject with
reason. Rust: use `reqwest`'s URL parsing + `tokio::net::lookup_host` (or `dns`
via `std::net::ToSocketAddrs` in spawn_blocking). Keep the "resolve all IPs"
conservative behavior.

### 9.6 `redact.rs`

Port `internal/redact/redact.go` verbatim: full pattern table (OpenAI
sk-(proj-|svca-)?, sk_live_/sk_test_, Anthropic sk-ant-/sk_ant_, AIza, AKIA,
GitHub ghp_/github_pat_/gho_/ghu_/ghs_/ghr_, hf_, xox, Stripe, SG./MG./SK,
PEM headers, Bearer/JWT, long base64 blob ≥40); env assignment regexes;
JSON-key scan; URL query-param scan (`api_key,key,token,...`); never scans
`data:image/*;base64,` ranges. `Mask` keeps head6/tail4, floor 18, preserves
length. `Redact(text)` replaces spans; `JSONRedact` walks JSON.
Rust: `regex::Regex` (compile once with `OnceLock`).

### 9.7 `attachments.rs`

Port `internal/attachments/attachments.go`: type image|text|pdf|binary; image
exts → base64; text list (.txt,.md,.csv,.json,.yaml,.yml,.go,.py,.js,.ts,.html,
.css,.sh,.xml,.log) → raw text; pdf → `pdftotext path -` (exec) else base64
fallback; binary → base64. `FindInWorkspace` candidates (root, uploads/, images/,
documents/), `ListWorkspaceFiles`, `ToImageURL`, `ToText`, `ToMarkdown`.

---

## 10. TUI (`cynapse-tui`) — jcode-inspired redesign

Use **ratatui 0.30 + crossterm 0.29** (jcode's stack). Tokio for the agent
loop; TUI reads events on the main loop, agent runs on a background task
sending chunks over `tokio::sync::mpsc` → `stream.rs`.

**Layout (active chat):**
```
┌─ CYNAPSE ──────────────────────────┬───────────────┐
│  [scrollback: user / assistant /   │ Memory panel:  │
│   tool / system messages]          │ DENDRITE       │
│   ...                              │ nodes list     │
│                                    │ (collapsible)  │
│  spinner / streaming text          │                │
├────────────────────────────────────┴───────────────┤
│  > input  [attachments: file.txt 📎]               │
├────────────────────────────────────────────────────┤
│ Model: qwen3.5:9b │ ⏱ 123ms │ 🪙 456 tok │ ◆ d:... │
└────────────────────────────────────────────────────┘
```

**Screens/modes:**
1. **Idle/hero** — port the ASCII CYNAPSE logo + palette; type to enter.
2. **Chat (default)** — scrollback auto-follow, streaming text inline, spinner
   while thinking, tool cards (`🔧 Tool: bash` + result in dim), system cards
   (`●` orange), confirm cards (D/O/S/A keys, secret buffer masked as `*`).
3. **Menus** (Ctrl+K like Go): Status / Models (Ollama list via
   `ListOllamaModels`) / Memory (DENDRITE panel + search) / Clear / Help / Quit.
4. **Confirm overlay** — when a bash tool needs a decision, render a modal card
   and intercept D/O/S/A; secret mode echoes `*`. Bridges agent thread ↔ TUI via
   a channel pair (port `confirm_ui.go` semantics).

**Input widget:** line editor with left/right cursor, backspace, enter; slash
commands ported: `/attach <file>`, `/attachments`, `/clear-attach`,
`/compress`, `/allowed list|forget <r>|clear` (wired to allowlist snapshot).

**Theme:** exact cynapse palette — purple `#9b59b6`, orange `#e67e22`, bg
`#0a0e14`, dim `#4a5568`, bright `#e4e7eb`; map to ratatui styles.

**Status bar:** `Model: <m> | ⏱ <elapsed> | 🪙 <tokens>` right-aligned like Go.

**Performance habits (jcode):** render only on event / dirty; cap scrollback
re-layout; `CrosstermBackend`; keep event polling on one thread; stream chunks
batched; no allocations in hot render where avoidable. (Optional: precompute
layout in `ratatui::layout`, reuse buffers.)

---

## 11. CLI (root crate)

Port `cmd/cynapse/main.go` + jcode-style clap derive. Binary name `cynapse`:

- no args / unknown → interactive chat (TUI).
- `cynapse version` — `CYNAPSE v2.0.0-beta` (bump to `v3.0.0-rs`? — keep
  `v2.0.0-beta` string for compat; decide at build).
- `cynapse config init|edit|help` — init writes default YAML (0600), edit opens
  `$EDITOR`.
- `cynapse model ...` / `cynapse synapse ...` — **v2** (stub with a clear
  "not yet implemented in the Rust build" message in v1).
- `cynapse update` — **v2** (stub).

Also add (small, jcode-style, cheap): `cynapse memory list|search <q>`
(reads DENDRITE directly) — useful for verifying the DB port without the TUI.

---

## 12. Build & Performance Plan

- **Workspace profile settings** (copy jcode's approach, scaled):
  - `[profile.release] opt-level = 1, debug = 0, codegen-units = 256, incremental = true`
  - `[profile.release-lto] inherits = "release", lto = "thin", codegen-units = 16, incremental = false`
  - `[profile.dev.package.ratatui] opt-level = 3` etc. for the hot TUI crates in
    dev builds (jcode's pattern).
- **Startup:** config load + dendrite open + session open before first frame;
  persona/dendrite hydrate on a spawned task so the first frame is fast.
- **No jemalloc in v1** (Rust's default allocator is fine; revisit if RSS
  matters later). Document the jcode allocator tuning knobs in a README note.
- Feature flags gate optional stacks (embeddings, anthropic, pdf) so the default
  build stays lean (mirrors jcode's `embeddings`/`pdf`/`bedrock` feature
  forwarding).

---

## 13. Testing Strategy

- **Port-parity tests** (unit): dendrite parsing (wikilinks/tags/toNodeID),
  approval regex table (port Go's test cases — there is `tools_test.go`,
  `api_test.go`, `ollama_e2e_test.go`; replicate the pure ones), redact patterns
  (mask/scan), compressor token math, confirm rule-key normalization, netguard
  IP classification.
- **DB compatibility test:** open the **real** `data/dendrite.db`, run
  `LoadAll` + `FTSSearch`, assert node count = 8 and expected IDs present; write
  a node, re-open, confirm persistence + FTS trigger sync.
- **Live smoke test:** run TUI against local Ollama (config points to
  `qwen3.5:9b`) and verify a tool-call turn streams.
- **Compressor test:** feed a long session, assert middle archived into DENDRITE
  with `compaction` tags and handoff message inserted (port `compressor.go`
  logic + tags `compaction`, `compaction-user`, `compaction-tool`,
  `compaction-assistant`).

---

## 14. Milestones (each ends compilable + tested)

1. **Scaffold** — workspace, 3 crates, clap CLI skeleton, config load, feature
   flags, CI-friendly `cargo fmt`/`clippy`.
2. **DENDRITE core** — `dendrite.rs` + `dendrite_store.rs` + `dendrite_context.rs`
   + DB-compat test against live data. **Checkpoint: user can run `cynapse
   memory list` and see the 8 nodes.**
3. **Session + persona + compressor** — JSONL manager, persona file read/write,
   compactor with DENDRITE sink. Parity tests.
4. **LLM + agent** — providers (Ollama + OpenAI), tool loop, circuit breaker,
   selfImproveFork. Test against local Ollama.
5. **Safety stack** — approval/confirm/allowlist/netguard/redact/attachments +
   tools registry + BuildProfile. Port unit tests.
6. **TUI** — ratatui chat screen, streaming, menus, confirm bridge, status bar,
   theme. Interactive smoke test.
7. **Polish** — slash commands, memory panel, profile/feature tuning,
   README, `cargo install` ergonomics.

---

## 15. Out of Scope (v2+)

- `cynapse model search|download|import|remove` (HF registry)
- MCP client + synapse registry
- Local HTTP + D3 graph server (`/api/dendrite` etc.) — replaced by TUI memory panel in v1
- Local ONNX embeddings / semantic memory (`embeddings` feature flag)
- Additional providers (gemini, local llama-server, leafcutter)
- Auto-update

---

## 16. Open Questions for the user (none blocking; defaults chosen)

- Binary version string: keep `v2.0.0-beta` or bump? (default: keep for compat)
- `memory.persona_path` etc. resolved relative to CWD exactly as Go does — confirm
  you want to keep running the Rust build from the same CWD as today.
- Exact `memory.go` behaviors (SaveFact node shape, daily log filename,
  CompileSystemPrompt assembly) — I will read that file first thing during
  milestone 3 and mirror it.

---

*This plan is deliberately implementation-ready. Any deviation from the Go
source discovered while porting will be flagged and default to matching the Go
behavior unless the user says otherwise.*
