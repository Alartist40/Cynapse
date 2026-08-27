//! HuggingFace Hub GGUF model resolver and downloader module.
//!
//! Provides native Rust support for fetching model quants directly from HuggingFace
//! using `hf:user/repo`, `user/repo@quant`, or HTTPS URLs.

use anyhow::{anyhow, Context, Result};
use indicatif::{ProgressBar, ProgressStyle};
use serde::Deserialize;
use std::fs::{self, File};
use std::io::Write;
use std::path::{Path, PathBuf};

#[derive(Debug, Clone)]
pub struct ParsedHfUri {
    pub repo: String,
    pub quant_filter: Option<String>,
    pub filename: Option<String>,
}

/// Parse user-supplied model identifier string.
///
/// Examples:
///   - `hf:Qwen/Qwen2.5-Coder-7B-Instruct-GGUF`
///   - `Qwen/Qwen2.5-Coder-7B-Instruct-GGUF@q4_k_m`
///   - `https://huggingface.co/Qwen/Qwen2.5-Coder-7B-Instruct-GGUF/blob/main/qwen2.5-coder-7b-instruct-q4_k_m.gguf`
pub fn parse_hf_uri(input: &str) -> Option<ParsedHfUri> {
    let s = input.trim();

    if s.starts_with("https://huggingface.co/") {
        let trimmed = s.trim_start_matches("https://huggingface.co/");
        let parts: Vec<&str> = trimmed.split('/').collect();
        if parts.len() >= 2 {
            let repo = format!("{}/{}", parts[0], parts[1]);
            let filename = parts.last().cloned().filter(|f| f.ends_with(".gguf")).map(|f| f.to_string());
            return Some(ParsedHfUri {
                repo,
                quant_filter: None,
                filename,
            });
        }
    }

    let clean = if s.starts_with("hf:") {
        &s[3..]
    } else {
        s
    };

    if clean.contains('/') {
        let (repo_part, quant_part) = match clean.split_once('@') {
            Some((r, q)) => (r, Some(q.to_lowercase())),
            None => (clean, None),
        };
        return Some(ParsedHfUri {
            repo: repo_part.to_string(),
            quant_filter: quant_part,
            filename: None,
        });
    }

    None
}

#[derive(Debug, Deserialize)]
struct HfTreeItem {
    path: String,
    size: Option<u64>,
}

/// Query HuggingFace Hub API to find matching `.gguf` files for a repository.
pub fn fetch_hf_gguf_files(repo: &str) -> Result<Vec<(String, u64)>> {
    let url = format!("https://huggingface.co/api/models/{}/tree/main", repo);
    let client = reqwest::blocking::Client::builder()
        .user_agent("cynapse-agent/0.1")
        .build()?;

    let resp = client.get(&url).send().context("failed to query HuggingFace API")?;
    if !resp.status().is_success() {
        return Err(anyhow!("HuggingFace API returned HTTP status {}", resp.status()));
    }

    let items: Vec<HfTreeItem> = resp.json().context("failed to parse HuggingFace API response JSON")?;
    let mut files: Vec<(String, u64)> = items
        .into_iter()
        .filter(|item| item.path.ends_with(".gguf"))
        .map(|item| (item.path, item.size.unwrap_or(0)))
        .collect();

    files.sort_by(|a, b| a.0.cmp(&b.0));
    Ok(files)
}

/// Select the best matching GGUF filename given a requested quantization filter.
pub fn select_best_gguf(files: &[(String, u64)], quant_filter: Option<&str>) -> Result<(String, u64)> {
    if files.is_empty() {
        return Err(anyhow!("no .gguf files found in repository"));
    }

    if let Some(q) = quant_filter {
        let q_lower = q.to_lowercase();
        for (name, size) in files {
            if name.to_lowercase().contains(&q_lower) {
                return Ok((name.clone(), *size));
            }
        }
    }

    // Default preference order if no quant filter specified: Q4_K_M -> Q4_K_S -> Q5_K_M -> Q8_0 -> first file
    let preferences = ["q4_k_m", "q4_k_s", "q5_k_m", "q8_0", "q4_0"];
    for pref in preferences {
        for (name, size) in files {
            if name.to_lowercase().contains(pref) {
                return Ok((name.clone(), *size));
            }
        }
    }

    Ok(files[0].clone())
}

/// Download a HuggingFace GGUF model directly to `~/.cache/cynapse/models/`.
pub fn download_hf_model(uri_str: &str) -> Result<PathBuf> {
    let parsed = parse_hf_uri(uri_str).ok_or_else(|| anyhow!("invalid HuggingFace URI format: {}", uri_str))?;

    let files = fetch_hf_gguf_files(&parsed.repo)?;
    let (target_file, file_size) = if let Some(ref fname) = parsed.filename {
        (fname.clone(), 0)
    } else {
        select_best_gguf(&files, parsed.quant_filter.as_deref())?
    };

    let cache_dir = dirs::cache_dir()
        .unwrap_or_else(|| PathBuf::from(".cache"))
        .join("cynapse")
        .join("models");
    fs::create_dir_all(&cache_dir)?;

    let local_path = cache_dir.join(&target_file);
    if local_path.exists() {
        println!("✅ Model file already cached at {}", local_path.display());
        return Ok(local_path);
    }

    let download_url = format!("https://huggingface.co/{}/resolve/main/{}", parsed.repo, target_file);
    println!("📥 Downloading HuggingFace model: {} -> {}", download_url, local_path.display());

    let client = reqwest::blocking::Client::builder()
        .user_agent("cynapse-agent/0.1")
        .timeout(std::time::Duration::from_secs(3600))
        .build()?;

    let mut resp = client.get(&download_url).send().context("download request failed")?;
    if !resp.status().is_success() {
        return Err(anyhow!("download failed with HTTP status {}", resp.status()));
    }

    let total_size = resp.content_length().unwrap_or(file_size);

    let pb = ProgressBar::new(total_size);
    pb.set_style(
        ProgressStyle::default_bar()
            .template("{spinner:.green} [{elapsed_precise}] [{bar:40.cyan/blue}] {bytes}/{total_bytes} ({eta})")
            .unwrap()
            .progress_chars("#>-"),
    );

    let tmp_path = local_path.with_extension("tmp");
    let mut out = File::create(&tmp_path)?;
    let mut buffer = [0u8; 65536];

    loop {
        let bytes_read = std::io::Read::read(&mut resp, &mut buffer)?;
        if bytes_read == 0 {
            break;
        }
        out.write_all(&buffer[..bytes_read])?;
        pb.inc(bytes_read as u64);
    }

    pb.finish_with_message("Download complete.");
    fs::rename(tmp_path, &local_path)?;
    println!("✅ Model saved to {}", local_path.display());

    Ok(local_path)
}
