//! File attachments for sending to the model.
//!
//! Faithful port of Go `internal/attachments/attachments.go`: loads a
//! file from disk, classifies it by extension, and encodes its
//! content (base64 for images/binaries, raw text for text/PDF).

use anyhow::{anyhow, Result};
use base64::Engine;

/// Kind of attachment.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum AttachmentType {
    Image,
    Text,
    Pdf,
    Binary,
}

impl AttachmentType {
    pub fn as_str(&self) -> &'static str {
        match self {
            AttachmentType::Image => "image",
            AttachmentType::Text => "text",
            AttachmentType::Pdf => "pdf",
            AttachmentType::Binary => "binary",
        }
    }
}

/// A file that can be sent to the model.
#[derive(Debug, Clone)]
pub struct Attachment {
    pub kind: AttachmentType,
    pub filename: String,
    pub mime: String,
    /// Text content or base64 for images/binary.
    pub content: String,
    /// Original path.
    pub path: String,
}

/// Load a file from the given path and return an Attachment.
pub fn load(path: &str) -> Result<Attachment> {
    let info = std::fs::metadata(path).map_err(|e| anyhow!("stat file: {e}"))?;
    if info.is_dir() {
        return Err(anyhow!("cannot attach a directory"));
    }

    let ext = std::path::Path::new(path)
        .extension()
        .map(|e| e.to_string_lossy().to_lowercase())
        .unwrap_or_default();
    let filename = std::path::Path::new(path)
        .file_name()
        .map(|f| f.to_string_lossy().to_string())
        .unwrap_or_else(|| path.to_string());

    let mut att = Attachment {
        kind: AttachmentType::Binary,
        filename,
        mime: "application/octet-stream".to_string(),
        content: String::new(),
        path: path.to_string(),
    };

    match ext.as_str() {
        "png" | "jpg" | "jpeg" | "gif" | "bmp" | "webp" => {
            att.kind = AttachmentType::Image;
            att.mime = mime_for_ext(&ext);
            let data = std::fs::read(path).map_err(|e| anyhow!("reading image: {e}"))?;
            att.content = base64::engine::general_purpose::STANDARD.encode(data);
        }
        "txt" | "md" | "csv" | "json" | "yaml" | "yml" | "go" | "py" | "js" | "ts" | "html"
        | "css" | "sh" | "xml" | "log" => {
            att.kind = AttachmentType::Text;
            att.mime = "text/plain".to_string();
            att.content = std::fs::read_to_string(path).map_err(|e| anyhow!("reading text: {e}"))?;
        }
        "pdf" => {
            att.kind = AttachmentType::Pdf;
            att.mime = "application/pdf".to_string();
            // Try to extract text with pdftotext if available.
            match extract_pdf_text(path) {
                Ok(text) => att.content = text,
                Err(_) => {
                    let data = std::fs::read(path).map_err(|e| anyhow!("reading pdf: {e}"))?;
                    att.content = base64::engine::general_purpose::STANDARD.encode(data);
                }
            }
        }
        _ => {
            att.kind = AttachmentType::Binary;
            att.mime = "application/octet-stream".to_string();
            let data = std::fs::read(path).map_err(|e| anyhow!("reading file: {e}"))?;
            att.content = base64::engine::general_purpose::STANDARD.encode(data);
        }
    }

    Ok(att)
}

impl Attachment {
    /// Data URI for image attachments.
    pub fn to_image_url(&self) -> String {
        if self.kind != AttachmentType::Image {
            return String::new();
        }
        format!("data:{};base64,{}", self.mime, self.content)
    }

    /// Text content for text/pdf attachments.
    pub fn to_text(&self) -> String {
        if matches!(self.kind, AttachmentType::Text | AttachmentType::Pdf) {
            self.content.clone()
        } else {
            String::new()
        }
    }

    /// Markdown representation of the attachment.
    pub fn to_markdown(&self) -> String {
        match self.kind {
            AttachmentType::Image => format!("![{}]({})", self.filename, self.to_image_url()),
            AttachmentType::Text | AttachmentType::Pdf => format!(
                "\n---\n**Attachment: {}**\n```\n{}\n```\n---\n",
                self.filename, self.content
            ),
            AttachmentType::Binary => format!(
                "\n---\n**Attachment: {}** (binary, {} bytes base64)\n---\n",
                self.filename,
                self.content.len()
            ),
        }
    }
}

/// Look for a filename in the workspace directory and common subdirs.
pub fn find_in_workspace(filename: &str, workspace_dir: &str) -> Result<String> {
    if std::path::Path::new(filename).is_absolute() {
        if std::path::Path::new(filename).exists() {
            return Ok(filename.to_string());
        }
        return Err(anyhow!("file not found: {filename}"));
    }

    let candidates = [
        std::path::Path::new(workspace_dir).join(filename),
        std::path::Path::new(workspace_dir).join("uploads").join(filename),
        std::path::Path::new(workspace_dir).join("images").join(filename),
        std::path::Path::new(workspace_dir).join("documents").join(filename),
    ];
    for c in candidates {
        if c.exists() {
            return Ok(c.to_string_lossy().to_string());
        }
    }
    Err(anyhow!("file not found in workspace: {filename}"))
}

