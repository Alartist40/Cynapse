//! Document-analysis / OCR.
//!
//! Transcribes attached images into text so a text-only chat model can
//! reason over documents. The primary engine is Ollama's
//! `frob/unlimited-ocr` model (a local big-model build of the
//! unlimited-ocr pipeline); if it is unavailable the remaining
//! configured vision models are tried in order. Text/PDF attachments do
//! not need OCR — their extracted text is the fallback.

use anyhow::{anyhow, Context as _, Result};
use serde_json::json;

use crate::attachments::{self, Attachment, AttachmentType};
use crate::config::OcrConfig;

/// OCR base URL: explicit override wins, else the LLM's Ollama URL.
pub fn base_url(cfg: &OcrConfig, llm_ollama_base_url: &str) -> String {
    if !cfg.ollama_base_url.is_empty() {
        cfg.ollama_base_url.trim_end_matches('/').to_string()
    } else {
        llm_ollama_base_url.trim_end_matches('/').to_string()
    }
}

/// Transcribe an image file to text, trying each configured OCR model
/// in order. Returns the transcription, or an error describing the last
/// failure if every model failed.
pub async fn extract_image_text(
    path: &str,
    cfg: &OcrConfig,
    llm_ollama_base_url: &str,
    http: &reqwest::Client,
) -> Result<String> {
    let att = attachments::load(path)?;
    if att.kind != AttachmentType::Image {
        return Err(anyhow!(
            "not an image ({}): OCR only applies to image attachments",
            att.mime
        ));
    }

    let size_mb = std::fs::metadata(path)
        .map(|m| m.len() / (1024 * 1024))
        .unwrap_or(0);
    if size_mb > cfg.max_image_mb {
        return Err(anyhow!(
            "image is {size_mb} MB — over the {} MB OCR limit",
            cfg.max_image_mb
        ));
    }

    let base = base_url(cfg, llm_ollama_base_url);
    let mut last_err = anyhow!("no OCR models configured");
    for model in &cfg.models {
        match generate(base.clone(), model, &att.content, cfg, http).await {
            Ok(text) if !text.trim().is_empty() => return Ok(text),
            Ok(_) => {
                last_err = anyhow!("model {model} returned an empty transcription");
            }
            Err(e) => {
                last_err = e;
                eprintln!("[OCR] model {model} failed: {last_err:#}");
            }
        }
    }
    Err(last_err)
}

/// Transcribe an already-loaded image attachment.
pub async fn extract_attachment_text(
    att: &Attachment,
    cfg: &OcrConfig,
    llm_ollama_base_url: &str,
    http: &reqwest::Client,
) -> Result<String> {
    if att.kind != AttachmentType::Image {
        return Err(anyhow!("OCR only applies to image attachments"));
    }
    let base = base_url(cfg, llm_ollama_base_url);
    let mut last_err = anyhow!("no OCR models configured");
    for model in &cfg.models {
        match generate(base.clone(), model, &att.content, cfg, http).await {
            Ok(text) if !text.trim().is_empty() => return Ok(text),
            Ok(_) => {
                last_err = anyhow!("model {model} returned an empty transcription");
            }
            Err(e) => {
                last_err = e;
                eprintln!("[OCR] model {model} failed: {last_err:#}");
            }
        }
    }
    Err(last_err)
}

async fn generate(
    base: String,
    model: &str,
    image_b64: &str,
    cfg: &OcrConfig,
    http: &reqwest::Client,
) -> Result<String> {
    let url = format!("{base}/api/generate");
    let body = json!({
        "model": model,
        "prompt": cfg.prompt,
        "images": [image_b64],
        "stream": false,
    });
    let resp = http
        .post(&url)
        .json(&body)
        .timeout(std::time::Duration::from_secs(cfg.timeout_seconds))
        .send()
        .await
        .context("connecting to Ollama")?;
    if !resp.status().is_success() {
        let status = resp.status();
        let text = resp.text().await.unwrap_or_default();
        return Err(anyhow!("Ollama HTTP {status}: {}", truncate(&text, 300)));
    }
    let data = resp.bytes().await.context("reading Ollama response")?;
    let v: serde_json::Value =
        serde_json::from_slice(&data).context("parsing Ollama response")?;
    let text = v
        .get("response")
        .and_then(|r| r.as_str())
        .unwrap_or_default()
        .to_string();
    if text.trim().is_empty() {
        return Err(anyhow!(
            "empty response from {model}: {}",
            truncate(&String::from_utf8_lossy(&data), 300)
        ));
    }
    Ok(text)
}

