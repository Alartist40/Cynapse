//! Configuration model and loader, faithful to the Go cynapse
//! `internal/config/config.go` semantics (defaults, env overrides, YAML).

use std::env;
use std::fs;
use std::path::Path;

use anyhow::{Context, Result};
use serde::{Deserialize, Serialize};

/// Effective security mode, normalised from the `security.mode` YAML string.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum SecurityMode {
    TrustLocal,
    Standard,
    Strict,
}

/// Effective net policy, from the `security.net_policy` YAML string.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum NetPolicy {
    Secure,
    LocalDev,
}

/// Root configuration, mirroring `Config` in the Go original.
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(default)]
pub struct Config {
    pub gateway: GatewayConfig,
    pub llm: LlmConfig,
    pub memory: MemoryConfig,
    pub tools: ToolsConfig,
    pub mcp: McpConfig,
    pub models: ModelsConfig,
    pub security: SecurityConfig,
    /// Number of pre-update backups to retain (default: 5).
    pub backup_keep: u32,
    /// Document-analysis / OCR settings.
    pub ocr: OcrConfig,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(default)]
pub struct SecurityConfig {
    /// "trust-local" | "standard" | "strict"
    pub mode: String,
    /// Strip credential-like substrings. `None` falls back to
    /// true under standard/strict, false under trust-local.
    pub redact_secrets: Option<bool>,
    /// "secure" | "local-dev"
    pub net_policy: String,
    /// "trust-local" | "balanced" | "strict"
    pub approval_policy: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(default)]
pub struct GatewayConfig {
    pub address: String,
    pub auth_token: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(default)]
pub struct LlmConfig {
    /// "ollama" | "anthropic" | "openai" | "gemini" | "local"
    pub provider: String,
    pub model: String,
    pub anthropic_key: String,
    pub openai_key: String,
    pub gemini_key: String,
    /// OpenAI-compatible base URL. Default: https://api.openai.com/v1
    pub openai_base_url: String,
    /// Ollama base URL. Default: http://localhost:11434
    pub ollama_base_url: String,
    // Local model settings (provider: "local" | "leafcutter") — carried for
    // config compatibility; local GGUF inference is out of v1 scope.
    pub llama_server_path: String,
    pub leafcutter_path: String,
    pub local_gpu_layers: i64,
    pub local_context_size: i64,
    pub local_threads: i64,
    pub models_dir: String,
    // Generation params
    pub max_tokens: u64,
    pub temperature: f64,
    pub max_retries: u32,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(default)]
pub struct MemoryConfig {
    /// Persona markdown files per device. Default: "./data/persona"
    pub persona_path: String,
    /// JSONL session logs. Default: "./data/sessions"
    pub sessions_path: String,
    /// SQLite database for searchable memory. Default: "./data/memory.db"
    pub db_path: String,
    /// SQLite database for the knowledge graph. Default: "./data/dendrite.db"
    pub dendrite_db_path: String,
    /// Default persona templates. Default: "./persona/defaults"
    pub defaults_path: String,
    /// Hours before triggering heartbeat curator. Default: 6
    pub heartbeat_interval_hours: i64,
    /// Max session messages before compaction. Default: 100
    pub max_session_messages: u32,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(default)]
pub struct ModelsConfig {
    pub models_dir: String,
    pub use_ollama: bool,
    pub use_llama_server: bool,
    pub hf_token: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(default)]
pub struct ToolsConfig {
    /// "minimal" | "standard" | "full"
    pub profile: String,
    pub allow: Vec<String>,
    pub deny: Vec<String>,
    /// Working directory for the bash tool. Default: "./workspace"
    pub work_dir: String,
    /// Timeout for tool execution (seconds). Default: 30
    pub timeout_seconds: u32,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(default)]
pub struct McpConfig {
    pub enabled: bool,
    pub servers: Vec<McpServer>,
}

