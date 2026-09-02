//! Incremental parser for streaming LLM output with thinking detection.
//!
//! Ported from atomic-agent's `stream-parser.ts`. Detects `<think>...</think>`
//! blocks in the stream and surfaces live reasoning + reply text deltas
//! to the TUI for separated rendering.

/// Events emitted by the stream parser.
#[derive(Debug, Clone, PartialEq)]
pub enum StreamEvent {
    /// Opening a thinking block.
    ReasoningOpen,
    /// Delta text inside a thinking block.
    ReasoningDelta(String),
    /// Closing a thinking block.
    ReasoningClose,
    /// Opening reply text.
    ReplyOpen,
    /// Delta text in the reply.
    ReplyDelta(String),
    /// Closing reply text.
    ReplyClose,
}

/// Parser state machine.
#[derive(Debug, Clone, PartialEq)]
enum ParserState {
    Preamble,
    InsideThink,
    ReplyText,
    Done,
}

/// Configuration for the stream parser.
#[derive(Debug, Clone)]
pub struct StreamParserOptions {
    /// Whether the stream starts inside an already-open think tag.
    pub pre_opened_think: bool,
    /// The opening tag to detect (default: `<think>`).
    pub reasoning_open_tag: String,
    /// The closing tag to detect (default: `</think>`).
    pub reasoning_close_tag: String,
}

impl Default for StreamParserOptions {
    fn default() -> Self {
        Self {
            pre_opened_think: false,
            reasoning_open_tag: "<think>".to_string(),
            reasoning_close_tag: "</think>".to_string(),
        }
    }
}

/// Incremental stream parser that detects thinking blocks in real-time.
pub struct StreamParser {
    state: ParserState,
    buffer: String,
    open_tag: String,
    close_tag: String,
    /// Current thinking content (accumulated from ReasoningDelta events).
    current_thinking: String,
    /// Whether we're currently inside a think block.
    in_think: bool,
}

impl StreamParser {
    /// Create a new stream parser with the given options.
    pub fn new(options: StreamParserOptions) -> Self {
        let state = if options.pre_opened_think {
            ParserState::InsideThink
        } else {
            ParserState::Preamble
        };
        Self {
            state,
            buffer: String::new(),
            open_tag: options.reasoning_open_tag,
            close_tag: options.reasoning_close_tag,
            current_thinking: String::new(),
            in_think: options.pre_opened_think,
        }
    }

    /// Get the current thinking content (accumulated from all ReasoningDelta events).
    pub fn current_thinking(&self) -> &str {
        &self.current_thinking
    }

    /// Check if we're currently inside a think block.
    pub fn in_think_block(&self) -> bool {
        self.in_think
    }

    /// Clear the accumulated thinking content (call after displaying it).
    pub fn clear_thinking(&mut self) {
        self.current_thinking.clear();
    }

    /// Feed a chunk of raw model text; returns any events produced.
    pub fn push(&mut self, chunk: &str) -> Vec<StreamEvent> {
        if chunk.is_empty() {
            return Vec::new();
        }
        self.buffer.push_str(chunk);
        self.advance()
    }

    /// Flush pending state at stream end; emits close events if needed.
    pub fn end(&mut self) -> Vec<StreamEvent> {
        let mut out = self.advance();

        match self.state {
            ParserState::InsideThink => {
                // Emit any remaining buffer as reasoning
                if !self.buffer.is_empty() {
                    self.current_thinking.push_str(&self.buffer);
                    out.push(StreamEvent::ReasoningDelta(self.buffer.clone()));
                    self.buffer.clear();
                }
                out.push(StreamEvent::ReasoningClose);
                self.state = ParserState::Done;
                self.in_think = false;
            }
            ParserState::ReplyText => {
                if !self.buffer.is_empty() {
                    out.push(StreamEvent::ReplyDelta(self.buffer.clone()));
                    self.buffer.clear();
                }
                out.push(StreamEvent::ReplyClose);
                self.state = ParserState::Done;
            }
            ParserState::Preamble => {
                // Emit any remaining buffer as reply
                if !self.buffer.is_empty() {
                    out.push(StreamEvent::ReplyDelta(self.buffer.clone()));
                    self.buffer.clear();
                }
                self.state = ParserState::Done;
            }
            _ => {
                self.buffer.clear();
                self.state = ParserState::Done;
            }
        }

        out
    }

