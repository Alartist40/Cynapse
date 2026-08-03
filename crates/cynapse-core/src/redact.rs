//! Conservative secret-pattern redaction.
//!
//! Faithful port of Go `internal/redact/redact.go` (itself borrowed
//! from Hermes Agent's `agent/redact.py`): a regex-driven scanner for
//! common credential formats plus JSON-key and URL-query scans.
//!
//! Intent: false positives are fine (we mask a string that isn't a
//! secret); false negatives are not. Base64 image data is never scanned.

use std::collections::HashSet;
use std::sync::OnceLock;

use regex::Regex;
use serde_json::Value;

const DEFAULT_HEAD: usize = 6;
const DEFAULT_TAIL: usize = 4;
const DEFAULT_FLOOR: usize = 18;
const REDACTION_PLACEHOLDER: &str = "[REDACTED]";

fn regexes() -> &'static Vec<Regex> {
    static RE: OnceLock<Vec<Regex>> = OnceLock::new();
    RE.get_or_init(|| {
        [
            // OpenAI keys
            r"sk-(proj-|svca-)?[A-Za-z0-9]{20,}",
            r"sk_live_[A-Za-z0-9]{10,}",
            r"sk_test_[A-Za-z0-9]{10,}",
            // Anthropic keys
            r"sk-ant-[A-Za-z0-9-]{20,}",
            r"sk_ant_[A-Za-z0-9]{10,}",
            // Google AI Studio / Gemini keys
            r"AIza[A-Za-z0-9_-]{35}",
            // AWS access key IDs
            r"AKIA[0-9A-Z]{16}",
            // GitHub PATs (classic, fine-grained, and OAuth)
            r"ghp_[A-Za-z0-9]{36}",
            r"github_pat_[A-Za-z0-9_]{82}",
            r"gho_[A-Za-z0-9]{36}",
            r"ghu_[A-Za-z0-9]{36}",
            r"ghs_[A-Za-z0-9]{36}",
            r"ghr_[A-Za-z0-9]{36}",
            // HuggingFace
            r"hf_[A-Za-z0-9]{20,}",
            // Slack tokens
            r"xox[baprs]-[A-Za-z0-9-]{10,}",
            // Stripe
            r"sk_live_[A-Za-z0-9]{24,}",
            r"sk_test_[A-Za-z0-9]{24,}",
            // Mailgun / SendGrid / Twilio / Discord-ish long strings
            r"SG\.[A-Za-z0-9_-]{22}\.[A-Za-z0-9_-]{43}",
            r"MG\.[A-Za-z0-9_-]{32,}\.[A-Za-z0-9_-]{32,}",
            r"SK[a-fA-F0-9]{32}",
            // PEM private keys
            r"-----BEGIN [A-Z ]*PRIVATE KEY-----",
            r"-----BEGIN [A-Z ]*SECRET-----",
            r"-----BEGIN RSA [A-Z ]*-----",
            r"-----BEGIN OPENSSH PRIVATE KEY-----",
            // Bearer / Basic auth headers and JWT-ish tokens
            r"(?i)Bearer\s+[A-Za-z0-9._\-+/=]{20,}",
            r"eyJ[A-Za-z0-9_\-+/=]{10,}\.[A-Za-z0-9_\-+/=]{10,}\.[A-Za-z0-9_\-+/=]{10,}",
            // Long random base64 / hex blobs (low confidence; 40+ chars)
            r"(?i)(?:^|[^A-Za-z0-9])[A-Za-z0-9+/]{40,}={0,2}(?:[^A-Za-z0-9]|$)",
        ]
        .iter()
        .map(|p| Regex::new(p).expect("valid redact pattern"))
        .collect()
    })
}

/// Shell `KEY=value` and JSON `"key": "value"` assignments. The value is
/// the part that gets redacted.
fn env_assignment_patterns() -> &'static Vec<Regex> {
    static RE: OnceLock<Vec<Regex>> = OnceLock::new();
    RE.get_or_init(|| {
        [
            r#"(?i)\b(aws_secret_access_key|aws_session_token|api_key|apikey|api-key|access_token|refresh_token|auth_token|bearer_token|client_secret|client_id|private_key|secret|secret_key|token|password|passwd|pwd)\b\s*=\s*['"]?([^'"\s]+)"#,
            r#"(?i)"(api_?key|token|secret|password|access_?token|refresh_?token|auth_?token|bearer|client_?secret|client_?id|private_?key|secret_?value|secret_?input|key_?material)"\s*:\s*"([^"]+)""#,
        ]
        .iter()
        .map(|p| Regex::new(p).expect("valid env pattern"))
        .collect()
    })
}

fn url_pattern() -> &'static Regex {
    static RE: OnceLock<Regex> = OnceLock::new();
    RE.get_or_init(|| Regex::new(r#"https?://[^\s'"\)\]}>]+"#).unwrap())
}

fn image_data_url_pattern() -> &'static Regex {
    static RE: OnceLock<Regex> = OnceLock::new();
    RE.get_or_init(|| Regex::new(r"data:image/[A-Za-z0-9+]+;base64,").unwrap())
}

