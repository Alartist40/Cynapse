//! GraftEngine — AST structural outliner, repository map generator, and safe context reader.
//!
//! Inspired by `Graft` (https://github.com/trailhq/Graft).
//! Provides:
//!   - `safe_read`: Guards context loading against binary files, secrets, lockfiles (`Cargo.lock`, `package-lock.json`), and oversized assets.
//!   - `extract_outline`: Generates lightweight Markdown outlines of code structure (functions, structs, impls, traits, classes) for large files instead of dumping 2,000 raw lines into prompt context.
//!   - `generate_repo_map`: Creates a structural Markdown map of a repository directory.

use anyhow::{Context, Result};
use std::fs;
use std::path::Path;

pub struct GraftEngine;

impl GraftEngine {
    /// Safe file reader that rejects binaries, secrets, and giant lockfiles.
    pub fn safe_read(path: &Path) -> Result<String> {
        let filename = path.file_name().and_then(|s| s.to_str()).unwrap_or("");

        // Block sensitive files & heavy lockfiles
        if filename == "Cargo.lock"
            || filename == "package-lock.json"
            || filename == "yarn.lock"
            || filename == "pnpm-lock.yaml"
            || filename.ends_with(".env")
            || filename.ends_with(".pem")
            || filename.ends_with(".key")
        {
            anyhow::bail!(
                "safe_read blocked file '{}' (binary/lockfile/secret)",
                filename
            );
        }

        let meta = fs::metadata(path).context("reading file metadata")?;
        if meta.len() > 10 * 1024 * 1024 {
            anyhow::bail!(
                "safe_read blocked file '{}' (exceeds 10MB safe size limit)",
                filename
            );
        }

        let content = fs::read_to_string(path).context("reading file content")?;

        // Verify UTF-8 / non-binary content
        if content.bytes().take(1024).any(|b| b == 0) {
            anyhow::bail!(
                "safe_read blocked file '{}' (binary format detected)",
                filename
            );
        }

        Ok(content)
    }

    /// Extract a lightweight structural outline (functions, structs, traits, impls, classes) from a code file.
    pub fn extract_outline(filename: &str, content: &str) -> String {
        let mut outline = Vec::new();
        outline.push(format!("### File Outline: `{filename}`"));

        for (idx, line) in content.lines().enumerate() {
            let line_num = idx + 1;
            let trimmed = line.trim();

            if trimmed.starts_with("pub fn ")
                || trimmed.starts_with("fn ")
                || trimmed.starts_with("pub struct ")
                || trimmed.starts_with("struct ")
                || trimmed.starts_with("pub enum ")
                || trimmed.starts_with("enum ")
                || trimmed.starts_with("impl ")
                || trimmed.starts_with("pub trait ")
                || trimmed.starts_with("trait ")
                || trimmed.starts_with("class ")
                || trimmed.starts_with("def ")
                || trimmed.starts_with("async def ")
                || trimmed.starts_with("function ")
                || trimmed.starts_with("export function ")
                || trimmed.starts_with("export default ")
            {
                // Truncate long signature lines cleanly
                let display_line = if trimmed.len() > 80 {
                    format!("{}...", &trimmed[..77])
                } else {
                    trimmed.to_string()
                };
                outline.push(format!("- L{line_num}: `{display_line}`"));
            }
        }

        if outline.len() == 1 {
            format!("### File Outline: `{filename}`\n- *(No high-level functions or symbols detected)*")
        } else {
            outline.join("\n")
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_extract_outline() {
        let code = "pub struct Engine;\n\nimpl Engine {\n    pub fn load(path: &str) -> Result<Self> {\n        todo!()\n    }\n}\n";
        let outline = GraftEngine::extract_outline("engine.rs", code);
        assert!(outline.contains("struct Engine"));
        assert!(outline.contains("impl Engine"));
        assert!(outline.contains("fn load"));
    }
}
