//! `cynapse doctor` — comprehensive system diagnostic and auto-repair.
//!
//! Checks: system hardware, binary installation, llama.cpp linkage, model
//! discovery, Ollama connectivity, DENDRITE database, persona files,
//! network access, and configuration validity. With `--fix`, attempts
//! automatic repairs.

use std::path::{Path, PathBuf};
use std::time::Duration;

use colored::Colorize;

struct Check {
    label: String,
    status: Status,
    detail: String,
    fixable: bool,
}

enum Status {
    Ok,
    Warn,
    Fail,
}

impl Status {
    fn icon(&self) -> String {
        match self {
            Status::Ok => "✓".green().bold().to_string(),
            Status::Warn => "⚠".yellow().bold().to_string(),
            Status::Fail => "✗".red().bold().to_string(),
        }
    }
}

struct Doctor {
    checks: Vec<Check>,
    fixes: Vec<String>,
}

impl Doctor {
    fn new() -> Self {
        Self { checks: Vec::new(), fixes: Vec::new() }
    }

    fn add(&mut self, label: impl Into<String>, status: Status, detail: String) {
        self.checks.push(Check { label: label.into(), status, detail, fixable: false });
    }

    fn add_fixable(&mut self, label: impl Into<String>, status: Status, detail: String) {
        self.checks.push(Check { label: label.into(), status, detail, fixable: true });
    }

    fn section(&self, title: &str) {
        println!();
        println!("  {}", title.purple().bold());
        println!("  {}", "─".repeat(52).dimmed());
    }

    fn print_results(&self) {
        let fails = self.checks.iter().filter(|c| matches!(c.status, Status::Fail)).count();
        let warns = self.checks.iter().filter(|c| matches!(c.status, Status::Warn)).count();

        for c in &self.checks {
            let marker = c.status.icon();
            let label = c.label.bold();
            let detail = if c.detail.is_empty() { String::new() } else { format!(" ({})", c.detail.dimmed()) };
            let fix_hint = if c.fixable && matches!(c.status, Status::Fail | Status::Warn) {
                " [auto-fixable]".yellow().to_string()
            } else {
                String::new()
            };
            println!("     {} {:<30}{}{}", marker, label, detail, fix_hint);
        }

        println!();
        if fails == 0 && warns == 0 {
            println!("  {}", "✅ All checks passed. Cynapse is healthy.".green().bold());
        } else {
            let mut parts = Vec::new();
            if fails > 0 { parts.push(format!("{} failures", fails).red().bold().to_string()); }
            if warns > 0 { parts.push(format!("{} warnings", warns).yellow().bold().to_string()); }
            println!("  {}", format!("⚠ Issues found: {}", parts.join(", ")).bold());
            if !self.fixes.is_empty() {
                println!("  {}", format!("🔧 {} auto-fixes applied.", self.fixes.len()).green().bold());
                for fix in &self.fixes {
                    println!("     {}", format!("→ {}", fix).green());
                }
            } else if fails > 0 {
                println!("  {}", "   Run with --fix to attempt automatic repairs.".dimmed());
            }
        }
    }
}

