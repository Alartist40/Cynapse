mod cli;

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
        Some(cli::Command::Config(cmd)) => cli::config_dispatch(cmd),
        Some(cli::Command::Memory(cmd)) => {
            let cfg = cynapse_core::config::load(std::path::Path::new("config.yaml"))?;
            cli::memory_dispatch(&cfg, cmd)
        }
        None => {
            let rt = tokio::runtime::Runtime::new()?;
            rt.block_on(cynapse_tui::app::run(None))
        }
    }
}
