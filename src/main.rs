mod cli;
mod doctor;
mod repl;

use std::sync::Arc;

use clap::Parser;

fn main() {
    let _ = leafcutter::init::configure_thread_pool(None);
    let args = cli::Cli::parse();
    if let Err(e) = run(args) {
        eprintln!("error: {e:#}");
        std::process::exit(1);
    }
}

fn run(args: cli::Cli) -> anyhow::Result<()> {
    match args.command {
        Some(cli::Command::Version) => {
            println!("cynapse {}", cynapse_tui::VERSION);
            Ok(())
        }
        Some(cli::Command::Chat) => run_chat(),
        Some(cli::Command::Repl(cmd)) => repl::run_repl(cmd),
        Some(cli::Command::Serve(cmd)) => run_serve(cmd),
        Some(cli::Command::Config(cmd)) => cli::config_dispatch(cmd),
        Some(cli::Command::Memory(cmd)) => {
            let cfg = cynapse_core::config::load(std::path::Path::new("config.yaml"))?;
            cli::memory_dispatch(&cfg, cmd)
        }
        Some(cli::Command::Doctor { fix }) => doctor::run_doctor(fix),
        Some(cli::Command::Update) => run_update(),
        Some(cli::Command::Get(cmd)) => run_get(cmd),
        Some(cli::Command::Load(cmd)) => run_load(cmd),
        Some(cli::Command::Unload) => run_unload(),
        Some(cli::Command::Ps) => run_ps(),
        Some(cli::Command::Ls) => run_ls(),
        None => run_chat(),
    }
}

fn run_chat() -> anyhow::Result<()> {
    let rt = tokio::runtime::Runtime::new()?;
    rt.block_on(async {
        let cfg = cynapse_core::config::load(std::path::Path::new("config.yaml")).unwrap_or_default();
        if cfg.llm.provider == "leafcutter" {
            cynapse_core::llm::prewarm_leafcutter_engine(&cfg.llm);
        }
        cynapse_tui::app::run(None).await
    })
}

fn run_serve(cmd: cli::ServeCmd) -> anyhow::Result<()> {
    let rt = tokio::runtime::Runtime::new()?;
    rt.block_on(async move {
        let cfg_path = std::path::Path::new(&cmd.config);
        let mut cfg = cynapse_core::config::load(cfg_path)?;
        if let Some(addr) = cmd.address {
            cfg.gateway.address = addr;
        }
        let state = Arc::new(cynapse_core::gateway::GatewayState::new(cfg));
        cynapse_core::gateway::run_server(state).await
    })
}

/// `cynapse update` — fetch the latest code from GitHub and rebuild.
///
/// Mirrors what `scripts/install.sh` does so the installed launcher is kept
/// in sync: clone/pull into a temp dir, `cargo build --release`, then install
/// into `~/.cynapse/builds/versions/<hash>/cynapse` and re-point the
/// `~/.cynapse/builds/stable/cynapse` + `~/.local/bin/cynapse` symlinks.
fn run_update() -> anyhow::Result<()> {
    use std::process::Command;

    let home = std::env::var("HOME").unwrap_or_else(|_| ".".to_string());
    let cynapse_home = std::env::var("CYNAPSE_HOME")
        .unwrap_or_else(|_| format!("{}/.cynapse", home));
    let install_dir = std::env::var("CYNAPSE_INSTALL_DIR")
        .unwrap_or_else(|_| format!("{}/.local/bin", home));
    let repo_url = std::env::var("CYNAPSE_REPO")
        .unwrap_or_else(|_| "https://github.com/Alartist40/cynapse.git".to_string());
    let branch = std::env::var("CYNAPSE_BRANCH").unwrap_or_else(|_| "main".to_string());

    println!("🔄 Updating cynapse from {} ({}) …", repo_url, branch);

    // Build into a temp dir so we never clobber a working install.
    let tmpdir = std::env::temp_dir().join(format!("cynapse-update-{}", std::process::id()));
    if tmpdir.exists() {
        std::fs::remove_dir_all(&tmpdir)?;
    }

    if !Command::new("git")
        .args(["clone", "--depth", "1", "--branch", &branch, &repo_url, tmpdir.to_str().unwrap()])
        .status()
        .map(|s| s.success())
        .unwrap_or(false)
    {
        anyhow::bail!("`git clone` failed. Is git installed and the network up?");
    }

    // Sync local LeafcutterLLM engine code into the build directory if available
    let local_leafcutter = format!("{}/Documents/portfolio/LeafcutterLLM/rust", home);
    let target_leafcutter = tmpdir.join("leafcutter");
    if std::path::Path::new(&local_leafcutter).exists() {
        println!("🌿 Syncing latest LeafcutterLLM engine from {} …", local_leafcutter);
        let _ = Command::new("cp")
            .args(["-r", &local_leafcutter, target_leafcutter.to_str().unwrap()])
            .status();
        let _ = std::fs::remove_dir_all(target_leafcutter.join("target"));
    }

    if !Command::new("cargo")
        .current_dir(&tmpdir)
        .args(["build", "--release"])
        .status()
        .map(|s| s.success())
        .unwrap_or(false)
    {
        let _ = std::fs::remove_dir_all(&tmpdir);
        anyhow::bail!("`cargo build --release` failed. Is cargo installed?");
    }

    let version_hash = Command::new("git")
        .args(["-C", tmpdir.to_str().unwrap(), "rev-parse", "--short", "HEAD"])
        .output()
        .ok()
        .map(|o| String::from_utf8_lossy(&o.stdout).trim().to_string())
        .unwrap_or_else(|| "unknown".to_string());

    let builds_dir = format!("{}/builds", cynapse_home);
    let stable_dir = format!("{}/stable", builds_dir);
    let version_dir = format!("{}/versions/{}", builds_dir, version_hash);
    let built = tmpdir.join("target/release/cynapse");

    if !built.exists() {
        let _ = std::fs::remove_dir_all(&tmpdir);
        anyhow::bail!("build produced no binary at {}", built.display());
    }

    std::fs::create_dir_all(&version_dir)?;
    std::fs::create_dir_all(&install_dir)?;
    std::fs::copy(&built, format!("{}/cynapse", version_dir))?;
    #[cfg(unix)]
    {
        use std::os::unix::fs::PermissionsExt;
        std::fs::set_permissions(
            format!("{}/cynapse", version_dir),
            std::fs::Permissions::from_mode(0o755),
        )?;
    }
    std::fs::write(format!("{}/VERSION", version_dir), &version_hash)?;

    // Symlinks: stable -> versioned; launcher -> stable.
    std::fs::create_dir_all(&stable_dir)?;
    std::fs::remove_file(format!("{}/cynapse", stable_dir)).ok();
    std::os::unix::fs::symlink(
        format!("{}/cynapse", version_dir),
        format!("{}/cynapse", stable_dir),
    )?;
    std::fs::remove_file(format!("{}/cynapse", install_dir)).ok();
    std::os::unix::fs::symlink(
        format!("{}/cynapse", stable_dir),
        format!("{}/cynapse", install_dir),
    )?;

    std::fs::write(format!("{}/stable-version", builds_dir), &version_hash)?;

    let _ = std::fs::remove_dir_all(&tmpdir);

    println!();
    println!("✅ cynapse ({}) updated. Restart cynapse to use it.", version_hash);
    println!("   Version: {} -> {}", cynapse_core::VERSION, version_hash);
    Ok(())
}

