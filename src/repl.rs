//! Cynapse Native Engine CLI & REPL.
//!
//! Powered directly by Leafcutter's native LLM inference engine (`leafcutter::inference::engine::Engine`)
//! with zero wrapper overhead. Features dynamic greetings/farewells, in-session model hot-swapping (`/model`),
//! slash command menu (`/help`), thinking mode toggle (`/think`), and color-graded reasoning vs response streaming.
//!
//! ### Customizing Greetings & Farewells
//! - To add or edit greetings: Modify the [`CYNAPSE_GREETINGS`] array below in [`src/repl.rs`](file:///home/orangepi/Documents/portfolio/cynapse/src/repl.rs#L38).
//! - To add or edit farewells: Modify the [`CYNAPSE_FAREWELLS`] array below in [`src/repl.rs`](file:///home/orangepi/Documents/portfolio/cynapse/src/repl.rs#L53).

use std::io::{self, Write};
use std::path::{Path, PathBuf};
use std::sync::Arc;
use std::time::{Duration, Instant};

use anyhow::{Context, Result};
use colored::*;
use rustyline::DefaultEditor;

use cynapse_core::agent::Agent;
use cynapse_core::approval;
use cynapse_core::config::{self, Config};
use cynapse_core::llm;
use cynapse_core::netguard;
use cynapse_core::persona::Persona;
use cynapse_core::session::Manager;
use cynapse_core::tools;

use leafcutter::detect::{choose_tier, HardwareInfo};
use leafcutter::inference::engine::Engine;
use leafcutter::model::gguf::GGUFValue;
use leafcutter::profiles::{render_chat_prompt, resolve_profile, ModelProfile};

use crate::cli::ReplCmd;

// ─── Custom Greetings & Farewells Configuration ──────────────────────────────

pub const CYNAPSE_GREETINGS: &[&str] = &[
    "Greetings! I am right here beside you. How may I serve and support your work today?",
    "Welcome back! May wisdom, clarity, and peace guide our conversation today. What is on your mind?",
    "Hello my friend! Ready whenever you are. How can I assist your coding or architecture goals?",
    "Shalom! I'm here to lend a helping hand and thoughtful counsel. Where should we begin today?",
    "Welcome! The session is full of possibilities. What shall we build or solve right now?",
    "Good to see you! Ready to dive in whenever you are—let's accomplish something great together.",
    "Grace and peace to you today! I am tuned in and ready to assist with your project.",
    "Ah, welcome back companion! What meaningful task shall we tackle together today?",
    "Hello! It is a joy to collaborate with you. How can I help make your workflow smooth and productive?",
    "Welcome friend! Whether querying graph memory or writing rust code, I stand ready to assist.",
];

pub const CYNAPSE_FAREWELLS: &[&str] = &[
    "I really enjoyed our conversation! Go with strength and wisdom—talk later!",
    "Until next time! May your code be bug-free and your work fruitful.",
    "It was a pleasure helping you today. Take care, and I will be right here whenever you return!",
    "Farewell for now! May your path be clear and your effort blessed. Talk soon!",
    "Safe travels on your work today! I enjoyed our session—reach out whenever you need me again.",
    "Goodbye for now, my friend! Keep striving with courage and grace. Talk later!",
    "Rest well and go in peace! I will be waiting right here when you return.",
    "Farewell, dear friend! May clarity attend your steps until we speak again.",
];

pub fn get_random_greeting() -> &'static str {
    let now = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|d| d.as_nanos() as usize)
        .unwrap_or(0);
    CYNAPSE_GREETINGS[now % CYNAPSE_GREETINGS.len()]
}

pub fn get_random_farewell() -> &'static str {
    let now = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|d| d.as_nanos() as usize)
        .unwrap_or(0);
    CYNAPSE_FAREWELLS[now % CYNAPSE_FAREWELLS.len()]
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ThinkingMode {
    /// Stream thinking steps in dim purple, response in gold.
    Dim,
    /// Hide internal thinking scratchpad output, stream answer in gold.
    Hide,
}

// ─── Entry Point ─────────────────────────────────────────────────────────────

pub fn run_repl(cmd: ReplCmd) -> Result<()> {
    let cfg_path = Path::new(&cmd.config);
    let cfg = config::load(cfg_path).unwrap_or_default();

    if cfg.llm.provider == "leafcutter" {
        run_native_engine_repl(&cfg, cmd)
    } else {
        let rt = tokio::runtime::Runtime::new()?;
        rt.block_on(async move { run_fallback_repl(&cfg, cmd).await })
    }
}

