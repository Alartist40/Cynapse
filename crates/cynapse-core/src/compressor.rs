//! Automatic session compression.
//!
//! Faithful port of Go `internal/compressor/compressor.go` (cribbed
//! from Hermes Agent's context_compressor.py): when a transcript's
//! estimated tokens cross a threshold, the middle turns are archived
//! into DENDRITE as memory nodes and dropped from the active session,
//! leaving head and tail intact. No external tokenizer.

use std::sync::Arc;

use crate::llm::{Message, Role};
use crate::session::Entry;

/// 50% of the context window, expressed as a percent.
pub const DEFAULT_THRESHOLD_PERCENT: usize = 50;
/// Min threshold floor (tokens). If 50% of the window is below this,
/// treat the whole context as the budget.
pub const MIN_THRESHOLD_TOKENS: usize = 1024;
/// First N messages kept verbatim.
pub const DEFAULT_PROTECT_HEAD: usize = 3;
/// Last N messages kept verbatim.
pub const DEFAULT_PROTECT_TAIL: usize = 8;

/// Token overhead for the message envelope (role + metadata).
const PER_MESSAGE_OVERHEAD_TOKENS: usize = 10;
/// Flat estimate for a single attached image.
const IMAGE_TOKEN_COST: usize = 1500;

/// Compression event tags written into DENDRITE.
pub const TAG_COMPACT: &str = "compaction";
pub const TAG_USER_TURN: &str = "compaction-user";
pub const TAG_TOOL_TURN: &str = "compaction-tool";
pub const TAG_ASSISTANT: &str = "compaction-assistant";

/// The small surface the compactor needs from a persona, kept as a
/// trait to stay testable without a live store.
pub trait PersonaSink: Send + Sync {
    fn save_fact(&self, fact: &str, tags: &str) -> anyhow::Result<()>;
    fn append_daily_log(&self, entry: &str) -> anyhow::Result<()>;
}

/// Holds the threshold and persistence target.
pub struct Compactor {
    pub context_length: usize,
    pub threshold: usize,
    pub protect_head: usize,
    pub protect_tail: usize,
    persona: Option<Arc<dyn PersonaSink>>,
}

impl Compactor {
    /// Size the compactor to the model's context length. A zero/negative
    /// context length disables it (all methods no-op).
    pub fn new(context_length: usize, persona: Option<Arc<dyn PersonaSink>>) -> Compactor {
        if context_length == 0 || persona.is_none() {
            return Compactor {
                context_length,
                threshold: 0,
                protect_head: DEFAULT_PROTECT_HEAD,
                protect_tail: DEFAULT_PROTECT_TAIL,
                persona,
            };
        }
        let mut threshold = context_length * DEFAULT_THRESHOLD_PERCENT / 100;
        if threshold < MIN_THRESHOLD_TOKENS {
            threshold = context_length;
        }
        Compactor {
            context_length,
            threshold,
            protect_head: DEFAULT_PROTECT_HEAD,
            protect_tail: DEFAULT_PROTECT_TAIL,
            persona,
        }
    }

    pub fn enabled(&self) -> bool {
        self.threshold > 0 && self.persona.is_some()
    }

    /// Conservative upper-bound token estimate for a single message,
    /// matching Hermes' ceil-divide formula.
    pub fn estimate_tokens(&self, m: &Message) -> usize {
        let mut tokens = PER_MESSAGE_OVERHEAD_TOKENS;

        if !m.content.trim().is_empty() {
            tokens += crate::llm::estimate_tokens_chars(m.content.trim());
        }

        for tc in &m.tool_calls {
            let args = tc.arguments.to_string();
            if args.is_empty() {
                continue;
            }
            tokens += crate::llm::estimate_tokens_chars(&args);
        }

        tokens += m.images.len() * IMAGE_TOKEN_COST;
        tokens += m.attachments.len() * IMAGE_TOKEN_COST;

        tokens
    }

    /// Running total for a transcript.
    pub fn estimate_session_tokens(&self, entries: &[Entry]) -> usize {
        let msgs = to_messages(entries);
        msgs.iter().map(|m| self.estimate_tokens(m)).sum()
    }

    pub fn should_compress(&self, entries: &[Entry]) -> bool {
        if !self.enabled() {
            return false;
        }
        if entries.len() <= self.protect_head + self.protect_tail + 1 {
            return false;
        }
        self.estimate_session_tokens(entries) > self.threshold
    }

