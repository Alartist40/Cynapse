# cynapse-rs

Rust port of [cynapse](../cynapse/) — a small, fast, local-first AI agent with
long-term memory (DENDRITE), streaming chat, document analysis, and a
ratatui TUI.

Inspired by [jcode](../reference/jcode/)'s layered crate architecture.

## Install

One-command bootstrap from source (Linux / macOS):

```bash
curl -fsSL https://raw.githubusercontent.com/nex/cynapse-rs/main/scripts/install.sh | bash
```

This builds the binary, places it in `~/.cynapse/builds/versions/<hash>/cynapse`,
creates `~/.local/bin/cynapse` as the launcher, and (idempotently) adds the
launcher directory to `PATH` in `~/.zshenv`, `~/.bashrc`, `~/.profile`, and
fish config.

For local development builds (no GitHub):

```bash
scripts/install_release.sh        # release-lto profile
scripts/install_release.sh --fast # fast release profile (no LTO)
```

## CLI

```bash
cynapse                # launch the chat TUI (default)
cynapse chat           # launch the chat TUI (explicit)
cynapse version        # print version string
cynapse config show    # print resolved YAML config
cynapse config path    # absolute path to config.yaml
cynapse config init    # write default ~/.cynapse/config.yaml (mode 0600)
cynapse memory list
cynapse memory get <id>
cynapse memory search <query>
cynapse memory stats
cynapse memory export
```

In the TUI: `/help` lists slash commands (`/attach`, `/clear`, `/compress`,
`/memory`, `/allowed`, `/model`, `/quit`, ...).

## Providers

| Provider        | Default model            | Streaming | Notes |
|-----------------|--------------------------|-----------|-------|
| `ollama`        | `qwen-bench:latest`      | NDJSON    | Default; any Ollama local model |
| `openai`        | (config)                 | SSE       | Set `OPENAI_API_KEY` or `openai_key` |
| `anthropic`     | (config)                 | SSE       | Behind `--features anthropic` |
| `leafcutter`    | local GGUF path          | SSE + fallback | Spawns `leafcutter server --model <gguf>`; falls back to non-streaming if leafcutter's native-streaming engine panics |

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