// ─── Native Leafcutter Engine Direct CLI ────────────────────────────────────

fn run_native_engine_repl(cfg: &Config, cmd: ReplCmd) -> Result<()> {
    let current_model_path = resolve_gguf_path(cfg)?;
    let model_path = PathBuf::from(&current_model_path);
    let mut model_name = model_path
        .file_name()
        .map(|s| s.to_string_lossy().to_string())
        .unwrap_or_else(|| cfg.llm.model.clone());

    let mut engine = Engine::load(&current_model_path)
        .map_err(|e| anyhow::anyhow!("failed loading engine model '{}': {e}", model_path.display()))?;

    let hw = HardwareInfo::probe();
    let file_bytes = std::fs::metadata(&model_path).map(|m| m.len()).unwrap_or(0);
    let file_mb = file_bytes as f64 / (1024.0 * 1024.0);
    let tier = choose_tier(hw.gpu, hw.ram_available_mb, file_bytes, false);
    let mut profile = resolve_profile(&engine.model.file.metadata, None);
    let mut info = engine.config.clone();

    let arch_str = engine
        .model
        .file
        .metadata
        .get("general.architecture")
        .and_then(|v| match v {
            GGUFValue::String(s) => Some(s.as_str()),
            _ => None,
        })
        .unwrap_or("Qwen3.5")
        .to_string();

    let mut temp = cfg.llm.temperature as f32;
    let top_p = 0.95f32;
    let mut max_tokens = cfg.llm.max_tokens as usize;
    let mut thinking_mode = ThinkingMode::Dim;

    print_native_banner(
        &model_name,
        &arch_str,
        info.num_hidden_layers,
        info.hidden_size,
        file_mb,
        &hw,
        tier.number(),
        tier.label(),
        &profile.name,
        temp,
        top_p,
        max_tokens,
    );

    let greeting = get_random_greeting();
    println!("\n{}", format!("💬 {}", greeting).purple().bold());

    let mut conversation: Vec<(String, String)> = Vec::new();

    if let Some(prompt) = cmd.prompt {
        execute_native_turn(&mut engine, &profile, &model_name, &prompt, &conversation, temp, top_p, max_tokens, thinking_mode)?;
        return Ok(());
    }

    let mut rl = DefaultEditor::new().ok();
    leafcutter::cpu_monitor::start();

    loop {
        let prompt_str = format!("\n{} ", gold(">>>"));
        let input = match read_line(&mut rl, &prompt_str) {
            Ok(line) => line,
            Err(_) => break,
        };

        let trimmed = input.trim();
        if trimmed.is_empty() {
            continue;
        }

        if trimmed.starts_with('/') {
            let parts: Vec<&str> = trimmed.splitn(3, ' ').collect();
            match parts[0] {
                "/bye" | "/quit" | "/exit" => {
                    let farewell = get_random_farewell();
                    println!("\n{}", format!("👋 {}", farewell).yellow().bold());
                    break;
                }
                "/clear" => {
                    conversation.clear();
                    engine.kv_cache.clear();
                    engine.ssm_cache.clear();
                    engine.deltanet_cache.clear();
                    engine.seq_offset = 0;
                    eprintln!("{}", dim_purple("[context cleared — engine caches flushed]"));
                    continue;
                }
                "/think" => {
                    if parts.len() < 2 {
                        let status = match thinking_mode {
                            ThinkingMode::Dim => "dim (stream thinking in dim purple)",
                            ThinkingMode::Hide => "hide (suppress scratchpad output)",
                        };
                        println!("Current thinking mode: {status}. Usage: /think dim or /think hide");
                    } else {
                        match parts[1].trim().to_lowercase().as_str() {
                            "hide" | "off" => {
                                thinking_mode = ThinkingMode::Hide;
                                println!("{}", "[thinking mode = HIDE (scratchpad output suppressed)]".green());
                            }
                            "dim" | "on" | "show" => {
                                thinking_mode = ThinkingMode::Dim;
                                println!("{}", "[thinking mode = DIM (thinking in purple, response in gold)]".green());
                            }
                            _ => println!("Usage: /think dim (show in purple) or /think hide (suppress scratchpad)"),
                        }
                    }
                    continue;
                }
                "/models" | "/ls" | "/list" => {
                    print_available_models(cfg);
                    continue;
                }
                "/model" => {
                    if parts.len() < 2 {
                        eprintln!("{}", "Usage: /model <name_or_number> (e.g. /model 1 or /model qwen)".yellow());
                        print_available_models(cfg);
                    } else {
                        let target = parts[1].trim();
                        match reload_model(target, cfg, &hw) {
                            Ok((new_engine, _new_path, new_name, new_profile, new_info, new_mb, new_tier, new_arch)) => {
                                engine = new_engine;
                                model_name = new_name;
                                profile = new_profile;
                                info = new_info;

                                conversation.clear();
                                println!("{}", format!("\n✨ Swapped active model to: {}", model_name).green().bold());
                                print_native_banner(
                                    &model_name,
                                    &new_arch,
                                    info.num_hidden_layers,
                                    info.hidden_size,
                                    new_mb,
                                    &hw,
                                    new_tier.number(),
                                    new_tier.label(),
                                    &profile.name,
                                    temp,
                                    top_p,
                                    max_tokens,
                                );
                            }
                            Err(e) => {
                                eprintln!("{}", format!("Failed to swap model: {e:#}").red());
                            }
                        }
                    }
                    continue;
                }
                "/set" => {
                    if parts.len() < 3 {
                        println!("Usage: /set temp <value> or /set max <value>");
                    } else {
                        match parts[1] {
                            "temp" | "temperature" => {
                                if let Ok(val) = parts[2].parse::<f32>() {
                                    temp = val;
                                    println!("{}", format!("[temperature = {:.2}]", temp).green());
                                } else {
                                    println!("Invalid temperature value.");
                                }
                            }
                            "max" | "maxtokens" => {
                                if let Ok(val) = parts[2].parse::<usize>() {
                                    max_tokens = val;
                                    println!("{}", format!("[max_tokens = {}]", max_tokens).green());
                                } else {
                                    println!("Invalid max_tokens value.");
                                }
                            }
                            _ => println!("Unknown parameter. Use /set temp <val> or /set max <val>"),
                        }
                    }
                    continue;
                }
                "/ps" => {
                    let cur_rss = get_current_rss_mb();
                    let peak_rss = get_peak_rss_mb();
                    println!(
                        "{}",
                        format!(
                            "📊 Engine RAM footprint: {} (peak {})",
                            format_rss(cur_rss),
                            format_rss(peak_rss)
                        )
                        .purple()
                        .bold()
                    );
                    continue;
                }
                "/help" | "/?" => {
                    print_help_menu();
                    continue;
                }
                _ => {
                    println!("Unknown command. Type /help for assistance.");
                    continue;
                }
            }
        }

        if let Err(e) = execute_native_turn(
            &mut engine,
            &profile,
            &model_name,
            trimmed,
            &conversation,
            temp,
            top_p,
            max_tokens,
            thinking_mode,
        ) {
            eprintln!("\n{}", format!("Engine execution error: {e:#}").red());
        }

        conversation.push(("user".into(), trimmed.to_string()));
    }

    Ok(())
}