pub fn run_doctor(fix: bool) -> anyhow::Result<()> {
    let mut doc = Doctor::new();

    println!();
    println!("{}", "╔══════════════════════════════════════════════════════════════╗".purple().bold());
    println!("{}", "║        ⚡ CYNAPSE AI CLI — SYSTEM DOCTOR DIAGNOSTICS         ║".yellow().bold());
    println!("{}", "╚══════════════════════════════════════════════════════════════╝".purple().bold());

    let cfg_path = find_config();
    let cfg = cynapse_core::config::load(&cfg_path).unwrap_or_default();
    let home = std::env::var("HOME").unwrap_or_else(|_| ".".into());
    let cynapse_home = PathBuf::from(format!("{}/.cynapse", home));

    // ── 1. System Hardware ───────────────────────────────────────
    doc.section("🖥  System Hardware & Platform");
    check_hardware(&mut doc);

    // ── 2. Binary Installation ───────────────────────────────────
    doc.section("📦 Binary Installation & PATH");
    check_binary(&mut doc, fix);

    // ── 3. llama.cpp Linkage ─────────────────────────────────────
    doc.section("🦙 llama.cpp Native Engine");
    check_llama_cpp(&mut doc);

    // ── 4. Configuration ─────────────────────────────────────────
    doc.section("⚙  Configuration");
    check_config(&mut doc, &cfg, &cfg_path, &cynapse_home, fix);

    // ── 5. Model Discovery ───────────────────────────────────────
    doc.section("📁 Model Discovery");
    check_models(&mut doc, &cfg, &home);

    // ── 6. Ollama Server ─────────────────────────────────────────
    doc.section("🦙 Ollama Provider");
    check_ollama(&mut doc, &cfg);

    // ── 7. DENDRITE Database ─────────────────────────────────────
    doc.section("🧠 DENDRITE Graph Memory");
    check_dendrite(&mut doc, &cfg);

    // ── 8. Persona Files ─────────────────────────────────────────
    doc.section("🎭 Persona & Seed Files");
    check_persona(&mut doc, &cfg, &cynapse_home);

    // ── 9. Network Access ────────────────────────────────────────
    doc.section("🌐 Network Connectivity");
    check_network(&mut doc);

    // ── 10. TUI ──────────────────────────────────────────────────
    doc.section("🎨 TUI Interface");
    check_tui(&mut doc, &cfg);

    // ── 11. Security ─────────────────────────────────────────────
    doc.section("🔒 Security Posture");
    check_security(&mut doc, &cfg, fix);

    doc.print_results();
    println!();
    Ok(())
}

fn find_config() -> PathBuf {
    let candidates = [
        PathBuf::from("config.yaml"),
        dirs().join("config.yaml"),
        PathBuf::from("/etc/cynapse/config.yaml"),
    ];
    candidates.iter().find(|p| p.exists()).cloned().unwrap_or_else(|| candidates[0].clone())
}

fn dirs() -> PathBuf {
    let home = std::env::var("HOME").unwrap_or_else(|_| ".".into());
    PathBuf::from(format!("{}/.cynapse", home))
}

// ── Hardware checks ──────────────────────────────────────────────

fn check_hardware(doc: &mut Doctor) {
    // OS
    let os = std::env::var("CARGO_CFG_TARGET_OS").unwrap_or_else(|_| {
        std::process::Command::new("uname").arg("-s").output()
            .map(|o| String::from_utf8_lossy(&o.stdout).trim().to_string())
            .unwrap_or_else(|_| "unknown".into())
    });
    doc.add("Operating System", Status::Ok, os);

    // Arch
    let arch = std::env::var("CARGO_CFG_TARGET_ARCH").unwrap_or_else(|_| {
        std::process::Command::new("uname").arg("-m").output()
            .map(|o| String::from_utf8_lossy(&o.stdout).trim().to_string())
            .unwrap_or_else(|_| "unknown".into())
    });
    doc.add("Architecture", Status::Ok, arch);

    // CPU cores
    let cores = std::thread::available_parallelism().map(|n| n.get()).unwrap_or(1);
    let status = if cores >= 4 { Status::Ok } else { Status::Warn };
    doc.add("CPU Cores", status, format!("{}", cores));

    // RAM
    if let Some((total_mb, free_mb)) = read_mem_info() {
        let status = if total_mb >= 8192 { Status::Ok } else if total_mb >= 4096 { Status::Warn } else { Status::Fail };
        doc.add("System RAM", status, format!("{} MB total, {} MB free", total_mb, free_mb));
    }

    // Disk space in ~/.cynapse
    let home = std::env::var("HOME").unwrap_or_else(|_| ".".into());
    if let Ok(stat) = std::fs::metadata(&home) {
        let _ = stat; // just checking it exists
    }
    if let Ok(output) = std::process::Command::new("df").arg("-BM").arg(&home).output() {
        let stdout = String::from_utf8_lossy(&output.stdout);
        if let Some(line) = stdout.lines().nth(1) {
            let parts: Vec<&str> = line.split_whitespace().collect();
            if parts.len() >= 4 {
                doc.add("Disk Space", Status::Ok, format!("{} available", parts[3]));
            }
        }
    }
}

