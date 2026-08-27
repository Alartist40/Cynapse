# Testing Walkthrough

## Quick start (unit tests)

```bash
cd /home/xander/Documents/portfolio/cynapse-rs
cargo test --workspace
```

This runs 64 core unit tests, 3 dendrite-compatibility tests (against the live
`data/dendrite.db`), and 6 TUI widget unit tests. All tests are offline and
require no network or Ollama.

Expected output:

```
   Compiling cynapse-core ...
   Compiling cynapse-tui ...
   Compiling cynapse ...
    Finished `test` profile
     Running unittests ...
     Running unittests ...
     ...
test result: ok. 64 passed; 0 failed; ...
test result: ok. 3 passed; 0 failed; ...
test result: ok. 6 passed; 0 failed; ...
```

## Live smoke tests

These connect to real services and are `#[ignore]`d by default. Run them
individually or as a group:

### Ollama e2e (requires `ollama serve` on localhost:11434)

```bash
cargo test -p cynapse-core --test agent_live -- --ignored --nocapture live_ollama
```

Runs:
- `live_ollama_chat_roundtrip` — one-shot generation, checks tool calls
- `live_ollama_stream_roundtrip` — streaming, checks content non-empty
- `live_circuit_breaker_recovers` — points at dead port, verifies breaker opens

### Leafcutter (requires `leafcutter` binary + a local GGUF model)

```bash
LEAFCUTTER_MODEL=/path/to/model.gguf \
  cargo test -p cynapse-core --test agent_live -- --ignored --nocapture live_leafcutter
```

Default model path: `/home/xander/Downloads/models/Ministral-3-3B-Instruct-2512-Q4_K_M.gguf`

Runs:
- `live_leafcutter_chat_roundtrip` — single completion
- `live_leafcutter_stream_roundtrip` — streaming (falls back to non-streaming if
  leafcutter's native-streaming engine panics on `stream:true` requests)

### OCR (requires `frob/unlimited-ocr:q8_0` pulled in Ollama)

```bash
OCR_IMAGE=/path/to/screenshot.png \
  cargo test -p cynapse-core --test agent_live -- --ignored --nocapture live_ocr
```

Default image: `/home/xander/Downloads/models/unlimited ocr/baidu.png`

## Running all live tests

```bash
cargo test -p cynapse-core --test agent_live -- --ignored --nocapture
```

Note: the Ollama and leafcutter tests compete for GPU/memory. Run them
sequentially if you see timeouts.

If you see the CYNAPSE logo and a spinner, the TUI works. Press `Escape` then
`q` to quit, or `Ctrl+C`.

## Native Engine CLI testing (`cynapse cli`)

Test the direct native LLM engine CLI:

```bash
cynapse cli
```

Key features to verify:
1. Dynamic greeting banner on launch and dynamic farewell on exit (`/bye`, `/quit`).
2. Hardware diagnostics box showing CPU cores, RAM, dispatch tier, profile, temp, max tokens.
3. Live streaming with color-graded reasoning (`<think>`) and response text (`gold`).
4. `/models` to list local GGUF models.
5. `/model <n|name>` to hot-swap active model live in-session.
6. `/help` command menu box.

To exercise a real streaming turn in a headless terminal:

```bash
stty rows 40 cols 120
script -qc 'echo "/memory soul" | timeout 15 ./target/release/cynapse chat' /dev/null
```

This should render DENDRITE FTS5 results. With Ollama running, a conversation
turn streams live:

```bash
echo "hello" | timeout 15 ./target/release/cynapse chat
```

## Verification against live data

The Rust binary reads the same paths as the Go original:

| Data | Location | What to check |
|------|----------|---------------|
| DENDRITE graph | `data/dendrite.db` | `cargo test --workspace` opens and validates 8 live nodes |
| Sessions | `data/sessions/` | TUI writes to `data/sessions/cynapse_tui_01.jsonl` (byte-compatible with Go) |
| Persona | `data/persona/` | TUI reads `AGENTS.md`, `USER.md`, `TOOLS.md`, `HEARTBEAT.md` etc. |
| Config | `config.yaml` (cwd) | `cargo run -- config show` prints resolved YAML |

CLI commands for ad-hoc verification:

```bash
cargo run -- memory list          # should show 8 nodes (identity, user, soul, ...)
cargo run -- memory get identity  # full markdown body
cargo run -- memory search "agent rules"  # FTS5 search
cargo run -- memory stats         # node count, DB size, FTS status
```

## Cleaning up after tests

Live tests create temp files under `/tmp/cynapse-live-*`. These are cleaned
up automatically (the test harness has a `Drop` guard or test-local
`remove_dir_all`). The TUI appends to the real session file
(`data/sessions/cynapse_tui_01.jsonl`); delete that manually if you want a
clean slate.