/// All files under the workspace that could be attached.
pub fn list_workspace_files(workspace_dir: &str) -> Result<Vec<String>> {
    let mut files = Vec::new();
    fn walk(dir: &std::path::Path, out: &mut Vec<String>) -> Result<()> {
        for entry in std::fs::read_dir(dir)? {
            let entry = entry?;
            let path = entry.path();
            if path.is_dir() {
                walk(&path, out)?;
            } else {
                out.push(path.to_string_lossy().to_string());
            }
        }
        Ok(())
    }
    let root = std::path::Path::new(workspace_dir);
    if root.exists() {
        walk(root, &mut files)?;
    }
    Ok(files)
}

fn mime_for_ext(ext: &str) -> String {
    match ext {
        "png" => "image/png".to_string(),
        "jpg" | "jpeg" => "image/jpeg".to_string(),
        "gif" => "image/gif".to_string(),
        "bmp" => "image/bmp".to_string(),
        "webp" => "image/webp".to_string(),
        _ => "image/png".to_string(),
    }
}

fn extract_pdf_text(path: &str) -> Result<String> {
    let out = std::process::Command::new("pdftotext")
        .arg(path)
        .arg("-")
        .output()
        .map_err(|e| anyhow!("pdftotext: {e}"))?;
    if !out.status.success() {
        return Err(anyhow!("pdftotext failed"));
    }
    Ok(String::from_utf8_lossy(&out.stdout).to_string())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn text_attachment() {
        let dir = std::env::temp_dir().join(format!("cynapse-att-{}-txt", std::process::id()));
        let _ = std::fs::create_dir_all(&dir);
        let path = dir.join("note.txt");
        std::fs::write(&path, "hello attachment").unwrap();
        let att = load(path.to_str().unwrap()).unwrap();
        assert_eq!(att.kind, AttachmentType::Text);
        assert_eq!(att.content, "hello attachment");
        assert_eq!(att.to_text(), "hello attachment");
        let _ = std::fs::remove_dir_all(&dir);
    }

    #[test]
    fn image_attachment_base64() {
        let dir = std::env::temp_dir().join(format!("cynapse-att-{}-img", std::process::id()));
        let _ = std::fs::create_dir_all(&dir);
        let path = dir.join("pic.png");
        std::fs::write(&path, [0x89u8, 0x50, 0x4e, 0x47]).unwrap();
        let att = load(path.to_str().unwrap()).unwrap();
        assert_eq!(att.kind, AttachmentType::Image);
        assert_eq!(att.mime, "image/png");
        assert!(att.to_image_url().starts_with("data:image/png;base64,"));
        let _ = std::fs::remove_dir_all(&dir);
    }

    #[test]
    fn unknown_binary() {
        let dir = std::env::temp_dir().join(format!("cynapse-att-{}-bin", std::process::id()));
        let _ = std::fs::create_dir_all(&dir);
        let path = dir.join("blob.xyz");
        std::fs::write(&path, [1u8, 2, 3, 4]).unwrap();
        let att = load(path.to_str().unwrap()).unwrap();
        assert_eq!(att.kind, AttachmentType::Binary);
        assert_eq!(att.mime, "application/octet-stream");
        let _ = std::fs::remove_dir_all(&dir);
    }

    #[test]
    fn reject_directory() {
        let dir = std::env::temp_dir().join(format!("cynapse-att-{}-dir", std::process::id()));
        let _ = std::fs::create_dir_all(&dir);
        assert!(load(dir.to_str().unwrap()).is_err());
        let _ = std::fs::remove_dir_all(&dir);
    }

    #[test]
    fn find_in_workspace_direct_and_subdir() {
        let dir = std::env::temp_dir().join(format!("cynapse-att-{}-find", std::process::id()));
        let _ = std::fs::create_dir_all(dir.join("uploads"));
        std::fs::write(dir.join("top.txt"), "top").unwrap();
        std::fs::write(dir.join("uploads").join("up.txt"), "up").unwrap();
        assert_eq!(find_in_workspace("top.txt", dir.to_str().unwrap()).unwrap(), dir.join("top.txt").to_string_lossy().to_string());
        assert_eq!(find_in_workspace("up.txt", dir.to_str().unwrap()).unwrap(), dir.join("uploads").join("up.txt").to_string_lossy().to_string());
        assert!(find_in_workspace("nope.txt", dir.to_str().unwrap()).is_err());
        let _ = std::fs::remove_dir_all(&dir);
    }
}