    fn advance(&mut self) -> Vec<StreamEvent> {
        let mut out = Vec::new();
        let mut keep_going = true;

        while keep_going {
            keep_going = false;

            match self.state {
                ParserState::Preamble => {
                    // Look for opening tag or JSON tool start
                    if let Some(idx) = self.buffer.find(&self.open_tag) {
                        // Emit any text before the tag as ReplyDelta
                        let before = &self.buffer[..idx];
                        if !before.is_empty() {
                            out.push(StreamEvent::ReplyDelta(before.to_string()));
                        }
                        self.buffer = self.buffer[idx + self.open_tag.len()..].to_string();
                        self.state = ParserState::InsideThink;
                        self.in_think = true;
                        out.push(StreamEvent::ReasoningOpen);
                        keep_going = true;
                        continue;
                    }

                    // Check if buffer ends with a partial tag match
                    let partial = self.hold_possible_tag_start();
                    if !partial.is_empty() {
                        // Keep the partial match in buffer, don't emit anything
                        // The safe emit index ensures we don't emit partial tag prefixes
                        let safe_idx = self.find_safe_emit_index();
                        if safe_idx > 0 {
                            let emit: String = self.buffer[..safe_idx].to_string();
                            self.buffer = self.buffer[safe_idx..].to_string();
                            if !emit.is_empty() {
                                out.push(StreamEvent::ReplyDelta(emit));
                            }
                        }
                    } else {
                        // No partial match, emit everything as ReplyDelta
                        if !self.buffer.is_empty() {
                            let emit = self.buffer.clone();
                            self.buffer.clear();
                            out.push(StreamEvent::ReplyDelta(emit));
                        }
                    }
                }

                ParserState::InsideThink => {
                    // Look for closing tag
                    if let Some(idx) = self.buffer.find(&self.close_tag) {
                        let before = &self.buffer[..idx];
                        if !before.is_empty() {
                            self.current_thinking.push_str(before);
                            out.push(StreamEvent::ReasoningDelta(before.to_string()));
                        }
                        out.push(StreamEvent::ReasoningClose);
                        self.buffer = self.buffer[idx + self.close_tag.len()..].to_string();
                        self.state = ParserState::Preamble;
                        self.in_think = false;
                        keep_going = true;
                        continue;
                    }

                    // Emit safe portion (hold back enough for a partial close tag)
                    let holdback = self.close_tag.len().max(16);
                    let safe_idx = self.find_safe_reasoning_emit_index(holdback);
                    if safe_idx > 0 {
                        let emit: String = self.buffer[..safe_idx].to_string();
                        self.buffer = self.buffer[safe_idx..].to_string();
                        self.current_thinking.push_str(&emit);
                        out.push(StreamEvent::ReasoningDelta(emit));
                    }
                }

                ParserState::ReplyText => {
                    // In reply text, emit everything until end
                    // (simplified - full version would handle JSON escape sequences)
                    if !self.buffer.is_empty() {
                        let text = self.buffer.clone();
                        self.buffer.clear();
                        out.push(StreamEvent::ReplyDelta(text));
                    }
                }

                ParserState::Done => {
                    self.buffer.clear();
                }
            }
        }

        out
    }

    /// Check if buffer ends with a prefix of the open tag.
    fn hold_possible_tag_start(&self) -> String {
        let max_probe = self.buffer.len().min(self.open_tag.len().saturating_sub(1).max(1));
        for len in (1..=max_probe).rev() {
            let tag_prefix = &self.open_tag[..len];
            if self.buffer.ends_with(tag_prefix) {
                return tag_prefix.to_string();
            }
        }
        String::new()
    }

