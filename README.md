# cynapse-rs

Rust port of [cynapse](../cynapse/) — a small, fast, local-first AI agent with
long-term memory (DENDRITE), streaming chat, document analysis, and a
ratatui TUI.

Inspired by [jcode](../reference/jcode/)'s layered crate architecture.

## Install

One-command install (Linux / macOS / SBCs like Orange Pi):

```bash
curl -fsSL https://raw.githubusercontent.com/Alartist40/cynapse/main/scripts/install.sh | bash
```

This downloads the prebuilt `cynapse` binary for your OS/CPU (x86_64 and
aarch64 published on the GitHub releases page), so no Rust toolchain is needed.
If no prebuilt exists for your platform, it falls back to building from source.
Either way the binary lands in `~/.cynapse/builds/versions/<hash>/cynapse`,
`~/.local/bin/cynapse` is created as the launcher, and (idempotently) the
launcher directory is added to `PATH` in `~/.zshenv`, `~/.bashrc`,
`~/.profile`, and fish config — so `cynapse` works from any directory.

Update to the latest version:

```bash
cynapse update
```

`cynapse update` pulls the latest code from GitHub, rebuilds it, and re-points
the launcher — like `opencode upgrade` / `hermes update`.

For local development builds (no GitHub):

```bash
scripts/install_release.sh        # release-lto profile
scripts/install_release.sh --fast # fast release profile (no LTO)
```

## CLI

```bash
cynapse                # launch the chat TUI (default)
cynapse chat           # launch the chat TUI (explicit)
cynapse cli            # launch direct native engine interactive CLI REPL
cynapse repl -p "msg"  # execute single prompt in lightweight CLI mode
cynapse version        # print version string
cynapse config show    # print resolved YAML config
cynapse config path    # absolute path to config.yaml
cynapse config init    # write default ~/.cynapse/config.yaml (mode 0600)
cynapse memory list
cynapse memory get <id>
cynapse memory search <query>
cynapse memory stats
cynapse memory export
cynapse doctor         # run full system diagnostic health check
cynapse update         # update to latest release from GitHub
```

In `cynapse cli` & `cynapse tui`:
- Interactive **Startup Model Picker Modal** (`🚀 Select Model on Launch`) on every start to pick or download models.
- **Double-ESC (`Esc`) Interrupt**: Press `Esc` while the model is responding to interrupt streaming instantly and return to prompt input.
- **Real-Time Live Thinking Stream**: Thinking scratchpad streams live in Dim Purple Accent, cleanly separated from the final response in Gold.
- `/focus` to toggle focused, zero-fluff output mode.
- `/think` to toggle reasoning output scratchpad.
- `/download <hf_repo>` to fetch GGUF models directly from HuggingFace.
- `/models` to list and hot-swap active LLM models live in-session without restarting.
- `/memory search`, `/memory edit`, `/memory del` to manage DENDRITE graph memory nodes.
- `/ps` to display live RAM footprint vs peak memory.
- `/help` lists interactive CLI and TUI commands.

See [INSTALL.md](INSTALL.md) for step-by-step setup, hardware acceleration, and thermal tuning details.

## Providers

| Provider        | Default model            | Streaming | Notes |
|-----------------|--------------------------|-----------|-------|
| `ollama`        | `qwen-bench:latest`      | NDJSON    | Any Ollama local model |
| `openai`        | (config)                 | SSE       | Set `OPENAI_API_KEY` or `openai_key` |
| `anthropic`     | (config)                 | SSE       | Behind `--features anthropic` |
| `leafcutter`    | local GGUF path          | SSE + fallback | Native engine with vendored llama.cpp (b10434) — **2.5+ tok/s, no Ollama dependency** |

## Leafcutter Native Engine (Vendored llama.cpp)

Cynapse embeds **Leafcutter** as its native inference engine, with **llama.cpp statically linked** inside the binary. No external dependencies required.

### Architecture

1. **Vendored llama.cpp (b10434)**: Compiled with `GGML_NATIVE=ON` for ARM NEON/SVE SIMD kernels, statically linked via FFI
2. **Layer-Streaming Mode (`shard_loader`)**: For 70B+ models, streams layer-by-layer from SSD using memory-mapped zero-copy reads

### Performance (Orange Pi 6 Plus, 12-core ARMv9-A)

| Engine | Speed | Notes |
|--------|-------|-------|
| Pure Rust (scalar) | ~1.0 tok/s | No SIMD |
| **Vendored llama.cpp (FFI)** | **~2.5 tok/s** | Matches Ollama |
| Ollama API | 2.58 tok/s | Reference |

### Config

```yaml
llm:
  provider: leafcutter
  model: /path/to/model.gguf
  local_threads: 10  # optimal for 12-core ARM
```

Set the provider:

```bash
CYNAPSE_PROVIDER=ollama CYNAPSE_MODEL=qwen-bench:latest cynapse
```

## Document analysis (OCR)

Image attachments are transcribed before reaching the chat model. Configure
the OCR chain in `config.yaml`:

```yaml
ocr:
  enabled: true
  models:
    - frob/unlimited-ocr:q8_0   # primary: local big-model OCR
    - llava                     # fallbacks
    - llama3.2-vision
    - moondream
  prompt: "<image>document parsing."
  max_image_mb: 20
  timeout_seconds: 120
```

Each model is tried in order. The first non-empty transcription wins. If every
model fails, the image attachment is preserved so any multimodal provider
that can see images still receives it — graceful degradation.

Text and PDF attachments are inlined directly into the user message (their
extracted text is the no-OCR-needed fallback for non-vision chat models).

## Config

Loaded from `./config.yaml` (cwd) → `~/.cynapse/config.yaml` → built-in
defaults. Environment overrides:

| Variable               | Field                                |
|------------------------|--------------------------------------|
| `ANTHROPIC_API_KEY`    | `llm.anthropic_key`                  |
| `OPENAI_API_KEY`       | `llm.openai_key`                     |
| `OPENAI_BASE_URL`      | `llm.openai_base_url`                |
| `GEMINI_API_KEY`       | `llm.gemini_key`                     |
| `OLLAMA_BASE_URL`      | `llm.ollama_base_url`                |
| `CYNAPSE_PROVIDER`     | `llm.provider`                       |
| `CYNAPSE_MODEL`        | `llm.model`                          |
| `CYNAPSE_AUTH_TOKEN`   | `gateway.auth_token`                 |
| `CYNAPSE_HOME`         | overrides `~/.cynapse` for builds    |
| `HF_TOKEN`             | `models.hf_token`                    |

## Workspace layout

```
cynapse-rs/
├── Cargo.toml              # workspace
├── src/                    # root binary: cli + main
├── scripts/                # install.sh, install_release.sh
├── crates/
│   ├── cynapse-core/       # config, dendrite, agent, providers, tools, ocr, ...
│   └── cynapse-tui/        # ratatui presentation layer
└── config.yaml             # local dev config (live-data paths)
```

## Tests

```bash
cargo test --workspace                                  # unit + compat
cargo test -p cynapse-core --test agent_live -- --ignored --nocapture  # live smoke
```

See `TESTING.md` for the full walkthrough.

## License

Same as the upstream cynapse project.