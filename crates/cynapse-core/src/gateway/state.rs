//! Shared state passed into axum handlers.
//!
//! The gateway owns an `Agent` constructed once at startup. Building the
//! agent is heavy (it spawns the LLM subprocess and warms caches), so we
//! hold the resolved value in a shared `OnceCell`-equivalent.

use std::path::PathBuf;
use std::sync::Arc;

use anyhow::{Context, Result};
use tokio::sync::OnceCell;

use crate::agent::Agent;
use crate::approval;
use crate::config::Config;
use crate::llm;
use crate::netguard;
use crate::persona::Persona;
use crate::session::Manager;
use crate::tools;

/// What the gateway exposes to the rest of the system.
pub struct GatewayState {
    pub config: Config,
    agent: OnceCell<Arc<Agent>>,
}

impl GatewayState {
    pub fn new(config: Config) -> Self {
        Self { config, agent: OnceCell::new() }
    }

    /// Resolve (or build) the agent on demand. Subsequent calls return the
    /// cached `Arc`, so the LLM provider is spawned exactly once per process.
    pub async fn agent(&self) -> Result<Arc<Agent>> {
        self.agent
            .get_or_try_init(|| async {
                let cfg = &self.config;
                let llm_client = llm::new(&cfg.llm)
                    .context("initialising LLM provider for gateway")?;

                let device_id = std::env::var("CYNAPSE_DEVICE_ID")
                    .unwrap_or_else(|_| "cynapse-gateway".to_string());

                let persona_path = PathBuf::from(&cfg.memory.persona_path);
                let defaults_path = PathBuf::from(&cfg.memory.defaults_path);
                let db_path = PathBuf::from(&cfg.memory.db_path);
                let sessions_path = PathBuf::from(&cfg.memory.sessions_path);

                let persona = Arc::new(
                    Persona::new(&device_id, &persona_path, &defaults_path, &db_path)
                        .context("loading persona")?,
                );
                let sessions = Arc::new(
                    Manager::new_with_mode(sessions_path, cfg.session_file_mode())
                        .context("opening session store")?,
                );
                let tools = tools::build_profile(
                    &cfg.tools.profile,
                    &cfg.tools.work_dir,
                    cfg.tools.timeout_seconds,
                    persona.clone(),
                    approval::default_policy(),
                    netguard::secure_default(),
                    None,
                );

                let agent = Agent::new(
                    device_id,
                    llm_client,
                    persona,
                    sessions,
                    tools,
                    cfg.clone(),
                );
                Ok::<_, anyhow::Error>(Arc::new(agent))
            })
            .await
            .cloned()
    }
}