fn execute_native_turn(
    engine: &mut Engine,
    profile: &ModelProfile,
    model_name: &str,
    user_msg: &str,
    history: &[(String, String)],
    temp: f32,
    top_p: f32,
    max_tokens: usize,
    thinking_mode: ThinkingMode,
) -> Result<()> {
    let formatted_prompt = render_chat_prompt(profile, user_msg, history);
    let prompt_tokens = if let Some(tok) = engine.tokenizer_from_model() {
        tok.encode(&formatted_prompt, true)
    } else {
        Vec::new()
    };

    if prompt_tokens.is_empty() {
        anyhow::bail!("failed to tokenize prompt");
    }

    let gen_start = Instant::now();
    let mut generated_text = String::new();
    let stop_token_ids: Vec<usize> = profile.stop_tokens.iter().map(|s| s.0).collect();

    let mut in_thinking = profile.opens_with_thinking;
    let mut thinking_prefix_shown = false;
    let mut thinking_tail = String::new();

    println!();
    let generated_ids = engine.generate_streaming_with_stops(
        &prompt_tokens,
        max_tokens,
        temp,
        top_p,
        &stop_token_ids,
        |_id, chunk| {
            thinking_tail.push_str(chunk);

            // Strip thinking header prefixes as soon as they appear in thinking_tail
            while thinking_tail.starts_with("<think>")
                || thinking_tail.starts_with("Thinking Process:")
                || thinking_tail.starts_with("Thinking process:")
                || thinking_tail.starts_with("Thinking:")
                || (thinking_tail.starts_with('\n') && in_thinking && !thinking_prefix_shown)
            {
                if let Some(rest) = thinking_tail.strip_prefix("<think>") {
                    thinking_tail = rest.to_string();
                } else if let Some(rest) = thinking_tail.strip_prefix("Thinking Process:") {
                    thinking_tail = rest.to_string();
                } else if let Some(rest) = thinking_tail.strip_prefix("Thinking process:") {
                    thinking_tail = rest.to_string();
                } else if let Some(rest) = thinking_tail.strip_prefix("Thinking:") {
                    thinking_tail = rest.to_string();
                } else if let Some(rest) = thinking_tail.strip_prefix('\n') {
                    thinking_tail = rest.to_string();
                }
            }

            // HIDE Mode: Discard thinking scratchpad silently, output answer only
            if thinking_mode == ThinkingMode::Hide {
                if in_thinking {
                    if thinking_tail.contains("</think>") {
                        if let Some(pos) = thinking_tail.find("</think>") {
                            thinking_tail = thinking_tail[pos + 8..].to_string();
                        }
                        in_thinking = false;
                    } else if thinking_tail.contains("\n\n") && thinking_tail.len() > 60 {
                        if let Some(pos) = thinking_tail.find("\n\n") {
                            thinking_tail = thinking_tail[pos + 2..].to_string();
                        }
                        in_thinking = false;
                    } else {
                        return true;
                    }
                }
                if !thinking_tail.is_empty() {
                    print!("{}", gold(&thinking_tail));
                    let _ = io::stdout().flush();
                    generated_text.push_str(&thinking_tail);
                    thinking_tail.clear();
                }
                return true;
            }

            // DIM Mode: Stream thinking steps in dim purple, answer in gold
            if in_thinking {
                if let Some(pos) = thinking_tail.find("</think>") {
                    let (pre, rest) = thinking_tail.split_at(pos);
                    if !pre.trim().is_empty() {
                        if !thinking_prefix_shown {
                            print!("{}", dim_purple("💭 "));
                            thinking_prefix_shown = true;
                        }
                        print!("{}", dim_purple(pre.trim_start()));
                    }
                    println!();
                    thinking_tail = rest[8..].to_string();
                    in_thinking = false;
                } else if thinking_tail.contains("\n\n") && thinking_tail.len() > 60 {
                    if let Some(pos) = thinking_tail.find("\n\n") {
                        let (pre, rest) = thinking_tail.split_at(pos);
                        if !pre.trim().is_empty() {
                            if !thinking_prefix_shown {
                                print!("{}", dim_purple("💭 "));
                                thinking_prefix_shown = true;
                            }
                            print!("{}", dim_purple(pre.trim_start()));
                        }
                        println!();
                        thinking_tail = rest[2..].to_string();
                        in_thinking = false;
                    }
                } else {
                    let keep = floor_char_boundary(&thinking_tail, thinking_tail.len().saturating_sub(12));
                    if keep > 0 {
                        let (emit, rest) = thinking_tail.split_at(keep);
                        if !emit.is_empty() {
                            if !thinking_prefix_shown {
                                print!("{}", dim_purple("💭 "));
                                thinking_prefix_shown = true;
                            }
                            print!("{}", dim_purple(emit));
                        }
                        thinking_tail = rest.to_string();
                    }
                }
                let _ = io::stdout().flush();
                return true;
            }

            if !thinking_tail.is_empty() {
                print!("{}", gold(&thinking_tail));
                let _ = io::stdout().flush();
                generated_text.push_str(&thinking_tail);
                thinking_tail.clear();
            }

            true
        },
    );

    let gen_elapsed = gen_start.elapsed();
    let gen_tokens = generated_ids.len();
    let tok_per_sec = if gen_tokens > 0 && gen_elapsed.as_secs_f64() > 0.0 {
        gen_tokens as f64 / gen_elapsed.as_secs_f64()
    } else {
        0.0
    };

    let peak_rss = get_peak_rss_mb();
    let cur_rss = get_current_rss_mb();

    println!();
    println!("{}", dim_purple("─────────────────────────────────────────────────"));
    println!(
        "{} {} {} {} {} {} {}",
        dim_purple(&truncate_str(model_name, 28)),
        dim_purple("|"),
        gold(&format!("out={}", gen_tokens)),
        dim_purple("|"),
        gold(&format!("{:.2}s", gen_elapsed.as_secs_f64())),
        dim_purple("|"),
        gold(&format!(
            "{:.2} tok/s  RAM {} (peak {})",
            tok_per_sec,
            format_rss(cur_rss),
            format_rss(peak_rss)
        ))
    );

    Ok(())
}

