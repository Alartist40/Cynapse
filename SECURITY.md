# Cynapse Security Policy

This document describes Cynapse's trust model, names the one
security boundary the project treats as load-bearing, and defines
the scope for vulnerability reports.

## Reporting a Vulnerability

Open a private issue or email the maintainer behind `github.com/Alartist40/cynapse`.
**Cynapse does not operate a bug bounty program.**

A useful report includes:

- A concise description and severity assessment.
- The affected component, identified by file path and line range
  (e.g. `internal/tools/tools.go:120-145`).
- Environment details (`cynapse version`, commit SHA, OS, Go version).
- A reproduction against `main` or the latest release.
- A statement of which trust boundary in §2 is crossed.

Please read §2 and §3 before submitting.

---

## 1. The One-Sentence Summary

**Cynapse's bash tool, web_fetch, MCP servers, and synapse plugins
all run with the operator's full user privileges.  The heuristic
safety stack (approval / netguard / redact / confirm) is
accident-prevention, never a containment boundary.  When you wire
Cynapse to untrusted input surfaces, treat it like any other
spawned subprocess: wrap the process tree, not the agent.**

## 2. Trust Model

### 2.1 Definitions

- **Agent process.** The Go binary running Cynapse, including any
  in-process modules it has loaded (LLM providers, MCP servers,
  synapse plugins).
- **Trust envelope.** The set of resources the operator has
  implicitly granted Cynapse by running it — typically, whatever
  the operator's own user account can reach on the host.
- **Heuristic layer.** One of `internal/approval`, `internal/redact`,
  `internal/netguard`, or `internal/confirm`.  Each is in-process
  Go that screens LLM output or tool requests.

### 2.2 The Boundary: OS-Level Isolation

**The only security boundary against an adversarial LLM is the
operating system.**  Nothing inside the agent process constitutes
containment — not the approval gate, not the redaction layer, not
the trust prompt, not any allowlist.  Any in-process component
that screens LLM output is a heuristic operating on an
attacker-influenced string, and this policy treats it as such.

Cynapse is a single-tenant personal agent.  Two OS-level isolation
postures are supported:

#### 2.2.1 Whole-process wrapping

Run the entire `cynapse` process tree inside a sandbox (Docker,
cgroups/namespaces, Firejail, NVIDIA OpenShell, NsJail).  Every
code path — bash, web_fetch, MCP subprocess, plugin exec, model
download — is subject to the same filesystem, network, process
policy.  This is the recommended posture when ingesting any
content the operator does not author.

#### 2.2.2 Operator present, untrusted content rare

When the operator is the only author of inputs and runs Cynapse
on a workstation in front of them, the heuristic stack (default
`security.mode: standard`) catches the cooperative-mode mistakes
that account for the vast majority of agent accidents:

- `approval`: refuses rm-rf, mkfs, dd-of-dev, fork bombs, curl|bash
- `netguard`: refuses loopback / RFC1918 / metadata endpoints
- `redact`: masks API keys before they touch the session JSONL
- `confirm`: prompts the operator on every Warn+ command

This is the supported posture for the typical Cynapse workflow.

### 2.3 Heuristic Layers

Each layer is pure Go, depends only on `stdlib`, and is gated
independently.

#### 2.3.1 Approval (`internal/approval`)

Destructive-command pattern detector.  Four severity tiers:

- **Info** — `curl` / `wget` / `ssh` (may prompt under strict)
- **Warn** — `curl|bash`, `nc -e`, `/dev/tcp`, force-push (prompts under default)
- **Danger** — `rm -rf`, `find -delete`, `shred`, fork bombs, infinite loops (denies under default)
- **Critical** — `mkfs`, `dd of=/dev/*`, `wipefs`, `chmod 777 /` (always denies)

Two canned policies: `balanced` (default, Warn+ prompts, Danger+ denies)
and `trust-local` (Critical only).  Select via `security.approval_policy`
in `~/.cynapse/config.yaml`.

Limitation: regex denylists over shell strings are structurally
incomplete.  An adversarial prompt that base64-encodes its payload
or uses `${IFS}` injection can bypass any pure-string detector.

#### 2.3.2 Netguard (`internal/netguard`)

SSRF guard for outbound HTTP.  Resolves the URL hostname via
`net.LookupIP` and tests every A record against the policy.

- `SecureDefault()`: refuses loopback, RFC1918, link-local, multicast,
  unspecified, and the AWS/GCP/Azure metadata endpoint
  `169.254.169.254`.
- `LocalDevPolicy()`: allows loopback and RFC1918, so Ollama on
  `localhost:11434` still works.  Metadata is still denied.

Limitation: DNS rebinding TOCTOU windows exist.  Pair with a
whole-process network policy.

#### 2.3.3 Redact (`internal/redact`)

Regex + JSON-key + URL-query-param scanner.  Catches OpenAI,
Anthropic, HF, GitHub, AWS, Slack, Stripe, Twilio, PEM private
keys, JWTs, plus URL embedded `?api_key=`/`?token=`/`?signature=`.

The agent runs `redact.Redact()` over every tool result and every
final reply *before* writing to the session JSONL, so secrets do
not end up on disk.

Limitation: any denylist misses novel credential formats.  Pair
with least-privileged API keys.