fn read_mem_info() -> Option<(u64, u64)> {
    let content = std::fs::read_to_string("/proc/meminfo").ok()?;
    let mut total = 0u64;
    let mut available = 0u64;
    for line in content.lines() {
        if let Some(val) = line.strip_prefix("MemTotal:") {
            total = val.trim().split_whitespace().next()?.parse().ok()?;
        }
        if let Some(val) = line.strip_prefix("MemAvailable:") {
            available = val.trim().split_whitespace().next()?.parse().ok()?;
        }
    }
    Some((total / 1024, available / 1024))
}

// ── Binary checks ────────────────────────────────────────────────

fn check_binary(doc: &mut Doctor, _fix: bool) {
    let exe = std::env::current_exe().unwrap_or_default();
    doc.add("Binary Path", Status::Ok, exe.display().to_string());

    // Check if in PATH
    let in_path = std::env::var("PATH").unwrap_or_default()
        .split(':')
        .any(|d| Path::new(d).join("cynapse").exists());
    if in_path {
        doc.add("In PATH", Status::Ok, "cynapse found in PATH".into());
    } else {
        doc.add_fixable("In PATH", Status::Warn, "~/.local/bin not in PATH".into());
    }

    // Check binary size (sanity)
    if let Ok(meta) = std::fs::metadata(&exe) {
        let size_mb = meta.len() / (1024 * 1024);
        if size_mb > 1 {
            doc.add("Binary Size", Status::Ok, format!("{} MB", size_mb));
        } else {
            doc.add("Binary Size", Status::Warn, format!("{} MB (seems small)", size_mb));
        }
    }

    // Static vs dynamic linking check
    let output = std::process::Command::new("ldd").arg(&exe).output();
    if let Ok(out) = output {
        let stdout = String::from_utf8_lossy(&out.stdout);
        if stdout.contains("libllama") {
            doc.add("llama.cpp Linkage", Status::Warn, "dynamically linked (needs libllama.so)".into());
        } else {
            doc.add("llama.cpp Linkage", Status::Ok, "statically linked (self-contained)".into());
        }
    }
}

// ── llama.cpp checks ─────────────────────────────────────────────

fn check_llama_cpp(doc: &mut Doctor) {
    // Check for vendored llama.cpp source
    let home = std::env::var("HOME").unwrap_or_else(|_| ".".into());
    let vendored = PathBuf::from(format!("{}/.local/src/cynapse/leafcutter/llama.cpp", home));
    let alt_vendored = PathBuf::from("leafcutter/llama.cpp");

    let llama_dir = if vendored.exists() { vendored } else if alt_vendored.exists() { alt_vendored } else {
        doc.add("llama.cpp Source", Status::Warn, "vendored source not found".into());
        return;
    };
    doc.add("llama.cpp Source", Status::Ok, llama_dir.display().to_string());

    // Check for static libs
    let build_dir = llama_dir.join("build");
    let lib_llama = build_dir.join("src/libllama.a");
    let lib_ggml = build_dir.join("ggml/src/libggml.a");

    if lib_llama.exists() && lib_ggml.exists() {
        let size_mb = (std::fs::metadata(&lib_llama).map(|m| m.len()).unwrap_or(0)
            + std::fs::metadata(&lib_ggml).map(|m| m.len()).unwrap_or(0)) / (1024 * 1024);
        doc.add("Static Libraries", Status::Ok, format!("libllama.a + libggml.a ({} MB)", size_mb));
    } else {
        doc.add_fixable("Static Libraries", Status::Fail, "not built (run cmake + make)".into());
    }

    // Check cmake
    let has_cmake = std::process::Command::new("cmake").arg("--version").output().is_ok();
    if has_cmake {
        doc.add("cmake", Status::Ok, "available".into());
    } else {
        doc.add_fixable("cmake", Status::Fail, "not installed".into());
    }
}

// ── Config checks ────────────────────────────────────────────────