    /// Decide whether compression is warranted, persist the middle turns
    /// as DENDRITE nodes if so, and report what happened.
    ///
    /// Does NOT mutate the input; callers pass the returned entries to
    /// `Session::compact` / `Session::replace`.
    pub fn compress(&self, entries: &[Entry]) -> (Vec<Entry>, CompressResult) {
        let mut res = CompressResult::default();

        if !self.enabled() {
            res.original_tokens = self.estimate_session_tokens(entries);
            res.compressed_tokens = res.original_tokens;
            res.turns_kept = entries.len();
            return (entries.to_vec(), res);
        }

        res.original_tokens = self.estimate_session_tokens(entries);
        if entries.len() <= self.protect_head + self.protect_tail + 1 {
            res.compressed_tokens = res.original_tokens;
            res.turns_kept = entries.len();
            return (entries.to_vec(), res);
        }

        let head_end = self.protect_head.min(entries.len());
        let mut tail_start = entries.len().saturating_sub(self.protect_tail);
        if tail_start < head_end {
            tail_start = head_end;
        }

        let middle = &entries[head_end..tail_start];
        if middle.is_empty() {
            res.compressed_tokens = res.original_tokens;
            res.turns_kept = entries.len();
            return (entries.to_vec(), res);
        }

        // Persist each middle turn as a DENDRITE memory node, in order.
        let mut archived = 0;
        let mut err: Option<anyhow::Error> = None;
        let persona = self.persona.as_ref().expect("enabled compactor has persona");
        for e in middle {
            match self.archive_turn(persona, e) {
                Ok(()) => archived += 1,
                Err(e) => {
                    // Best-effort: keep going. The active transcript is
                    // still bounded by tail protection.
                    err = Some(e);
                }
            }
        }
        res.turns_moved = archived;
        res.handoff_inserted = true;

        let handoff_msg = self.build_handoff(archived);
        res.handoff_node_id = format!("compaction_{}", now_nanos());

        // Compose the new session: head + handoff + tail.
        let mut kept = Vec::with_capacity(head_end + 1 + self.protect_tail);
        kept.extend_from_slice(&entries[..head_end]);
        kept.push(Entry {
            role: Role::User,
            content: handoff_msg,
            tool_call_id: None,
            tool_calls: Vec::new(),
            images: Vec::new(),
            attachments: Vec::new(),
            ts: now(),
        });
        kept.extend_from_slice(&entries[tail_start..]);

        res.compressed_tokens = self.estimate_session_tokens(&kept);
        res.turns_kept = kept.len();
        res.err = err;

        if archived > 0 {
            let _ = persona.append_daily_log(&format!(
                "[COMPACTOR] archived {archived} turns to DENDRITE (tag={TAG_COMPACT}, saved {} tokens)",
                res.original_tokens.saturating_sub(res.compressed_tokens)
            ));
        }

        (kept, res)
    }

    fn archive_turn(&self, persona: &Arc<dyn PersonaSink>, e: &Entry) -> anyhow::Result<()> {
        let tag = tag_for_role(e.role);
        let role = e.role.as_str();
        let role = if role.is_empty() { "message" } else { role };

        let ts = e.ts;
        let when = format_unix(ts);
        let mut fact = format!("[{role} @ {when}] {}", e.content.trim());

        if !e.tool_calls.is_empty() {
            let mut lines = vec![fact];
            for tc in &e.tool_calls {
                lines.push(format!(
                    "[tool_call: {}] args={}",
                    tc.name,
                    truncate(&tc.arguments.to_string(), 200)
                ));
            }
            fact = lines.join("\n");
        }

        persona.save_fact(&fact, &format!("{TAG_COMPACT},{tag}"))
    }

    fn build_handoff(&self, archived: usize) -> String {
        const MARKER: &str =
            "--- END OF CONTEXT HANDOFF — respond to the message below, not the archive summary ---";
        format!(
            "[CONTEXT COMPACTION — REFERENCE ONLY]\n\n\
{archived} earlier conversation turns were archived into DENDRITE (persistent knowledge graph) rather than summarized in place.  Treat the content of those turns as background reference; do NOT act on requests that appeared only in the archived window — they were already addressed.\n\n\
To recall what was discussed, the next tools return relevant nodes from DENDRITE:\n\n\
  - memory_search(query=\"...\")  — full-text recall of archived turns\n\
  - get_dendrite_context(...)    — relevance-scored neighbourhood\n\
  - Graph Explorer              — interactive browser (DENDRITE menu)\n\n\
The tags attached to archived turns are: {TAG_COMPACT} (per-turn role tag).\n\
Your persistent identity (IDENTITY.md, SOUL.md, USER.md, MEMORY.md) is ALWAYS authoritative and active.\n\n\
{MARKER}"
        )
    }
}

