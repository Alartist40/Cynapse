//! Command-line interface for the cynapse binary.

use clap::{Args, Parser, Subcommand};

use cynapse_core::config::Config;

/// Local-first AI agent with a persistent graph memory (DENDRITE).
#[derive(Debug, Parser)]
#[command(name = "cynapse", version, about)]
pub struct Cli {
    #[command(subcommand)]
    pub command: Option<Command>,
}

#[derive(Debug, Subcommand)]
pub enum Command {
    /// Print version information.
    Version,
    /// Launch the interactive chat TUI.
    Chat,
    /// Launch the lightweight interactive CLI REPL (or execute single prompt).
    #[command(alias = "cli")]
    Repl(ReplCmd),
    /// Serve the local web gateway (camera stream + chat UI).
    Serve(ServeCmd),
    /// Inspect and validate the YAML configuration.
    Config(ConfigCmd),
    /// Query the DENDRITE graph memory.
    Memory(MemoryCmd),
    /// Run full system diagnostic health check.
    Doctor,
    /// Update cynapse to the latest version from GitHub.
    Update,
    /// Download a GGUF model from HuggingFace (e.g. cynapse get hf:Qwen/Qwen2.5-Coder-7B-Instruct-GGUF).
    Get(GetCmd),
    /// Pre-load a model file or HuggingFace ID into RAM memory.
    Load(LoadCmd),
    /// Unload and free the currently loaded engine model from RAM.
    Unload,
    /// Display currently loaded model and memory footprint status.
    Ps,
    /// List cached GGUF models in local model directories.
    Ls,
}

#[derive(Debug, Args, Default)]
pub struct ReplCmd {
    /// Execute a single prompt directly without entering interactive REPL mode
    #[arg(short, long)]
    pub prompt: Option<String>,

    /// Path to configuration file
    #[arg(long, default_value = "config.yaml")]
    pub config: String,
}

#[derive(Debug, Args)]
pub struct GetCmd {
    /// Model identifier or HuggingFace URI (e.g. hf:org/repo@quant)
    pub model: String,
}

#[derive(Debug, Args)]
pub struct LoadCmd {
    /// Model file path or HuggingFace URI to pre-load
    pub model: String,
}

#[derive(Debug, Args)]
pub struct ServeCmd {
    /// Path to the configuration file.
    #[arg(long, default_value = "config.yaml")]
    pub config: String,
    /// Override the bind address (gateway.address).
    #[arg(long)]
    pub address: Option<String>,
}

#[derive(Debug, Args)]
pub struct ConfigCmd {
    #[command(subcommand)]
    pub sub: ConfigSub,
}

#[derive(Debug, Subcommand)]
pub enum ConfigSub {
    /// Print the effective configuration (with secrets redacted).
    Show,
    /// Write a default config.yaml to the current directory.
    Init,
    /// Print the config file path that would be loaded.
    Path,
}

#[derive(Debug, Args)]
pub struct MemoryCmd {
    #[command(subcommand)]
    pub sub: MemorySub,
}

#[derive(Debug, Subcommand)]
pub enum MemorySub {
    /// List all nodes in the graph.
    List {
        #[arg(long, default_value_t = 20)]
        limit: usize,
    },
    /// Full-text search the graph.
    Search {
        query: String,
        #[arg(long, default_value_t = 10)]
        limit: usize,
    },
}

pub fn config_dispatch(cmd: ConfigCmd) -> anyhow::Result<()> {
    match cmd.sub {
        ConfigSub::Show => {
            let cfg = load_config()?;
            let mut out = serde_yaml::to_string(&cfg)?;
            out = redact_rendered_config(&out);
            print!("{out}");
            Ok(())
        }
        ConfigSub::Init => {
            let path = std::path::Path::new("config.yaml");
            cynapse_core::config::create_default(path)?;
            println!("wrote {}", path.display());
            Ok(())
        }
        ConfigSub::Path => {
            println!("{}", config_path().display());
            Ok(())
        }
    }
}

pub fn memory_dispatch(cfg: &Config, cmd: MemoryCmd) -> anyhow::Result<()> {
    let db_path = &cfg.memory.dendrite_db_path;
    let store = cynapse_core::dendrite::DendriteStore::open(db_path)?;
    match cmd.sub {
        MemorySub::List { limit } => {
            let graph = cynapse_core::dendrite::Dendrite::new();
            store.load_all(&graph)?;
            let nodes = graph.all();
            println!("{} node(s):", nodes.len());
            for n in nodes.iter().take(limit) {
                println!(
                    "[{}] {} ({})",
                    n.node_type.label(),
                    n.title,
                    n.id
                );
            }
            Ok(())
        }
        MemorySub::Search { query, limit } => {
            let ids = store.fts_search(&query, limit)?;
            if ids.is_empty() {
                println!("(no memories found)");
                return Ok(());
            }
            let graph = cynapse_core::dendrite::Dendrite::new();
            store.load_all(&graph)?;
            for id in ids {
                if let Some(node) = graph.get(&id) {
                    println!("## {}\n{}", node.title, node.content);
                    println!();
                }
            }
            Ok(())
        }
    }
}

/// Load config.yaml from the current directory (defaults if absent).
fn load_config() -> anyhow::Result<Config> {
    cynapse_core::config::load(&config_path())
}

fn config_path() -> std::path::PathBuf {
    std::path::PathBuf::from("config.yaml")
}

/// Strip known key-shaped values from a rendered YAML config before display.
fn redact_rendered_config(s: &str) -> String {
    cynapse_core::redact::redact(s)
}