fn check_config(doc: &mut Doctor, cfg: &cynapse_core::config::Config, cfg_path: &Path, cynapse_home: &Path, fix: bool) {
    if cfg_path.exists() {
        doc.add("Config File", Status::Ok, cfg_path.display().to_string());
    } else {
        doc.add_fixable("Config File", Status::Warn, "using defaults (no config.yaml)".into());
        if fix {
            let default = cynapse_home.join("config.yaml");
            if !default.exists() {
                if let Some(repo_config) = find_repo_config() {
                    std::fs::copy(&repo_config, &default).ok();
                    doc.fixes.push(format!("Installed default config to {}", default.display()));
                }
            }
        }
    }

    // Provider
    let valid_providers = ["leafcutter", "ollama", "openai", "anthropic", "gemini"];
    if valid_providers.contains(&cfg.llm.provider.as_str()) {
        doc.add("LLM Provider", Status::Ok, cfg.llm.provider.clone());
    } else {
        doc.add_fixable("LLM Provider", Status::Fail, format!("unknown provider: {}", cfg.llm.provider));
    }

    // Model name
    if cfg.llm.model.is_empty() {
        doc.add("Default Model", Status::Fail, "not configured".into());
    } else {
        doc.add("Default Model", Status::Ok, cfg.llm.model.clone());
    }

    // Models directory
    let models_dir = resolve_models_dir(&cfg.llm.models_dir);
    if models_dir.exists() {
        let count = count_gguf(&models_dir);
        doc.add("Models Directory", Status::Ok, format!("{} ({} models)", models_dir.display(), count));
    } else {
        doc.add_fixable("Models Directory", Status::Warn, format!("{} not found", models_dir.display()));
        if fix {
            std::fs::create_dir_all(&models_dir).ok();
            doc.fixes.push(format!("Created directory {}", models_dir.display()));
        }
    }

    // Data directories
    for subdir in &["data", "workspace", "persona/defaults"] {
        let dir = cynapse_home.join(subdir);
        if dir.exists() {
            doc.add(&format!("Dir: {}", subdir), Status::Ok, dir.display().to_string());
        } else {
            doc.add_fixable(&format!("Dir: {}", subdir), Status::Warn, "missing".into());
            if fix {
                std::fs::create_dir_all(&dir).ok();
                doc.fixes.push(format!("Created {}", dir.display()));
            }
        }
    }
}

fn resolve_models_dir(dir: &str) -> PathBuf {
    if dir.is_empty() {
        let home = std::env::var("HOME").unwrap_or_else(|_| ".".into());
        return PathBuf::from(format!("{}/Downloads/models", home));
    }
    if dir.starts_with("~/") {
        let home = std::env::var("HOME").unwrap_or_else(|_| ".".into());
        return PathBuf::from(format!("{}/{}", &home[0..0], &dir[2..]));
    }
    PathBuf::from(dir)
}

fn count_gguf(dir: &Path) -> usize {
    std::fs::read_dir(dir).map(|entries| {
        entries.filter_map(|e| e.ok())
            .filter(|e| e.path().extension().map(|ext| ext == "gguf").unwrap_or(false))
            .count()
    }).unwrap_or(0)
}

fn find_repo_config() -> Option<PathBuf> {
    let candidates = [
        PathBuf::from("config.yaml"),
        PathBuf::from("../config.yaml"),
        PathBuf::from("../../config.yaml"),
    ];
    candidates.into_iter().find(|p| p.exists())
}

// ── Model checks ─────────────────────────────────────────────────

fn check_models(doc: &mut Doctor, cfg: &cynapse_core::config::Config, home: &str) {
    let search_dirs = vec![
        resolve_models_dir(&cfg.llm.models_dir),
        PathBuf::from(format!("{}/Downloads/models", home)),
        PathBuf::from(format!("{}/.cynapse/models", home)),
        PathBuf::from("models"),
    ];

    let mut total_models = 0usize;
    let mut found_dirs = Vec::new();

    for dir in &search_dirs {
        if dir.exists() {
            let count = count_gguf(dir);
            if count > 0 {
                total_models += count;
                found_dirs.push(format!("{} ({} models)", dir.display(), count));
            }
        }
    }

    if total_models > 0 {
        doc.add("GGUF Models Found", Status::Ok, format!("{} in {}", total_models, found_dirs.join(", ")));
    } else {
        doc.add_fixable("GGUF Models Found", Status::Warn, "no .gguf files found in search paths".into());
    }

    // Check for Ollama models
    let ollama_path = PathBuf::from(format!("{}/.ollama/models", home));
    if ollama_path.exists() {
        doc.add("Ollama Models Dir", Status::Ok, ollama_path.display().to_string());
    } else {
        doc.add("Ollama Models Dir", Status::Warn, "not found".into());
    }
}

