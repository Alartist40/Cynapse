//! AdhdFilter — Focused, anti-fluff response shaper and ADHD mode prompt injector.
//!
//! Inspired by `i-have-adhd` (https://github.com/ayghri/i-have-adhd).
//! Provides:
//!   - `ADHD_SYSTEM_PROMPT`: Directives forcing action-first, 5-item list caps, no preamble/recap/closers.
//!   - `strip_fluff`: Clean pre-send output filter removing common LLM preambles, recaps, and conversational closers.

pub const ADHD_SYSTEM_PROMPT: &str = "\
## ADHD / Focus Mode Output Protocol (STRICT)
The reader requires focused, action-oriented, zero-fluff responses.

### Protocol Rules:
1. Lead with the next action. Line 1 must be an actionable command, path, code snippet, or direct answer.
2. No preamble. NEVER open with 'Great question!', 'Let me think...', 'Sure!', 'Looking at your code...', or 'To answer your question...'.
3. Number multi-step tasks. Maximum 5 items per list.
4. Restate turn state across multi-turn work (e.g. 'Step 2 of 4 done: ...').
5. End with ONE concrete next action under 2 minutes.
6. No closing pleasantries. NEVER end with 'Hope this helps!', 'Let me know if you need anything else', or 'Happy to clarify'.
7. Matter-of-fact tone for errors. State cause and fix directly.
";

/// Pre-send filter to strip conversational fluff (preambles, recaps, closers) from streamed or generated text.
pub fn strip_fluff(text: &str) -> String {
    let mut s = text.to_string();

    // Strip Thinking Process / Reasoning headers if present
    if let Some(pos) = s.find("Thinking Process:") {
        if let Some(end_pos) = s[pos..].find("\n\n") {
            s = s[pos + end_pos..].trim_start().to_string();
        }
    }

    if let Some(pos) = s.find("</think>") {
        s = s[pos + 8..].trim_start().to_string();
    }

    // Strip common preamble lines from beginning of text
    let preambles = [
        "Great question!",
        "Great question.",
        "Sure!",
        "Sure, I can help with that.",
        "Let me think about this.",
        "Let's break this down.",
        "Looking at your code,",
        "To answer your question,",
        "Here is what you need to do:",
        "Certainly!",
        "I'd be happy to help.",
    ];

    for p in preambles {
        let trimmed = s.trim_start();
        if trimmed.starts_with(p) {
            s = trimmed[p.len()..]
                .trim_start_matches(|c: char| c == '\n' || c == '\r' || c == ' ')
                .to_string();
        }
    }

    // Strip common closing pleasantry lines from end of text
    let closers = [
        "Hope this helps!",
        "Hope that helps!",
        "Let me know if you have any questions!",
        "Let me know if you need anything else.",
        "Happy coding!",
        "Feel free to ask if you need further clarification.",
    ];

    for c in closers {
        let trimmed = s.trim_end();
        if trimmed.ends_with(c) {
            s = trimmed[..trimmed.len() - c.len()]
                .trim_end_matches(|ch: char| ch == '\n' || ch == '\r' || ch == ' ')
                .to_string();
        }
    }

    s
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_strip_fluff_preamble() {
        let input = "Great question! Run `cargo build` to compile.";
        assert_eq!(strip_fluff(input), "Run `cargo build` to compile.");
    }

    #[test]
    fn test_strip_fluff_closer() {
        let input = "Run `cargo build` to compile.\n\nHope this helps!";
        assert_eq!(strip_fluff(input), "Run `cargo build` to compile.");
    }
}