    /// Find the safest index to emit reasoning text without splitting a close tag.
    fn find_safe_reasoning_emit_index(&self, holdback_len: usize) -> usize {
        let window_len = self.buffer.len().min(holdback_len);
        if window_len == 0 {
            return self.buffer.len();
        }
        let window = &self.buffer[self.buffer.len() - window_len..];
        let overlap = self.longest_trailing_prefix(window);
        self.buffer.len() - overlap
    }

    /// Find the longest prefix of `prefix` that matches a trailing substring of `buffer`.
    fn longest_trailing_prefix(&self, prefix: &str) -> usize {
        let max_probe = self.buffer.len().min(prefix.len().saturating_sub(1));
        for len in (1..=max_probe).rev() {
            let prefix_slice = &prefix[..len];
            if self.buffer.ends_with(prefix_slice) {
                return len;
            }
        }
        0
    }

    /// Find the safe emit index in preamble mode.
    fn find_safe_emit_index(&self) -> usize {
        // In preamble, we need to hold back enough for a partial open tag
        let holdback = self.open_tag.len().max(16);
        self.find_safe_reasoning_emit_index(holdback)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_no_think_tags() {
        let mut parser = StreamParser::new(StreamParserOptions::default());
        let events = parser.push("Hello world");
        // Text without think tags is emitted as ReplyDelta
        assert_eq!(events.len(), 1);
        assert_eq!(events[0], StreamEvent::ReplyDelta("Hello world".to_string()));
    }

    #[test]
    fn test_think_block() {
        let mut parser = StreamParser::new(StreamParserOptions::default());
        let mut events = parser.push("<think>Let me think</think>Hello");
        assert_eq!(events.len(), 4);
        assert_eq!(events[0], StreamEvent::ReasoningOpen);
        assert_eq!(events[1], StreamEvent::ReasoningDelta("Let me think".to_string()));
        assert_eq!(events[2], StreamEvent::ReasoningClose);
        assert_eq!(events[3], StreamEvent::ReplyDelta("Hello".to_string()));
    }

    #[test]
    fn test_think_across_chunks() {
        let mut parser = StreamParser::new(StreamParserOptions::default());
        let mut events = parser.push("<think>Let me");
        assert_eq!(events.len(), 2);
        assert_eq!(events[0], StreamEvent::ReasoningOpen);
        assert_eq!(events[1], StreamEvent::ReasoningDelta("Let me".to_string()));

        events = parser.push(" think</think>Hi");
        assert_eq!(events.len(), 3);
        assert_eq!(events[0], StreamEvent::ReasoningDelta(" think".to_string()));
        assert_eq!(events[1], StreamEvent::ReasoningClose);
        assert_eq!(events[2], StreamEvent::ReplyDelta("Hi".to_string()));
    }

    #[test]
    fn test_end_flushes_think() {
        let mut parser = StreamParser::new(StreamParserOptions::default());
        parser.push("<think>reasoning");
        let events = parser.end();
        // end() only needs to close the think block
        // The reasoning content was already emitted during push()
        assert_eq!(events.len(), 1);
        assert_eq!(events[0], StreamEvent::ReasoningClose);
    }

    #[test]
    fn test_end_flushes_reply() {
        let mut parser = StreamParser::new(StreamParserOptions::default());
        let mut all_events = parser.push("<think>reasoning</think>");
        all_events.extend(parser.push("Hello world"));
        all_events.extend(parser.end());
        // Full sequence: ReasoningOpen, ReasoningDelta, ReasoningClose, ReplyDelta
        assert_eq!(all_events.len(), 4);
        assert_eq!(all_events[0], StreamEvent::ReasoningOpen);
        assert_eq!(all_events[1], StreamEvent::ReasoningDelta("reasoning".to_string()));
        assert_eq!(all_events[2], StreamEvent::ReasoningClose);
        assert_eq!(all_events[3], StreamEvent::ReplyDelta("Hello world".to_string()));
    }

    #[test]
    fn test_pre_opened_think() {
        let mut parser = StreamParser::new(StreamParserOptions {
            pre_opened_think: true,
            ..Default::default()
        });
        let events = parser.push("thinking");
        assert_eq!(events.len(), 1);
        assert_eq!(events[0], StreamEvent::ReasoningDelta("thinking".to_string()));
    }
}