/// Build the user-message text for a set of attachments, running OCR on
/// images when enabled. Text/PDF attachments are inlined directly (their
/// extracted text is the fallback for non-visual models).
pub async fn augment_with_ocr(
    user_msg: &str,
    attachments: &[Attachment],
    cfg: &OcrConfig,
    llm_ollama_base_url: &str,
    http: &reqwest::Client,
) -> String {
    if !cfg.enabled || attachments.is_empty() {
        return user_msg.to_string();
    }
    let mut out = user_msg.to_string();
    for att in attachments {
        match att.kind {
            AttachmentType::Text | AttachmentType::Pdf => {
                if !att.content.is_empty() {
                    out.push_str(&format!(
                        "\n\n---\n**Attachment: {}**\n```\n{}\n```\n---",
                        att.filename, att.content
                    ));
                }
            }
            AttachmentType::Image => match extract_attachment_text(att, cfg, llm_ollama_base_url, http).await {
                Ok(text) => {
                    out.push_str(&format!("\n\n{}{}", cfg.prefix, text));
                }
                Err(e) => {
                    // Keep the image attachment itself so a multimodal
                    // provider can still see it — graceful degradation.
                    out.push_str(&format!(
                        "\n\n[Image attachment {}; OCR unavailable: {e}]",
                        att.filename
                    ));
                }
            },
            AttachmentType::Binary => {
                out.push_str(&format!(
                    "\n\n[Binary attachment {} — {} bytes base64, not transcribed]",
                    att.filename,
                    att.content.len()
                ));
            }
        }
    }
    out
}

fn truncate(s: &str, n: usize) -> String {
    if s.len() <= n {
        s.to_string()
    } else {
        format!("{}…", &s[..n])
    }
}

/// Convert wire-format [`crate::llm::Attachment`]s into the typed
/// [`attachments::Attachment`] used by the OCR pipeline.
pub fn to_core_attachments(atts: &[crate::llm::Attachment]) -> Vec<Attachment> {
    atts.iter()
        .map(|a| Attachment {
            kind: match a.kind.as_str() {
                "image" => AttachmentType::Image,
                "text" => AttachmentType::Text,
                "pdf" => AttachmentType::Pdf,
                _ => AttachmentType::Binary,
            },
            filename: a.filename.clone(),
            mime: a.mime.clone(),
            content: a.content.clone(),
            path: String::new(),
        })
        .collect()
}

#[cfg(test)]
mod tests {
    use super::*;
    use base64::Engine as _;

    #[test]
    fn base_url_override() {
        let cfg = OcrConfig::default();
        assert_eq!(base_url(&cfg, "http://x:11434"), "http://x:11434");
        let mut cfg2 = OcrConfig::default();
        cfg2.ollama_base_url = "http://y:11434/".into();
        assert_eq!(base_url(&cfg2, "http://x:11434"), "http://y:11434");
    }

    #[test]
    fn not_an_image_rejected() {
        let cfg = OcrConfig::default();
        let rt = tokio::runtime::Runtime::new().unwrap();
        let res = rt.block_on(async {
            extract_image_text(
                "Cargo.toml",
                &cfg,
                "http://localhost:11434",
                &reqwest::Client::new(),
            )
            .await
        });
        assert!(res.is_err());
        assert!(res.unwrap_err().to_string().contains("not an image"));
    }

    #[test]
    fn augment_inlines_text_attachments() {
        let cfg = OcrConfig::default();
        let att = Attachment {
            kind: AttachmentType::Text,
            filename: "note.txt".into(),
            mime: "text/plain".into(),
            content: "hello world".into(),
            path: "/tmp/note.txt".into(),
        };
        let rt = tokio::runtime::Runtime::new().unwrap();
        let out = rt.block_on(async {
            augment_with_ocr(
                "read this",
                &[att],
                &cfg,
                "http://localhost:11434",
                &reqwest::Client::new(),
            )
            .await
        });
        assert!(out.contains("hello world"));
        assert!(out.contains("read this"));
    }

    #[test]
    fn augment_disabled_passthrough() {
        let mut cfg = OcrConfig::default();
        cfg.enabled = false;
        let att = Attachment {
            kind: AttachmentType::Text,
            filename: "note.txt".into(),
            mime: "text/plain".into(),
            content: "hello".into(),
            path: "/tmp/note.txt".into(),
        };
        let rt = tokio::runtime::Runtime::new().unwrap();
        let out = rt.block_on(async {
            augment_with_ocr(
                "keep me",
                &[att],
                &cfg,
                "http://localhost:11434",
                &reqwest::Client::new(),
            )
            .await
        });
        assert_eq!(out, "keep me");
    }

    #[test]
    fn image_ocr_failure_degrades_gracefully() {
        // No Ollama running on port 9 → extract fails → the augmenter
        // notes the failure but still returns a message.
        let mut cfg = OcrConfig::default();
        cfg.ollama_base_url = "http://127.0.0.1:9".into();
        cfg.timeout_seconds = 2;
        let att = Attachment {
            kind: AttachmentType::Image,
            filename: "pic.png".into(),
            mime: "image/png".into(),
            content: base64::engine::general_purpose::STANDARD.encode([0x89u8, 0x50, 0x4e, 0x47]),
            path: "/tmp/pic.png".into(),
        };
        let rt = tokio::runtime::Runtime::new().unwrap();
        let out = rt.block_on(async {
            augment_with_ocr(
                "whats this",
                &[att],
                &cfg,
                "http://localhost:11434",
                &reqwest::Client::new(),
            )
            .await
        });
        assert!(out.contains("OCR unavailable"), "got: {out}");
        assert!(out.contains("whats this"));
    }
}
