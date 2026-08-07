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