fn print_native_banner(
    model_name: &str,
    arch: &str,
    layers: usize,
    hidden: usize,
    file_mb: f64,
    hw: &HardwareInfo,
    tier_num: u8,
    tier_label: &str,
    profile_name: &str,
    temp: f32,
    top_p: f32,
    max_tokens: usize,
) {
    let npu_suffix = if hw.npu.is_present() { " · NPU active" } else { "" };
    macro_rules! banner_row {
        ($label:expr, $value:expr) => {{
            let val = truncate_str(&$value.to_string(), 34);
            let padded = format!("{:<34}", val);
            eprintln!(
                "  {}  {}: {}{}",
                purple("║"),
                dim_purple($label),
                gold(&padded),
                purple("║")
            );
        }};
    }

    eprintln!();
    eprintln!("  {}", purple("╔══════════════════════════════════════════════╗"));
    eprintln!("  {}", gold(  "║  ⚡ CYNAPSE AI CLI — Native Engine            ║"));
    eprintln!("  {}", purple("╠══════════════════════════════════════════════╣"));
    banner_row!("Model   ", model_name);
    banner_row!("Arch    ", arch);
    banner_row!("Layers  ", format!("{} layers, {} hidden", layers, hidden));
    banner_row!("Size    ", format!("{:.1} MB", file_mb));
    banner_row!(
        "Hardware",
        format!(
            "{} · {} cores · {:.0} GiB free{}",
            hw.os,
            hw.cpu_cores,
            hw.ram_available_mb as f64 / 1024.0,
            npu_suffix
        )
    );
    banner_row!("Tier    ", format!("{} — {}", tier_num, tier_label));
    banner_row!("Profile ", profile_name);
    banner_row!("Temp    ", format!("{:.2}  (top_p={:.2})", temp, top_p));
    banner_row!("Max tok ", max_tokens);
    eprintln!("  {}", purple("╚══════════════════════════════════════════════╝"));
    eprintln!();
    eprintln!(
        "  {} {}",
        dim_purple("Type"),
        gold("/help for commands · /bye to exit")
    );
    eprintln!("  {}", dim_purple("─────────────────────────────────────────────────"));
}

