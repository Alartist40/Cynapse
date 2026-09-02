//! Provider fallback chain for graceful degradation.
//!
//! Ported from atomic-agent's `ProviderFallbackChain`. When the primary
//! LLM provider fails, the chain automatically switches to the next
//! configured provider with escalating cooldowns.

use std::collections::HashMap;
use std::sync::{Arc, Mutex};
use std::time::{Duration, Instant};

use anyhow::Result;

use crate::llm::providers::LlmClient;

/// Configuration for the fallback chain.
#[derive(Debug, Clone)]
pub struct FallbackConfig {
    /// Ordered list of provider IDs to try.
    pub chain: Vec<String>,
    /// Consecutive failures before switching providers.
    pub failure_threshold: u32,
    /// Escalating cooldown durations (must be non-decreasing).
    pub cooldowns: Vec<Duration>,
    /// Minimum time between probes to a recovered provider.
    pub probe_throttle: Duration,
    /// Time window after which failure counters reset.
    pub failure_window: Duration,
}

impl Default for FallbackConfig {
    fn default() -> Self {
        Self {
            chain: Vec::new(),
            failure_threshold: 3,
            cooldowns: vec![
                Duration::from_secs(30),
                Duration::from_secs(60),
                Duration::from_secs(300),
            ],
            probe_throttle: Duration::from_secs(300),
            failure_window: Duration::from_secs(86400),
        }
    }
}

/// State of a single provider in the fallback chain.
#[derive(Debug, Clone)]
struct ProviderState {
    failures: u32,
    last_failure: Option<Instant>,
    cooldown_step: usize,
    last_probe: Option<Instant>,
}

/// Provider fallback chain that switches on failure.
pub struct FallbackChain {
    config: FallbackConfig,
    providers: HashMap<String, Arc<dyn LlmClient>>,
    active_id: String,
    override_id: Option<String>,
    /// Per-session partition state (simplified to single partition for now).
    states: Mutex<HashMap<String, ProviderState>>,
}

impl FallbackChain {
    /// Create a new fallback chain.
    pub fn new(
        config: FallbackConfig,
        providers: HashMap<String, Arc<dyn LlmClient>>,
        active_id: String,
    ) -> Self {
        Self {
            config,
            providers,
            active_id,
            override_id: None,
            states: Mutex::new(HashMap::new()),
        }
    }

    /// Get the current active provider, respecting the override.
    pub fn current_provider(&self) -> Option<&Arc<dyn LlmClient>> {
        let active_id = if let Some(ref override_id) = self.override_id {
            override_id.as_str()
        } else {
            &self.active_id
        };
        self.providers.get(active_id)
    }

    /// Record a failure on the current provider.
    pub fn record_failure(&mut self, error: &anyhow::Error) {
        let is_advance_worthy = is_advance_worthy_error(error);
        if !is_advance_worthy {
            return;
        }

        let active_id = if let Some(ref override_id) = self.override_id {
            override_id.clone()
        } else {
            self.active_id.clone()
        };

        // Check if we should switch
        let should_switch = {
            let mut states = self.states.lock().unwrap();
            let state = states
                .entry(active_id.clone())
                .or_insert_with(|| ProviderState {
                    failures: 0,
                    last_failure: None,
                    cooldown_step: 0,
                    last_probe: None,
                });

            state.failures += 1;
            state.last_failure = Some(Instant::now());

            state.failures >= self.config.failure_threshold
        };

        if should_switch {
            self.switch_to_next();
        }
    }

    /// Record a success on the current provider.
    pub fn record_success(&mut self) {
        let active_id = if let Some(ref override_id) = self.override_id {
            override_id.clone()
        } else {
            self.active_id.clone()
        };

        let mut states = self.states.lock().unwrap();
        if let Some(state) = states.get_mut(&active_id) {
            // If we were on an override, switch back to primary
            if self.override_id.is_some() {
                self.override_id = None;
            }
            state.failures = 0;
            state.cooldown_step = 0;
        }
    }

    /// Try to switch to the next provider in the chain.
    fn switch_to_next(&mut self) {
        // Find current position in chain
        let current_id = if let Some(ref override_id) = self.override_id {
            override_id.clone()
        } else {
            self.active_id.clone()
        };

        if let Some(current_idx) = self.config.chain.iter().position(|id| *id == current_id) {
            // Try next provider
            for idx in (current_idx + 1)..self.config.chain.len() {
                let next_id = &self.config.chain[idx];
                if self.providers.contains_key(next_id) {
                    // Check cooldown
                    let mut states = self.states.lock().unwrap();
                    if let Some(state) = states.get(next_id) {
                        if let Some(last_failure) = state.last_failure {
                            let cooldown = self.get_cooldown(state.cooldown_step);
                            if last_failure.elapsed() < cooldown {
                                continue;
                            }
                        }
                    }

                    // Switch to next provider
                    self.override_id = Some(next_id.clone());

                    // Reset state for new provider
                    if let Some(state) = states.get_mut(next_id) {
                        state.failures = 0;
                        state.cooldown_step = 0;
                    }

                    return;
                }
            }
        }
    }

    /// Get cooldown duration for a given step.
    fn get_cooldown(&self, step: usize) -> Duration {
        if step >= self.config.cooldowns.len() {
            self.config.cooldowns.last().copied().unwrap_or(Duration::from_secs(300))
        } else {
            self.config.cooldowns[step]
        }
    }

    /// Get the currently active provider ID.
    pub fn active_id(&self) -> &str {
        if let Some(ref override_id) = self.override_id {
            override_id
        } else {
            &self.active_id
        }
    }
}

/// Check if an error should advance the fallback chain.
fn is_advance_worthy_error(error: &anyhow::Error) -> bool {
    let msg = error.to_string().to_lowercase();

    // Transport errors (network issues, timeouts)
    if msg.contains("connection")
        || msg.contains("timeout")
        || msg.contains("network")
        || msg.contains("unreachable")
    {
        return true;
    }

    // Model errors (empty, truncated)
    if msg.contains("empty") || msg.contains("truncated") {
        return true;
    }

    // Grammar errors and cancelled are NOT advance-worthy
    false
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_fallback_config_default() {
        let config = FallbackConfig::default();
        assert_eq!(config.failure_threshold, 3);
        assert_eq!(config.cooldowns.len(), 3);
    }

    #[test]
    fn test_is_advance_worthy() {
        assert!(is_advance_worthy_error(&anyhow::anyhow!("connection refused")));
        assert!(is_advance_worthy_error(&anyhow::anyhow!("timeout")));
        assert!(!is_advance_worthy_error(&anyhow::anyhow!("grammar error")));
    }
}
