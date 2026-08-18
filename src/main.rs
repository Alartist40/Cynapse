mod cli;

use std::sync::Arc;

use clap::Parser;

fn main() {
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
        Some(cli::Command::Serve(cmd)) => run_serve(cmd),
        Some(cli::Command::Config(cmd)) => cli::config_dispatch(cmd),
        Some(cli::Command::Memory(cmd)) => {
            let cfg = cynapse_core::config::load(std::path::Path::new("config.yaml"))?;
            cli::memory_dispatch(&cfg, cmd)
        }
        Some(cli::Command::Update) => run_update(),
        None => run_chat(),
    }
}

fn run_chat() -> anyhow::Result<()> {
    let rt = tokio::runtime::Runtime::new()?;
    rt.block_on(cynapse_tui::app::run(None))
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