#### 2.3.4 Confirm (`internal/confirm`)

Interactive prompt protocol with four operator choices:

- **Decline** — refuse this request
- **AllowOnce** — approve this single invocation, no memory
- **AllowSection** — approve every matching request for the
  current agent section (a turn, a tool run)
- **AllowAlways** — persist a rule to `~/.cynapse/allowlist` so
  the operator doesn't see this prompt again

Persistent allowlist at `~/.cynapse/allowlist` survives restarts.
Sensitive request kinds (`sudo`, `password`) refuse the `Always`
option — secrets are never persisted.  Sudo paths route the typed
password through `sudo -S -p ''` so the agent itself never sees
the password as plaintext on its own stdin.

Limitation: `AllowAlways` rules are exact-string match.  A prompt
that rewrites its command trivially (whitespace, casing, semicolon
vs `&&`) is treated as a new rule.  This is on purpose: collapses
all matches into one rule would be a worse failure mode.

### 2.4 File Permissions

- `config.yaml` is written `0600` (was `0644` in v2.2 and earlier).
- Session JSONL is `0644` in `standard` mode and `0600` in
  `strict` mode (via `cfg.SessionFileMode()`).
- The persistent allowlist is `0600`.

### 2.5 Plugin Trust Model

Synapses are executables in `~/.cynapse/synapses/` that respond to
`--meta` with JSON.  They run with full agent privileges: they can
read the same config file (API keys), call the same tools, and
spawn the same MCP servers.

The boundary for third-party synapses is operator review before
install.  SHA-256 verification is supported for URL downloads via
`cynapse synapse add <name> --url <url> --hash <sha256>`.

A malicious or buggy synapse that exfiltrates data is the expected
failure mode of one that wasn't reviewed, not a vulnerability in
Cynapse itself.  Bugs in Cynapse's synapse-install path that
prevent the operator from seeing what they're installing are
security issues under §3.1.

### 2.6 External Surfaces

- **DENDRITE API server.** Binds `127.0.0.1:0` (loopback only,
  random high port).  CORS wide-open on purpose because the only
  client is the embedded D3.js visualisation in the TUI.  No
  authentication because the bind is local.
- **Gateway config.** The default `gateway.address: 0.0.0.0:8080`
  in the config schema is intended for loopback binding only
  when wired into a TUI consumer.  Operators publishing the
  gateway publicly must provide their own authentication and
  TLS on top of the bind.

---

## 3. Scope

### 3.1 In Scope

- Escape from the supported posture (§2.2) — for example: a
  heuristic that over-rejects operator-authored input and a
  documented break-glass flag that silently disables all gates.
- Unauthorized external-surface access — any caller outside the
  configured authorisation set dispatching work or receiving
  output.
- Credential exfiltration — leakage of operator credentials to a
  destination outside the trust envelope via a mechanism that
  should have prevented it (env scrubbing bug, allowlist file
  written world-readable, etc.).
- Trust-model documentation violations — code behaving contrary
  to what this policy or reasonable operator expectations would
  predict.

### 3.2 Out of Scope

- **Bypasses of in-process heuristics** — defeating `approval` via
  clever encoding, defeating `redact` via novel credential formats,
  or defeating `confirm` via rule-key variance.  These components
  are explicitly *not boundaries*; defeating them is not a
  vulnerability under this policy.
- **Prompt injection per se.**  Getting the LLM to emit unusual
  output — via injected content, hallucination, or training
  artefacts — is not itself a vulnerability.  A successful
  prompt injection that results in a §3.1 outcome (e.g. unauth
  external access) is an issue; the prompt injection itself is
  not.
- **Consequences of running outside the supported posture.**
  Reports that bash or web_fetch reach host state under the local
  backend; reports whose preconditions require pre-existing write
  access to operator-owned configuration files.
- **Documented break-glass settings.**  `security.mode: trust-local`
  explicitly disables most heuristics; reports against that
  configuration are not vulnerabilities — that's the flag's job.
- **Community-contributed synapses**, including the synapse
  registry.  These are in the operator's review surface, not
  Cynapse's trust surface.  Bugs in Cynapse's synapse-install
  path that prevent the operator from seeing what they're
  installing are in scope under §3.1.

---

## 4. Deployment Hardening

The single most important hardening decision is to match the
isolation posture (§2.2) to the trust of the content the agent
will ingest.  Beyond that:

- Run the agent as a non-root user.
- Keep credentials in `~/.cynapse/config.yaml` with `chmod 600`,
  or use environment variables (which are equally visible to
  spawned subprocesses).
- Do not expose the gateway or API to the public internet without
  VPN, Tailscale, or firewall protection.
- Review third-party synapses before install.
- Configure `security.approval_policy` as the strictest level
  your workflow tolerates; loosen only when you understand the
  trade-off.
- Operate the persistent allowlist (cat `~/.cynapse/allowlist`)
  periodically and prune entries that no longer apply.

---

## 5. Disclosure

- **Coordinated disclosure window:** 90 days from report, or until
  a fix is released, whichever comes first.
- **Credit:** reporters are credited in release notes unless
  anonymity is requested.

---

*This policy is informed by the Hermes Agent trust model
(Nous Research, MIT licensed), re-shaped to match Cynapse's
single-tenant, terminal-first posture.*
