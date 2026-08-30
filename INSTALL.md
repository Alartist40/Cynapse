# Cynapse AI — Installation & Hardware Setup Guide

This guide covers installing `cynapse` as a universal terminal command, building from source, configuring PATH, and optimizing hardware performance for CPU/GPU execution.

---

## 1. Quick Installation

### Option A: Local Build & Universal Install (Recommended for Development)
To build from source and install `cynapse` as a universal system command:

```bash
# Clone and enter directory
cd ~/Documents/portfolio/cynapse

# Run release installer script
scripts/install_release.sh
```

`scripts/install_release.sh` compiles the release executable and automatically deploys the binary to:
- `~/.cargo/bin/cynapse`
- `~/.local/bin/cynapse`
- `~/.cynapse/builds/stable/cynapse`

It also adds the binary directory to your `PATH` in `~/.bashrc`, `~/.profile`, and `~/.zshenv`.

### Option B: Cargo Install (Hardware Safe)
```bash
RUSTFLAGS="-C target-cpu=native" cargo build --release --offline -j 2
install -m 755 target/release/cynapse ~/.cargo/bin/cynapse
```

---

## 2. Ensuring `cynapse` Works Everywhere

If running `cynapse cli` in your terminal runs an old binary or says "command not found", verify that `~/.cargo/bin` or `~/.local/bin` is exported in your `~/.bashrc`:

```bash
echo 'export PATH="$HOME/.cargo/bin:$HOME/.local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
```

Clear shell command hashing cache:
```bash
hash -r
```

Verify the binary location:
```bash
which cynapse
# Expected: /home/orangepi/.cargo/bin/cynapse
```

---

## 3. Interactive CLI Commands (`cynapse cli`)

Inside `cynapse cli`, the following interactive commands are available:

| Command | Description |
|---|---|
| `/focus` | Toggle ADHD Focus mode on/off directly. Leads with line-1 actions and strips conversational fluff. |
| `/memory search <q>` | Search DENDRITE graph memory nodes. |
| `/memory edit <id> <text>` | Alter / update a specific memory node content in `dendrite.db`. |
| `/memory del <id>` | Delete a specific memory node from `dendrite.db`. |
| `/download <hf_repo>` | Download GGUF models directly from HuggingFace with quantization selection (`Q4_K_M`, `Q8_0`, etc.). |
| `/think` | Toggle reasoning output scratchpad. |
| `/models` or `/ls` | List available GGUF models on disk. |
| `/model <n\|name>` | Hot-swap active model live in-session without restarting. |
| `/ps` | Display current RAM footprint and peak memory usage. |
| `/clear` | Flush KV cache and reset conversation history. |
| `/help` | Print interactive command menu. |
| `/bye` or `/quit` | Exit session. |

---

## 4. Hardware Optimization & Thermal Performance

### CPU Thread Allocation (Preventing Fan Spikes)
On multi-core and heterogeneous big.LITTLE CPUs (e.g. 12-core ARM CIX P1 / RK3588), spawning worker threads across all logical cores causes:
1. Thread synchronization stalls on low-frequency efficiency cores.
2. Excessive CPU power draw and thermal fan spikes.
3. Decreased matrix dot-product performance.

Cynapse automatically detects optimal thread count. For 12-core ARM CPUs (e.g. Orange Pi 6 Plus), **10 threads** gives best throughput. Set in `~/.cynapse/config.yaml`:

```yaml
llm:
  provider: leafcutter
  model: Ornith-1.5-9B-Q4_K_M.gguf
  local_threads: 10
```

### Compiler Vectorization (ARM NEON & AVX2)
To compile Cynapse with native SIMD hardware dot-product instructions (`sdot` / `AVX2`):

```bash
RUSTFLAGS="-C target-cpu=native" cargo build --release --offline
```