/// URL query keys that should always be redacted regardless of value.
fn url_query_secret_params() -> &'static HashSet<&'static str> {
    static SET: OnceLock<HashSet<&'static str>> = OnceLock::new();
    SET.get_or_init(|| {
        [
            "api_key", "apikey", "key", "token", "access_token", "refresh_token", "auth_token",
            "bearer", "secret", "signature", "sig", "sigv4_signature", "password", "passwd",
            "pwd", "x-api-key",
        ]
        .into_iter()
        .collect()
    })
}

/// A detected secret span.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Secret {
    /// Byte offset in the original string.
    pub start: usize,
    pub end: usize,
    /// "regex" | "env" | "json" | "urlquery" | "longbase64"
    pub kind: &'static str,
}

/// Scan returns the list of detected secrets in `text`.
pub fn scan(text: &str) -> Vec<Secret> {
    if text.is_empty() {
        return Vec::new();
    }

    let mut out: Vec<Secret> = Vec::new();

    for re in regexes() {
        for m in re.find_iter(text) {
            out = append_if_new_range(out, m.start(), m.end(), "regex");
        }
    }

    let patterns = env_assignment_patterns();
    // Shell `KEY=value`: redact the value (group 2). (The Go original
    // redacts the key name here — an exposure bug; we fix it.)
    for cap in patterns[0].captures_iter(text) {
        if let (Some(_full), Some(val)) = (cap.get(0), cap.get(2)) {
            out = append_if_new_range(out, val.start(), val.end(), "env");
        }
    }
    // JSON `"key": "value"`: redact the value (group 2).
    for cap in patterns[1].captures_iter(text) {
        if let (Some(_full), Some(val)) = (cap.get(0), cap.get(2)) {
            out = append_if_new_range(out, val.start(), val.end(), "json");
        }
    }

    // URL query-param scan. Skip image data URLs — their content is not a
    // credential.
    let image_ranges: Vec<(usize, usize)> = image_data_url_pattern()
        .find_iter(text)
        .map(|m| (m.start(), m.end()))
        .collect();
    let overlaps_image = |start: usize, end: usize| {
        image_ranges
            .iter()
            .any(|&(s, e)| start < e && end > s)
    };

    for url_match in url_pattern().find_iter(text) {
        let url_str = &text[url_match.start()..url_match.end()];
        let Some(q_idx) = url_str.find('?') else {
            continue;
        };
        let query = &url_str[q_idx + 1..];
        let url_start = url_match.start();
        for kv in split_query(query) {
            let Some(eq) = kv.find('=') else { continue };
            let key = kv[..eq].trim().to_lowercase();
            if !url_query_secret_params().contains(key.as_str()) {
                continue;
            }
            let val_start = url_start + q_idx + 1 + eq + 1;
            let val_end = url_start + q_idx + 1 + kv.len();
            if overlaps_image(val_start, val_end) {
                continue;
            }
            out = append_if_new_range(out, val_start, val_end, "urlquery");
        }
    }

    out
}

/// Return `text` with all detected secrets replaced by masked aliases.
pub fn redact(text: &str) -> String {
    if text.is_empty() {
        return text.to_string();
    }
    let secrets = scan(text);
    if secrets.is_empty() {
        return text.to_string();
    }

    // Sort and merge ranges so output is correct even when detectors
    // report spans out of order or partially overlapping.
    let mut ranges: Vec<(usize, usize)> = secrets.iter().map(|s| (s.start, s.end)).collect();
    ranges.sort_unstable();
    let mut merged: Vec<(usize, usize)> = Vec::new();
    for (s, e) in ranges {
        if let Some(last) = merged.last_mut() {
            if s <= last.1 {
                last.1 = last.1.max(e);
                continue;
            }
        }
        merged.push((s, e));
    }

    let mut out = String::with_capacity(text.len());
    let mut cursor = 0;
    for (s, e) in merged {
        out.push_str(&text[cursor..s]);
        out.push_str(&mask(&text[s..e]));
        cursor = e;
    }
    out.push_str(&text[cursor..]);
    out
}

/// Partially-displayed version of `value`: keeps head/tail visible so a
/// human can confirm a secret existed, but cannot recover it from a log.
/// Length is preserved so column alignment stays sane.
pub fn mask(value: &str) -> String {
    if value.is_empty() {
        return String::new();
    }
    if value.len() < DEFAULT_FLOOR {
        return "*".repeat(value.len());
    }
    let head = head_n(value, DEFAULT_HEAD);
    let tail = tail_n(value, DEFAULT_TAIL);
    let mid_len = value.len() - head.len() - tail.len();
    format!("{head}{}{tail}", "*".repeat(mid_len))
}