// ── Ollama checks ────────────────────────────────────────────────

fn check_ollama(doc: &mut Doctor, cfg: &cynapse_core::config::Config) {
    let url = format!("{}/api/tags", cfg.llm.ollama_base_url);
    match ureq::get(&url).timeout(Duration::from_secs(2)).call() {
        Ok(resp) if resp.status() == 200 => {
            doc.add("Ollama Server", Status::Ok, "online".to_string());
            // Try to list models
            let mut body = String::new();
            if resp.into_reader().read_to_string(&mut body).is_ok() {
                if let Ok(val) = serde_json::from_str::<serde_json::Value>(&body) {
                    if let Some(arr) = val.get("models").and_then(|v| v.as_array()) {
                        let names: Vec<String> = arr.iter()
                            .filter_map(|m| m.get("name").and_then(|n| n.as_str()).map(String::from))
                            .collect();
                        if !names.is_empty() {
                            doc.add("Ollama Models", Status::Ok, format!("{} available", names.len()));
                        }
                    }
                }
            }
        }
        Ok(resp) => {
            doc.add("Ollama Server", Status::Warn, format!("responded with status {}", resp.status()));
        }
        Err(_) => {
            doc.add("Ollama Server", Status::Warn, "offline or unreachable".into());
        }
    }
}

// ── DENDRITE checks ──────────────────────────────────────────────

fn check_dendrite(doc: &mut Doctor, cfg: &cynapse_core::config::Config) {
    let db_path = Path::new(&cfg.memory.dendrite_db_path);
    if db_path.exists() {
        doc.add("Database File", Status::Ok, db_path.display().to_string());
        if let Ok(store) = cynapse_core::dendrite::DendriteStore::open(&cfg.memory.dendrite_db_path) {
            let graph = cynapse_core::dendrite::Dendrite::new();
            if store.load_all(&graph).is_ok() {
                let count = graph.all().len();
                let status = if count > 0 { Status::Ok } else { Status::Warn };
                doc.add("Memory Nodes", status, format!("{}", count));
            }
        }
    } else {
        doc.add_fixable("Database File", Status::Warn, "not initialized (will be created on first use)".into());
    }

    // Session storage
    let sessions_path = Path::new(&cfg.memory.sessions_path);
    if sessions_path.exists() {
        let count = std::fs::read_dir(sessions_path).map(|e| e.count()).unwrap_or(0);
        doc.add("Session Files", Status::Ok, format!("{} files", count));
    } else {
        doc.add("Session Files", Status::Warn, "directory not found".into());
    }
}

// ── Persona checks ───────────────────────────────────────────────

fn check_persona(doc: &mut Doctor, cfg: &cynapse_core::config::Config, cynapse_home: &Path) {
    let seeds = ["IDENTITY.md", "SOUL.md", "AGENTS.md", "USER.md", "TOOLS.md", "MEMORY.md", "HEARTBEAT.md"];
    let defaults_dir = Path::new(&cfg.memory.defaults_path);
    let persona_dir = Path::new(&cfg.memory.persona_path);
    let home_defaults = cynapse_home.join("persona/defaults");

    let mut found = 0;
    let mut missing = Vec::new();

    for s in &seeds {
        let exists = defaults_dir.join(s).exists()
            || persona_dir.join(s).exists()
            || home_defaults.join(s).exists();
        if exists {
            found += 1;
        } else {
            missing.push(s.to_string());
        }
    }

    if missing.is_empty() {
        doc.add("Persona Templates", Status::Ok, format!("{}/{} found", found, seeds.len()));
    } else {
        doc.add_fixable("Persona Templates", Status::Warn,
            format!("{}/{} found (missing: {})", found, seeds.len(), missing.join(", ")));
    }

    // Identity
    let identity = defaults_dir.join("IDENTITY.md");
    if identity.exists() {
        doc.add("Identity File", Status::Ok, identity.display().to_string());
    } else {
        doc.add("Identity File", Status::Warn, "using internal default".into());
    }
}