fn print_help_menu() {
    println!(
        "{}",
        "╔══════════════════════════════════════════════════════════════╗"
            .purple()
            .bold()
    );
    println!(
        "{}",
        "║               CYNAPSE AI CLI — COMMAND MENU                  ║"
            .yellow()
            .bold()
    );
    println!(
        "{}",
        "╚══════════════════════════════════════════════════════════════╝"
            .purple()
            .bold()
    );
    println!("  {}", gold("Interactive Commands:"));
    println!("    {} - Show this command menu & capabilities", purple("/help"));
    println!("    {} - List all available local GGUF models", purple("/models"));
    println!("    {} - Hot-swap active model in-session (by index or name)", purple("/model <n|id>"));
    println!("    {} - Toggle thinking scratchpad output (/think dim or /think hide)", purple("/think <dim|hide>"));
    println!("    {} - Adjust sampling temperature (e.g. /set temp 0.7)", purple("/set temp <v>"));
    println!("    {} - Adjust max tokens (e.g. /set max 2048)", purple("/set max <v>"));
    println!("    {} - Flush KV/SSM engine state & reset context", purple("/clear"));
    println!("    {} - Display live RAM footprint vs peak memory", purple("/ps"));
    println!("    {} - Exit interactive CLI session", purple("/bye"));
}

fn print_available_models(cfg: &Config) {
    let models = list_available_models(cfg);
    println!("{}", "\n📦 Available GGUF Models:".purple().bold());
    if models.is_empty() {
        println!("  (No .gguf models found in model directories. Run `cynapse get hf:org/repo` to download)");
    } else {
        for (idx, (name, _path, size_mb)) in models.iter().enumerate() {
            println!(
                "  [{}] {:<45} {:>7.1} MB",
                gold(&(idx + 1).to_string()),
                name.cyan(),
                size_mb
            );
        }
    }
}