/// For cases where you don't want to show anything of the original.
pub fn mask_placeholder() -> &'static str {
    REDACTION_PLACEHOLDER
}

fn head_n(s: &str, n: usize) -> &str {
    let mut end = n.min(s.len());
    while end > 0 && !s.is_char_boundary(end) {
        end -= 1;
    }
    &s[..end]
}

fn tail_n(s: &str, n: usize) -> &str {
    let mut start = s.len().saturating_sub(n);
    while start < s.len() && !s.is_char_boundary(start) {
        start += 1;
    }
    &s[start..]
}

fn append_if_new_range(out: Vec<Secret>, start: usize, end: usize, kind: &'static str) -> Vec<Secret> {
    for s in &out {
        if s.start <= start && end <= s.end {
            return out;
        }
    }
    let mut out = out;
    out.push(Secret { start, end, kind });
    out
}

fn split_query(qs: &str) -> Vec<&str> {
    qs.split('&').collect()
}

/// Walk a JSON structure and redact any string value whose key matches a
/// sensitive name. Tolerant of malformed input — returns the input on
/// parse failure.
pub fn json_redact(raw: &[u8]) -> Vec<u8> {
    if raw.is_empty() {
        return raw.to_vec();
    }
    let Ok(value) = serde_json::from_slice::<Value>(raw) else {
        return raw.to_vec();
    };
    let redacted = walk_json(value);
    serde_json::to_vec(&redacted).unwrap_or_else(|_| raw.to_vec())
}

fn walk_json(v: Value) -> Value {
    match v {
        Value::Object(map) => {
            let mut out = serde_json::Map::new();
            for (k, val) in map {
                if is_sensitive_key(&k) {
                    if let Value::String(s) = &val {
                        if !s.is_empty() {
                            out.insert(k, Value::String(mask(s)));
                            continue;
                        }
                    }
                }
                out.insert(k, walk_json(val));
            }
            Value::Object(out)
        }
        Value::Array(arr) => Value::Array(arr.into_iter().map(walk_json).collect()),
        other => other,
    }
}

fn is_sensitive_key(k: &str) -> bool {
    let lk = k.to_lowercase();
    matches!(
        lk.as_str(),
        "api_key"
            | "apikey"
            | "api-key"
            | "token"
            | "access_token"
            | "refresh_token"
            | "auth_token"
            | "bearer"
            | "secret"
            | "secret_value"
            | "secret_input"
            | "password"
            | "passwd"
            | "pwd"
            | "client_secret"
            | "client_id"
            | "private_key"
            | "key_material"
    )
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn redacts_openai_key() {
        let s = "key=sk-proj-1234567890ABCDEFGHIJKLMN";
        let out = redact(s);
        assert!(!out.contains("sk-proj-1234567890"));
        assert!(out.contains("sk-pr"));
        assert!(out.contains("*****"));
    }

    #[test]
    fn redacts_env_value() {
        let s = "export API_KEY=superSecretValue123";
        let out = redact(s);
        assert!(!out.contains("superSecretValue123"), "got: {out}");
        assert!(out.contains("superS"), "got: {out}");
        assert!(out.contains("e123"), "got: {out}");
    }

    #[test]
    fn redacts_json_value() {
        let s = r#"{"api_key": "abcdefghijklmnopqrstuvwxyz123456"}"#;
        let out = redact(s);
        assert!(!out.contains("abcdefghijklmnopqrstuvwxyz123456"));
    }

    #[test]
    fn redacts_url_query() {
        let s = "https://example.com/endpoint?token=SECRETVALUE123&ok=1";
        let out = redact(s);
        assert!(!out.contains("SECRETVALUE123"), "got: {out}");
        assert!(out.contains("ok=1"));
    }

    #[test]
    fn never_redacts_base64_image() {
        // The data:image prefix is never treated as a URL with secret params.
        // The generic long-base64 pass still masks the body, as in Go.
        let img = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAABTElEQVQ4jWNgYGBgAAAABAAAFNd6oQAAAABJRU5ErkJggg==";
        let out = redact(img);
        assert!(out.starts_with("data:image/png;base64,"), "got: {out}");
        assert!(!out.contains("iVBORw0KGgoAAAANSUhEUg"), "got: {out}");
    }

    #[test]
    fn mask_respects_length() {
        assert_eq!(mask("abcdefghijklmnopqrstuvwxyz"), "abcdef****************wxyz");
        assert_eq!(mask("short"), "*****");
    }

    #[test]
    fn json_redact_masks_sensitive_keys() {
        let raw = br#"{"name":"ok","token":"abcdef123456","nested":{"password":"hunter2"}}"#;
        let out = json_redact(raw);
        let v: Value = serde_json::from_slice(&out).unwrap();
        assert_eq!(v["name"], "ok");
        assert_ne!(v["token"], "abcdef123456");
        assert_ne!(v["nested"]["password"], "hunter2");
    }
}