/// Document-analysis (OCR) settings. Images attached to a message are
/// transcribed with a vision-capable model before they reach the chat
/// model. The model list is tried in order so the local
/// `unlimited-ocr` big model is used first, with generic Ollama vision
/// models (and finally the chat model's own multimodal handling) as
/// fallbacks.
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(default)]
pub struct OcrConfig {
    pub enabled: bool,
    /// Ordered list of Ollama models to try for OCR. The first one that
    /// returns text wins.
    pub models: Vec<String>,
    /// Prompt sent alongside the image (Ollama `/api/generate`).
    pub prompt: String,
    /// Ollama base URL for OCR. Empty reuses `llm.ollama_base_url`.
    pub ollama_base_url: String,
    /// Skip images larger than this many MB (avoid base64 blow-ups).
    pub max_image_mb: u64,
    /// Per-model request timeout (seconds).
    pub timeout_seconds: u64,
    /// Prefix inserted before the transcription in the user message.
    pub prefix: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(default)]
pub struct McpServer {
    pub name: String,
    pub command: String,
    pub args: Vec<String>,
    pub env: std::collections::HashMap<String, String>,
}

impl Default for SecurityConfig {
    fn default() -> Self {
        SecurityConfig {
            mode: "standard".to_string(),
            redact_secrets: None,
            net_policy: "secure".to_string(),
            approval_policy: "balanced".to_string(),
        }
    }
}

impl Default for GatewayConfig {
    fn default() -> Self {
        GatewayConfig {
            address: "0.0.0.0:8080".to_string(),
            auth_token: String::new(),
        }
    }
}

impl Default for LlmConfig {
    fn default() -> Self {
        LlmConfig {
            provider: "ollama".to_string(),
            model: "qwen2.5".to_string(),
            anthropic_key: String::new(),
            openai_key: String::new(),
            gemini_key: String::new(),
            openai_base_url: String::new(),
            ollama_base_url: "http://localhost:11434".to_string(),
            llama_server_path: String::new(),
            leafcutter_path: String::new(),
            local_gpu_layers: 0,
            local_context_size: 4096,
            local_threads: 0,
            models_dir: String::new(),
            max_tokens: 4096,
            temperature: 0.7,
            max_retries: 3,
        }
    }
}

impl Default for MemoryConfig {
    fn default() -> Self {
        MemoryConfig {
            persona_path: "./data/persona".to_string(),
            sessions_path: "./data/sessions".to_string(),
            db_path: "./data/memory.db".to_string(),
            dendrite_db_path: "./data/dendrite.db".to_string(),
            defaults_path: "./persona/defaults".to_string(),
            heartbeat_interval_hours: 6,
            max_session_messages: 100,
        }
    }
}

impl Default for ModelsConfig {
    fn default() -> Self {
        ModelsConfig {
            models_dir: "./models".to_string(),
            use_ollama: true,
            use_llama_server: false,
            hf_token: String::new(),
        }
    }
}

impl Default for ToolsConfig {
    fn default() -> Self {
        ToolsConfig {
            profile: "standard".to_string(),
            allow: Vec::new(),
            deny: Vec::new(),
            work_dir: "./workspace".to_string(),
            timeout_seconds: 30,
        }
    }
}

impl Default for McpConfig {
    fn default() -> Self {
        McpConfig {
            enabled: true,
            servers: Vec::new(),
        }
    }
}

impl Default for McpServer {
    fn default() -> Self {
        McpServer {
            name: String::new(),
            command: String::new(),
            args: Vec::new(),
            env: std::collections::HashMap::new(),
        }
    }
}

impl Default for OcrConfig {
    fn default() -> Self {
        OcrConfig {
            enabled: true,
            models: vec![
                "frob/unlimited-ocr:q8_0".to_string(),
                "llava".to_string(),
                "llama3.2-vision".to_string(),
                "moondream".to_string(),
            ],
            prompt: "<image>document parsing.".to_string(),
            ollama_base_url: String::new(),
            max_image_mb: 20,
            timeout_seconds: 120,
            prefix: "[OCR transcription of the attached image]\n".to_string(),
        }
    }
}