fn list_available_models(cfg: &Config) -> Vec<(String, String, f64)> {
    let mut search_dirs = vec![
        cfg.models.models_dir.clone(),
        cfg.llm.models_dir.clone(),
        "./models".into(),
        "../models".into(),
        "../../models".into(),
        "~/Downloads/models".into(),
        "~/Downloads".into(),
        "~/models".into(),
        "~/.leafcutter/models".into(),
        "~/.cache/cynapse/models".into(),
        "~/.cynapse/models".into(),
    ];

    let model_p = Path::new(&cfg.llm.model);
    if let Some(parent) = model_p.parent() {
        if !parent.as_os_str().is_empty() {
            search_dirs.push(parent.to_string_lossy().to_string());
        }
    }

    let mut out = Vec::new();
    let mut seen = std::collections::HashSet::new();

    if let Ok(active_path) = resolve_gguf_path(cfg) {
        let p = Path::new(&active_path);
        if p.exists() && p.extension().and_then(|s| s.to_str()) == Some("gguf") {
            let name = p.file_name().unwrap_or_default().to_string_lossy().to_string();
            seen.insert(name.clone());
            let bytes = std::fs::metadata(p).map(|m| m.len()).unwrap_or(0);
            let mb = bytes as f64 / (1024.0 * 1024.0);
            out.push((name, active_path.clone(), mb));
        }
    }

    for dir_str in search_dirs {
        if dir_str.trim().is_empty() {
            continue;
        }
        let expanded = shellexpand_tilde(&dir_str);
        let dir = Path::new(&expanded);
        if dir.exists() {
            if let Ok(entries) = std::fs::read_dir(dir) {
                for entry in entries.flatten() {
                    let p = entry.path();
                    if p.extension().and_then(|s| s.to_str()) == Some("gguf") {
                        let name = p.file_name().unwrap_or_default().to_string_lossy().to_string();
                        if !seen.contains(&name) {
                            seen.insert(name.clone());
                            let bytes = std::fs::metadata(&p).map(|m| m.len()).unwrap_or(0);
                            let mb = bytes as f64 / (1024.0 * 1024.0);
                            out.push((name, p.to_string_lossy().to_string(), mb));
                        }
                    }
                }
            }
        }
    }

    out
}

#[allow(clippy::type_complexity)]
fn reload_model(
    target: &str,
    cfg: &Config,
    _hw: &HardwareInfo,
) -> Result<(Engine, String, String, ModelProfile, leafcutter::model::loader::ModelConfig, f64, leafcutter::detect::Tier, String)> {
    let models = list_available_models(cfg);
    let resolved_path = if let Ok(idx) = target.parse::<usize>() {
        if idx >= 1 && idx <= models.len() {
            models[idx - 1].1.clone()
        } else {
            anyhow::bail!("Model index out of bounds (1..{})", models.len());
        }
    } else {
        models
            .iter()
            .find(|(name, path, _)| name.to_lowercase().contains(&target.to_lowercase()) || path.to_lowercase().contains(&target.to_lowercase()))
            .map(|(_, path, _)| path.clone())
            .unwrap_or_else(|| target.to_string())
    };

    let p = Path::new(&resolved_path);
    if !p.exists() {
        anyhow::bail!("Model file '{}' not found on disk.", resolved_path);
    }

    let model_name = p.file_name().unwrap_or_default().to_string_lossy().to_string();
    eprintln!("🌿 Swapping engine to model: {} ...", model_name.cyan().bold());

    let engine = Engine::load(&resolved_path)
        .map_err(|e| anyhow::anyhow!("failed loading engine model '{resolved_path}': {e}"))?;

    let fresh_hw = HardwareInfo::probe();
    let file_bytes = std::fs::metadata(p).map(|m| m.len()).unwrap_or(0);
    let file_mb = file_bytes as f64 / (1024.0 * 1024.0);
    let tier = choose_tier(fresh_hw.gpu, fresh_hw.ram_available_mb, file_bytes, false);
    let profile = resolve_profile(&engine.model.file.metadata, None);
    let info = engine.config.clone();

    let arch_str = engine
        .model
        .file
        .metadata
        .get("general.architecture")
        .and_then(|v| match v {
            GGUFValue::String(s) => Some(s.as_str()),
            _ => None,
        })
        .unwrap_or("Qwen3.5")
        .to_string();

    Ok((engine, resolved_path, model_name, profile, info, file_mb, tier, arch_str))
}

// ─── Fallback Async REPL for Non-Leafcutter Providers ──────────────────────

