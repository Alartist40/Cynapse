//! Dynamic Model Scheduler & Memory Manager
//!
//! Handles lazy GGUF model loading, tag resolution, and keep_alive idle
//! auto-unloading to keep system RAM footprint low.

use std::path::{Path, PathBuf};
use std::sync::{Arc, Mutex};
use std::time::{Duration, Instant};

use crate::inference::engine::Engine as NativeEngine;

pub struct LoadedEngine {
    pub name: String,
    pub path: PathBuf,
    pub engine: NativeEngine,
    pub last_used: Instant,
    pub keep_alive_duration: Duration,
}

#[derive(Clone)]
pub struct ModelScheduler {
    inner: Arc<Mutex<Option<LoadedEngine>>>,
}

impl ModelScheduler {
    pub fn new() -> Self {
        let scheduler = Self {
            inner: Arc::new(Mutex::new(None)),
        };

        let inner_clone = scheduler.inner.clone();
        tokio::spawn(async move {
            loop {
                tokio::time::sleep(Duration::from_secs(10)).await;
                if let Ok(mut guard) = inner_clone.lock() {
                    if let Some(loaded) = guard.as_ref() {
                        if loaded.last_used.elapsed() > loaded.keep_alive_duration {
                            eprintln!(
                                "[Scheduler] Idle timeout reached for model '{}'. Unloading mmap & RAM...",
                                loaded.name
                            );
                            guard.take(); // Drops LoadedEngine, freeing RAM & mmap!
                        }
                    }
                }
            }
        });

        scheduler
    }

    /// Resolve model tag name (e.g. "ministral-3:3b" or "ornith") or absolute path.
    pub fn resolve_model_path(&self, name: &str) -> Option<PathBuf> {
        let p = Path::new(name);
        if p.exists() && p.is_file() {
            return Some(p.to_path_buf());
        }

        let home = std::env::var("HOME").unwrap_or_default();
        let search_dirs = vec![
            PathBuf::from("./models"),
            PathBuf::from(format!("{home}/Downloads/models")),
            PathBuf::from(format!("{home}/models")),
            PathBuf::from(format!("{home}/.ollama/models")),
        ];

        let target = name.to_lowercase();
        // Exact filename check first
        for dir in &search_dirs {
            if let Ok(entries) = std::fs::read_dir(dir) {
                for ent in entries.flatten() {
                    let path = ent.path();
                    if path.is_file() && path.extension().and_then(|e| e.to_str()) == Some("gguf") {
                        if let Some(stem) = path.file_name().and_then(|s| s.to_str()) {
                            if stem.to_lowercase() == target {
                                return Some(path);
                            }
                        }
                    }
                }
            }
        }

        // Substring match fallback
        for dir in search_dirs {
            if let Ok(entries) = std::fs::read_dir(dir) {
                for ent in entries.flatten() {
                    let path = ent.path();
                    if path.is_file() && path.extension().and_then(|e| e.to_str()) == Some("gguf") {
                        let filename = path.file_name().unwrap_or_default().to_string_lossy().to_lowercase();
                        let target_clean = target.split(':').next().unwrap_or(&target);
                        if filename.contains(target_clean) || target_clean.contains(&filename) {
                            return Some(path);
                        }
                    }
                }
            }
        }
        None
    }

    /// Returns list of available GGUF model files across search paths.
    pub fn list_available_models(&self) -> Vec<(String, PathBuf, u64)> {
        let home = std::env::var("HOME").unwrap_or_default();
        let search_dirs = vec![
            PathBuf::from("./models"),
            PathBuf::from(format!("{home}/Downloads/models")),
            PathBuf::from(format!("{home}/models")),
        ];

        let mut models = Vec::new();
        for dir in search_dirs {
            if let Ok(entries) = std::fs::read_dir(dir) {
                for ent in entries.flatten() {
                    let path = ent.path();
                    if path.is_file() && path.extension().and_then(|e| e.to_str()) == Some("gguf") {
                        let size = std::fs::metadata(&path).map(|m| m.len()).unwrap_or(0);
                        let name = path
                            .file_name()
                            .unwrap_or_default()
                            .to_string_lossy()
                            .to_string();
                        models.push((name, path, size));
                    }
                }
            }
        }
        models
    }

    /// Get currently loaded model info (if any).
    pub fn currently_loaded(&self) -> Option<(String, PathBuf, u64)> {
        let guard = self.inner.lock().ok()?;
        let loaded = guard.as_ref()?;
        let size = std::fs::metadata(&loaded.path).map(|m| m.len()).unwrap_or(0);
        Some((loaded.name.clone(), loaded.path.clone(), size))
    }

    /// Execute a function with access to the requested model's loaded `NativeEngine`.
    pub fn with_engine<F, R>(&self, model_name: &str, keep_alive_secs: Option<u64>, f: F) -> Result<R, String>
    where
        F: FnOnce(&mut NativeEngine) -> R,
    {
        let mut guard = self.inner.lock().map_err(|e| e.to_string())?;

        let path = self
            .resolve_model_path(model_name)
            .ok_or_else(|| format!("Model '{model_name}' not found in search paths"))?;

        let keep_alive = Duration::from_secs(keep_alive_secs.unwrap_or(300));

        let need_load = match guard.as_ref() {
            Some(loaded) => loaded.path != path,
            None => true,
        };

        if need_load {
            if guard.is_some() {
                eprintln!("[Scheduler] Unloading previous model from RAM...");
                guard.take();
            }
            eprintln!("[Scheduler] Loading model GGUF: {}", path.display());
            let path_str = path.to_str().ok_or("Invalid path string")?;
            let engine = NativeEngine::load(path_str)
                .map_err(|e| format!("Failed to load GGUF model: {e}"))?;

            *guard = Some(LoadedEngine {
                name: model_name.to_string(),
                path: path.clone(),
                engine,
                last_used: Instant::now(),
                keep_alive_duration: keep_alive,
            });
        }

        let loaded = guard.as_mut().unwrap();
        loaded.last_used = Instant::now();
        loaded.keep_alive_duration = keep_alive;

        Ok(f(&mut loaded.engine))
    }
}