impl Default for Config {
    fn default() -> Self {
        Config {
            gateway: GatewayConfig::default(),
            llm: LlmConfig::default(),
            memory: MemoryConfig::default(),
            tools: ToolsConfig::default(),
            mcp: McpConfig::default(),
            models: ModelsConfig::default(),
            security: SecurityConfig::default(),
            ocr: OcrConfig::default(),
            backup_keep: 5,
        }
    }
}

impl Config {
    /// Whether the redaction layer should run. An explicit
    /// `redact_secrets` value always wins; otherwise true unless
    /// the effective mode is trust-local.
    pub fn effective_redaction(&self) -> bool {
        match self.security.redact_secrets {
            Some(v) => v,
            None => self.effective_security_mode() != SecurityMode::TrustLocal,
        }
    }

    /// Normalised security mode; unknown values fall back to Standard.
    pub fn effective_security_mode(&self) -> SecurityMode {
        match self.security.mode.as_str() {
            "trust-local" => SecurityMode::TrustLocal,
            "strict" => SecurityMode::Strict,
            _ => SecurityMode::Standard,
        }
    }

    /// File mode for transcripts — 0600 under strict mode, else 0644.
    pub fn session_file_mode(&self) -> u32 {
        if self.effective_security_mode() == SecurityMode::Strict {
            0o600
        } else {
            0o644
        }
    }

    pub fn effective_net_policy(&self) -> NetPolicy {
        match self.security.net_policy.as_str() {
            "local-dev" => NetPolicy::LocalDev,
            _ => NetPolicy::Secure,
        }
    }

    /// Effective approval policy: "trust-local" | "balanced" | "strict".
    pub fn effective_approval_policy(&self) -> &str {
        match self.security.approval_policy.as_str() {
            "trust-local" | "strict" => self.security.approval_policy.as_str(),
            _ => "balanced",
        }
    }
}

/// Default config, matching `defaults()` in the Go original.
pub fn defaults() -> Config {
    Config::default()
}

/// Create a default config file at `path` with mode 0600 (config holds keys).
pub fn create_default(path: &Path) -> Result<()> {
    let cfg = defaults();
    let data = serde_yaml::to_string(&cfg).context("marshaling config")?;
    if let Some(dir) = path.parent() {
        fs::create_dir_all(dir).context("creating directory")?;
    }
    write_with_mode(path, data.as_bytes(), 0o600)
}

/// Load config from `path`. Missing file → defaults + env overrides.
pub fn load(path: &Path) -> Result<Config> {
    let mut cfg = defaults();
    match fs::read(path) {
        Ok(data) => {
            let parsed: Config = serde_yaml::from_slice(&data).context("parsing config")?;
            // serde merges YAML over defaults via #[serde(default)] only when
            // deserialising into a pre-filled struct; we deserialise fresh so
            // missing sections must fall back. Use the parse result directly,
            // but it is already defaulted field-by-field.
            cfg = parsed;
        }
        Err(e) if e.kind() == std::io::ErrorKind::NotFound => {}
        Err(e) => return Err(e).context("reading config"),
    }
    apply_env(&mut cfg);
    load_keyring(&mut cfg);
    Ok(cfg)
}

fn load_keyring(cfg: &mut Config) {
    let home = match std::env::var("HOME") {
        Ok(h) => h,
        Err(_) => return,
    };
    let path = format!("{home}/.cynapse/apikeys");
    let content = match std::fs::read_to_string(&path) {
        Ok(c) => c,
        Err(_) => return,
    };
    for line in content.lines() {
        let line = line.trim();
        if line.is_empty() || line.starts_with('#') {
            continue;
        }
        if let Some(eq) = line.find('=') {
            let name = line[..eq].trim();
            let value = line[eq + 1..].trim();
            if !name.is_empty() && !value.is_empty() {
                match name.to_lowercase().as_str() {
                    "openai" if cfg.llm.openai_key.is_empty() => cfg.llm.openai_key = value.to_string(),
                    "anthropic" if cfg.llm.anthropic_key.is_empty() => cfg.llm.anthropic_key = value.to_string(),
                    "gemini" if cfg.llm.gemini_key.is_empty() => cfg.llm.gemini_key = value.to_string(),
                    _ => {}
                }
            }
        }
    }
}