async fn run_fallback_repl(cfg: &Config, cmd: ReplCmd) -> Result<()> {
    let agent = build_agent(cfg)?;

    if let Some(prompt) = cmd.prompt {
        println!("{}", format!("🤖 Single prompt mode: {}", prompt).cyan().bold());
        execute_turn_async(&agent, &prompt).await?;
        return Ok(());
    }

    println!("{}", "╔══════════════════════════════════════════════════════════════╗".purple().bold());
    println!("{}", "║          ⚡ CYNAPSE AI CLI — LIGHTWEIGHT REPL MODE           ║".yellow().bold());
    println!("{}", "╚══════════════════════════════════════════════════════════════╝".purple().bold());
    println!(" Engine: {} | Model: {}", cfg.llm.provider.yellow().bold(), cfg.llm.model.yellow().bold());
    println!(" Type {} for commands, {} or {} to exit.", "/help".cyan(), "/quit".cyan(), "Ctrl+C".cyan());
    println!();

    let mut rl = DefaultEditor::new().ok();

    loop {
        let prompt_str = format!("{}", "cynapse> ".purple().bold());
        let input = match read_line(&mut rl, &prompt_str) {
            Ok(line) => line,
            Err(_) => break,
        };

        let trimmed = input.trim();
        if trimmed.is_empty() {
            continue;
        }

        match trimmed {
            "/quit" | "/exit" | "/bye" => {
                println!("{}", get_random_farewell().yellow().bold());
                break;
            }
            "/clear" => {
                let _ = agent.clear_session();
                println!("{}", "Session cleared.".green());
                continue;
            }
            "/help" => {
                print_help_menu();
                continue;
            }
            _ => {}
        }

        execute_turn_async(&agent, trimmed).await?;
    }

    Ok(())
}

async fn execute_turn_async(agent: &Agent, user_msg: &str) -> Result<()> {
    let start = Instant::now();
    let (mut chunks_rx, mut errors_rx) = agent.process_message_stream(user_msg, Vec::new()).await;

    print!("{}", "assistant> ".yellow().bold());
    let _ = io::stdout().flush();

    let mut ttft: Option<Duration> = None;
    let mut full_text = String::new();
    let mut chunk_count = 0usize;

    loop {
        tokio::select! {
            chunk = chunks_rx.recv() => {
                match chunk {
                    Some(text) => {
                        if ttft.is_none() {
                            ttft = Some(start.elapsed());
                        }
                        print!("{text}");
                        let _ = io::stdout().flush();
                        full_text.push_str(&text);
                        chunk_count += 1;
                    }
                    None => break,
                }
            }
            err = errors_rx.recv() => {
                if let Some(e) = err {
                    eprintln!("\n{}", format!("Stream error: {e:#}").red());
                    return Err(e);
                }
            }
        }
    }

    let elapsed = start.elapsed();
    let elapsed_sec = elapsed.as_secs_f64();
    let ttft_ms = ttft.map(|d| d.as_millis()).unwrap_or(0);
    let token_estimate = full_text.split_whitespace().count().max(chunk_count);
    let tok_per_sec = if elapsed_sec > 0.0 { (token_estimate as f64) / elapsed_sec } else { 0.0 };

    println!();
    println!(
        "{}",
        format!(
            "⚡ [TTFT: {}ms | Total: {:.2}s | ~{} tokens | {:.1} tok/s]",
            ttft_ms, elapsed_sec, token_estimate, tok_per_sec
        )
        .bright_black()
        .italic()
    );

    Ok(())
}

// ─── Helpers ────────────────────────────────────────────────────────────────

fn read_line(rl: &mut Option<DefaultEditor>, prompt: &str) -> Result<String, ()> {
    if let Some(ed) = rl {
        match ed.readline(prompt) {
            Ok(line) => {
                let trimmed = line.trim();
                if !trimmed.is_empty() {
                    let _ = ed.add_history_entry(trimmed);
                }
                Ok(line)
            }
            Err(_) => Err(()),
        }
    } else {
        print!("{prompt}");
        let _ = io::stdout().flush();
        let mut input = String::new();
        if io::stdin().read_line(&mut input).is_ok() {
            Ok(input)
        } else {
            Err(())
        }
    }
}