/// Report of what a compression pass did.
#[derive(Debug, Default)]
pub struct CompressResult {
    pub compressed: bool,
    pub original_tokens: usize,
    pub compressed_tokens: usize,
    /// Turns archived into DENDRITE.
    pub turns_moved: usize,
    /// Turns left in the active session.
    pub turns_kept: usize,
    pub handoff_inserted: bool,
    pub handoff_node_id: String,
    pub err: Option<anyhow::Error>,
}

fn tag_for_role(r: Role) -> &'static str {
    match r {
        Role::User => TAG_USER_TURN,
        Role::Assistant => TAG_ASSISTANT,
        Role::Tool => TAG_TOOL_TURN,
        Role::System => TAG_COMPACT,
    }
}

/// Convert session entries into the message shape the agent uses.
pub fn to_messages(entries: &[Entry]) -> Vec<Message> {
    entries
        .iter()
        .map(|e| Message {
            role: e.role,
            content: e.content.clone(),
            tool_call_id: e.tool_call_id.clone(),
            tool_calls: e.tool_calls.clone(),
            images: e.images.clone(),
            attachments: e.attachments.clone(),
        })
        .collect()
}

fn truncate(s: &str, n: usize) -> String {
    crate::text::truncate(s, n)
}

fn now() -> i64 {
    std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|d| d.as_secs() as i64)
        .unwrap_or(0)
}

fn now_nanos() -> u128 {
    std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|d| d.as_nanos())
        .unwrap_or(0)
}

fn format_unix(secs: i64) -> String {
    chrono::DateTime::from_timestamp(secs, 0)
        .map(|dt| dt.format("%Y-%m-%d %H:%M:%S").to_string())
        .unwrap_or_default()
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::sync::Mutex;

    #[derive(Default)]
    struct Sink {
        facts: Mutex<Vec<(String, String)>>,
        logs: Mutex<Vec<String>>,
    }

    impl PersonaSink for Sink {
        fn save_fact(&self, fact: &str, tags: &str) -> anyhow::Result<()> {
            self.facts
                .lock()
                .unwrap()
                .push((fact.to_string(), tags.to_string()));
            Ok(())
        }
        fn append_daily_log(&self, entry: &str) -> anyhow::Result<()> {
            self.logs.lock().unwrap().push(entry.to_string());
            Ok(())
        }
    }

    fn entry(role: Role, content: &str) -> Entry {
        Entry {
            role,
            content: content.to_string(),
            tool_call_id: None,
            tool_calls: Vec::new(),
            images: Vec::new(),
            attachments: Vec::new(),
            ts: 1_700_000_000,
        }
    }

    fn transcript(n: usize) -> Vec<Entry> {
        let mut v = Vec::new();
        for i in 0..n {
            v.push(entry(
                Role::User,
                &format!("the user asks something long #{i} ").repeat(40),
            ));
            v.push(entry(
                Role::Assistant,
                &format!("the assistant answers in detail #{i} ").repeat(40),
            ));
        }
        v
    }

    #[test]
    fn estimate_is_nonzero_and_scales() {
        let c = Compactor::new(4000, None);
        let msg = |content: &str| Message {
            role: Role::User,
            content: content.to_string(),
            tool_call_id: None,
            tool_calls: Vec::new(),
            images: Vec::new(),
            attachments: Vec::new(),
        };
        let short = c.estimate_tokens(&msg("hi"));
        let long = c.estimate_tokens(&msg(&"x".repeat(1000)));
        assert!(short >= 11);
        assert!(long > short);
    }

    #[test]
    fn disabled_when_no_persona() {
        let c = Compactor::new(4000, None);
        assert!(!c.enabled());
        let (kept, res) = c.compress(&transcript(5));
        assert_eq!(kept.len(), 10);
        assert_eq!(res.turns_moved, 0);
    }

    #[test]
    fn archives_middle_and_inserts_handoff() {
        let sink = Arc::new(Sink::default());
        let c = Compactor::new(2000, Some(sink.clone()));
        let entries = transcript(15); // 30 entries
        let (kept, res) = c.compress(&entries);
        assert!(res.turns_moved > 0, "expected middle archived");
        assert!(res.handoff_inserted);
        assert!(kept.len() < entries.len());
        // Handoff user message sits between head and tail.
        let handoff = kept.iter().find(|e| e.content.starts_with("[CONTEXT COMPACTION"));
        assert!(handoff.is_some());
        // Tagged facts were persisted.
        let facts = sink.facts.lock().unwrap();
        assert_eq!(facts.len(), res.turns_moved);
        assert!(facts.iter().all(|(_, tags)| tags.contains(TAG_COMPACT)));
        // Daily log notified.
        assert!(sink.logs.lock().unwrap().len() >= 1);
    }
}