fn apply_env(cfg: &mut Config) {
    for (var, key) in [
        ("ANTHROPIC_API_KEY", &mut cfg.llm.anthropic_key),
        ("OPENAI_API_KEY", &mut cfg.llm.openai_key),
        ("OPENAI_BASE_URL", &mut cfg.llm.openai_base_url),
        ("GEMINI_API_KEY", &mut cfg.llm.gemini_key),
        ("OLLAMA_BASE_URL", &mut cfg.llm.ollama_base_url),
        ("CYNAPSE_AUTH_TOKEN", &mut cfg.gateway.auth_token),
        ("HF_TOKEN", &mut cfg.models.hf_token),
    ] {
        if let Ok(v) = env::var(var) {
            if !v.is_empty() {
                *key = v;
            }
        }
    }
    for (var, setter) in [
        ("CYNAPSE_PROVIDER", set_provider as fn(&mut Config, &str)),
        ("CYNAPSE_MODEL", set_model),
        ("CYNAPSE_ADDRESS", set_address),
    ] {
        if let Ok(v) = env::var(var) {
            if !v.is_empty() {
                setter(cfg, &v);
            }
        }
    }
}

fn set_provider(cfg: &mut Config, v: &str) {
    cfg.llm.provider = v.to_lowercase();
}
fn set_model(cfg: &mut Config, v: &str) {
    cfg.llm.model = v.to_string();
}
fn set_address(cfg: &mut Config, v: &str) {
    cfg.gateway.address = v.to_string();
}

/// Write a file with a restrictive mode (and default perms on Windows).
fn write_with_mode(path: &Path, data: &[u8], mode: u32) -> Result<()> {
    #[cfg(unix)]
    {
        use std::os::unix::fs::OpenOptionsExt;
        fs::OpenOptions::new()
            .write(true)
            .create(true)
            .truncate(true)
            .mode(mode)
            .open(path)
            .and_then(|mut f| {
                use std::io::Write;
                f.write_all(data)?;
                Ok(())
            })
            .context("writing file")
    }
    #[cfg(not(unix))]
    {
        fs::write(path, data).context("writing file")
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn defaults_match_go() {
        let c = defaults();
        assert_eq!(c.llm.provider, "ollama");
        assert_eq!(c.llm.model, "qwen2.5");
        assert_eq!(c.llm.ollama_base_url, "http://localhost:11434");
        assert_eq!(c.llm.max_tokens, 4096);
        assert_eq!(c.llm.temperature, 0.7);
        assert_eq!(c.llm.max_retries, 3);
        assert_eq!(c.memory.dendrite_db_path, "./data/dendrite.db");
        assert_eq!(c.tools.profile, "standard");
        assert_eq!(c.tools.work_dir, "./workspace");
        assert_eq!(c.tools.timeout_seconds, 30);
        assert_eq!(c.backup_keep, 5);
    }

    #[test]
    fn security_mode_normalisation() {
        let mut c = defaults();
        c.security.mode = "bogus".into();
        assert_eq!(c.effective_security_mode(), SecurityMode::Standard);
        c.security.mode = "strict".into();
        assert_eq!(c.effective_security_mode(), SecurityMode::Strict);
        assert_eq!(c.session_file_mode(), 0o600);
        c.security.mode = "trust-local".into();
        assert_eq!(c.session_file_mode(), 0o644);
    }

    #[test]
    fn effective_redaction_rules() {
        let mut c = defaults();
        c.security.mode = "trust-local".into();
        assert!(!c.effective_redaction());
        c.security.mode = "standard".into();
        assert!(c.effective_redaction());
        c.security.redact_secrets = Some(false);
        c.security.mode = "strict".into();
        assert!(!c.effective_redaction());
    }

    #[test]
    fn load_missing_file_uses_defaults() {
        let c = load(Path::new("/nonexistent/definitely-missing.yaml")).unwrap();
        assert_eq!(c.llm.provider, "ollama");
    }
}