fn run_get(cmd: cli::GetCmd) -> anyhow::Result<()> {
    use colored::Colorize;
    println!("{}", format!("🔍 Resolving HuggingFace model: {}", cmd.model).cyan().bold());
    let path = cynapse_core::hf::download_hf_model(&cmd.model)?;
    println!("{}", format!("✨ Model ready at: {}", path.display()).green().bold());
    Ok(())
}

fn run_load(cmd: cli::LoadCmd) -> anyhow::Result<()> {
    use colored::Colorize;
    let cfg = cynapse_core::config::load(std::path::Path::new("config.yaml")).unwrap_or_default();
    println!("{}", format!("⚡ Pre-loading model into RAM: {}", cmd.model).cyan().bold());
    let status = cynapse_core::llm::load_engine_model(&cmd.model, &cfg.llm.models_dir)?;
    if status.loaded {
        println!("{}", format!("✅ Model successfully loaded in RAM: {}", status.path.unwrap_or_default()).green().bold());
    }
    Ok(())
}

fn run_unload() -> anyhow::Result<()> {
    use colored::Colorize;
    let evicted = cynapse_core::llm::unload_engine_model();
    if evicted {
        println!("{}", "✅ Model unloaded from RAM.".green().bold());
    } else {
        println!("{}", "ℹ️  No model was currently loaded in RAM.".yellow());
    }
    Ok(())
}

fn run_ps() -> anyhow::Result<()> {
    use colored::Colorize;
    let status = cynapse_core::llm::get_engine_status();
    println!("{}", "📊 Cynapse Model Memory Status (ps):".purple().bold());
    if status.loaded {
        println!("  • Status:  {}", "LOADED (In RAM/Mmap Cache)".green().bold());
        println!("  • Model:   {}", status.path.unwrap_or_default().yellow());
    } else {
        println!("  • Status:  {}", "EMPTY (No model in RAM)".yellow());
    }
    Ok(())
}

fn run_ls() -> anyhow::Result<()> {
    use colored::Colorize;
    let cfg = cynapse_core::config::load(std::path::Path::new("config.yaml")).unwrap_or_default();
    let models = cynapse_core::llm::list_cached_models(&cfg.llm.models_dir);
    println!("{}", "📦 Cached Local GGUF Models (ls):".purple().bold());
    if models.is_empty() {
        println!("  (No .gguf models cached. Run 'cynapse get hf:org/repo@quant' to download)");
    } else {
        for (name, size) in models {
            let size_mb = size / (1024 * 1024);
            println!("  • {:<50} {:>6} MB", name.cyan(), size_mb);
        }
    }
    Ok(())
}