fn build_agent(cfg: &Config) -> Result<Arc<Agent>> {
    let llm_client = llm::new(&cfg.llm).context("initialising LLM provider")?;
    let device_id = std::env::var("CYNAPSE_DEVICE_ID").unwrap_or_else(|_| "cynapse-cli-repl".to_string());

    let persona_path = PathBuf::from(&cfg.memory.persona_path);
    let defaults_path = PathBuf::from(&cfg.memory.defaults_path);
    let db_path = PathBuf::from(&cfg.memory.db_path);
    let sessions_path = PathBuf::from(&cfg.memory.sessions_path);

    let persona = Arc::new(Persona::new(&device_id, &persona_path, &defaults_path, &db_path).context("loading persona")?);
    std::fs::create_dir_all(&sessions_path).ok();
    let sessions = Arc::new(Manager::new_with_mode(sessions_path, cfg.session_file_mode()).context("opening session store")?);
    let tools = tools::build_profile(&cfg.tools.profile, &cfg.tools.work_dir, cfg.tools.timeout_seconds, persona.clone(), approval::default_policy(), netguard::secure_default(), None);

    let agent = Agent::new(device_id, llm_client, persona, sessions, tools, cfg.clone());
    Ok(Arc::new(agent))
}

fn resolve_gguf_path(cfg: &Config) -> Result<String> {
    let model_setting = &cfg.llm.model;
    let path = Path::new(model_setting);
    if path.exists() && path.extension().and_then(|s| s.to_str()) == Some("gguf") {
        return Ok(path.to_string_lossy().to_string());
    }

    let search_dirs = [
        &cfg.llm.models_dir,
        "./models",
        "../models",
        "~/.leafcutter/models",
        "~/.cache/cynapse/models",
        "~/.cynapse/models",
    ];

    for dir_str in search_dirs {
        let expanded = shellexpand_tilde(dir_str);
        let dir = Path::new(&expanded);
        if dir.exists() {
            let candidate = dir.join(model_setting);
            if candidate.exists() {
                return Ok(candidate.to_string_lossy().to_string());
            }
            if let Ok(entries) = std::fs::read_dir(dir) {
                for entry in entries.flatten() {
                    let p = entry.path();
                    if p.extension().and_then(|s| s.to_str()) == Some("gguf") {
                        if p.file_name().unwrap_or_default().to_string_lossy().contains(model_setting) {
                            return Ok(p.to_string_lossy().to_string());
                        }
                    }
                }
            }
        }
    }

    Err(anyhow::anyhow!("model file not found: '{}'. Run `cynapse get hf:org/repo` to download it.", model_setting))
}

fn shellexpand_tilde(s: &str) -> String {
    if let Some(stripped) = s.strip_prefix("~/") {
        if let Ok(home) = std::env::var("HOME") {
            return format!("{home}/{stripped}");
        }
    }
    s.to_string()
}

fn purple(s: &str) -> String {
    s.purple().bold().to_string()
}
fn dim_purple(s: &str) -> String {
    s.magenta().to_string()
}
fn gold(s: &str) -> String {
    s.yellow().bold().to_string()
}

fn truncate_str(s: &str, max_len: usize) -> String {
    if s.len() > max_len {
        let raw_keep = max_len.saturating_sub(1);
        let keep = floor_char_boundary(s, raw_keep);
        format!("{}…", &s[..keep])
    } else {
        s.to_string()
    }
}

fn floor_char_boundary(s: &str, index: usize) -> usize {
    if index >= s.len() {
        return s.len();
    }
    let mut i = index;
    while i > 0 && !s.is_char_boundary(i) {
        i -= 1;
    }
    i
}

fn get_peak_rss_mb() -> u64 {
    if let Ok(contents) = std::fs::read_to_string("/proc/self/status") {
        for line in contents.lines() {
            if line.starts_with("VmHWM:") {
                let parts: Vec<&str> = line.split_whitespace().collect();
                if parts.len() >= 2 {
                    if let Ok(kb) = parts[1].parse::<u64>() {
                        return (kb * 1024) / (1024 * 1024);
                    }
                }
            }
        }
    }
    0
}

fn get_current_rss_mb() -> u64 {
    if let Ok(contents) = std::fs::read_to_string("/proc/self/status") {
        for line in contents.lines() {
            if line.starts_with("VmRSS:") {
                let parts: Vec<&str> = line.split_whitespace().collect();
                if parts.len() >= 2 {
                    if let Ok(kb) = parts[1].parse::<u64>() {
                        return (kb * 1024) / (1024 * 1024);
                    }
                }
            }
        }
    }
    0
}

fn format_rss(mb: u64) -> String {
    if mb >= 1024 {
        format!("{:.1} GB", mb as f64 / 1024.0)
    } else {
        format!("{} MB", mb)
    }
}