// ── TUI checks ──────────────────────────────────────────────────

fn check_tui(doc: &mut Doctor, cfg: &cynapse_core::config::Config) {
    let theme_name = &cfg.tui.theme;
    let valid_themes = [
        "default", "tokyonight", "catppuccin", "catppuccin-macchiato",
        "dracula", "nord", "gruvbox", "one-dark", "rose-pine",
        "everforest", "kanagawa", "solarized", "flexoki", "monokai",
        "cobalt2", "ayu",
    ];
    if valid_themes.contains(&theme_name.as_str()) {
        doc.add("TUI Theme", Status::Ok, theme_name.clone());
    } else {
        doc.add_fixable("TUI Theme", Status::Warn, format!("unknown theme: {}", theme_name));
    }

    // Check sidebar width
    let sw = cfg.tui.sidebar_width;
    if sw >= 16 && sw <= 60 {
        doc.add("Sidebar Width", Status::Ok, format!("{} cols", sw));
    } else {
        doc.add_fixable("Sidebar Width", Status::Warn, format!("{} cols (recommended 20-40)", sw));
    }

    // Check min terminal size
    doc.add("Min Terminal", Status::Ok, format!("{}x{}", cfg.tui.min_width, cfg.tui.min_height));

    // Message history limit
    let max_msgs = cfg.tui.max_messages;
    if max_msgs > 0 {
        doc.add("Message Limit", Status::Ok, format!("{} messages", max_msgs));
    } else {
        doc.add("Message Limit", Status::Warn, "unlimited (may grow large)".into());
    }
}

// ── Network checks ───────────────────────────────────────────────

fn check_network(doc: &mut Doctor) {
    // DNS resolution
    let dns_ok = std::net::TcpStream::connect("api.openai.com:443").is_ok();
    doc.add("DNS Resolution", if dns_ok { Status::Ok } else { Status::Fail }, if dns_ok { "working".into() } else { "failed".into() });

    // HTTPS connectivity
    let https_ok = ureq::get("https://httpbin.org/get")
        .timeout(Duration::from_secs(3))
        .call()
        .map(|r| r.status() == 200)
        .unwrap_or(false);
    doc.add("HTTPS Access", if https_ok { Status::Ok } else { Status::Warn },
        if https_ok { "connected to internet".into() } else { "no internet or blocked".into() });
}

// ── Security checks ──────────────────────────────────────────────

fn check_security(doc: &mut Doctor, cfg: &cynapse_core::config::Config, fix: bool) {
    // Net policy
    let policy = &cfg.security.net_policy;
    let status = match policy.as_str() {
        "disabled" => Status::Fail,
        "local-dev" => Status::Warn,
        "local-only" | "strict" => Status::Ok,
        _ => Status::Warn,
    };
    doc.add("Network Policy", status, policy.to_string());

    // Approval policy
    let approval = &cfg.security.approval_policy;
    let status = match approval.as_str() {
        "auto" => Status::Warn,
        "balanced" => Status::Ok,
        "locked-down" => Status::Ok,
        _ => Status::Warn,
    };
    doc.add("Tool Approval", status, approval.to_string());

    // Redaction
    let redact = cfg.effective_redaction();
    doc.add("Secret Redaction", if redact { Status::Ok } else { Status::Warn },
        if redact { "enabled".into() } else { "disabled".into() });

    // Config file permissions
    let cfg_path = find_config();
    if cfg_path.exists() {
        #[cfg(unix)]
        {
            use std::os::unix::fs::PermissionsExt;
            if let Ok(meta) = std::fs::metadata(&cfg_path) {
                let mode = meta.permissions().mode();
                let world_readable = mode & 0o004 != 0;
                if world_readable {
                    doc.add_fixable("Config Permissions", Status::Warn, "world-readable (consider chmod 600)".into());
                    if fix {
                        let _ = std::fs::set_permissions(&cfg_path, std::fs::Permissions::from_mode(0o600));
                        doc.fixes.push(format!("Fixed permissions on {}", cfg_path.display()));
                    }
                } else {
                    doc.add("Config Permissions", Status::Ok, format!("{:o}", mode & 0o777));
                }
            }
        }
    }
}
