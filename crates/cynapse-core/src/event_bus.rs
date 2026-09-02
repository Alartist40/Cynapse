//! Event bus for agent loop events, enabling TUI-reactive rendering.
//!
//! Ported from atomic-agent's event bus pattern. Events are dispatched
//! from the agent loop to subscribers (TUI, logging, etc.) via channels.

use std::sync::Arc;

use tokio::sync::broadcast;

/// Events emitted by the agent loop during processing.
#[derive(Debug, Clone)]
pub enum AgentLoopEvent {
    /// A new user message was received.
    UserMessage(String),
    /// The agent started processing a turn.
    TurnStarted,
    /// A streaming chunk of text was received.
    StreamDelta(String),
    /// A thinking/reasoning chunk was received.
    ThinkingDelta(String),
    /// The thinking block opened.
    ThinkingOpen,
    /// The thinking block closed.
    ThinkingClose,
    /// A tool call is about to execute.
    ToolCallStarted {
        name: String,
        arguments: String,
    },
    /// A tool call completed.
    ToolCallCompleted {
        name: String,
        result: String,
    },
    /// The agent finished generating a response.
    AssistantReply(String),
    /// The turn completed.
    TurnFinished,
    /// An error occurred.
    Error(String),
    /// The provider switched (fallback chain).
    ProviderSwitched {
        from: String,
        to: String,
        reason: String,
    },
}

/// Shared event bus for agent loop events.
pub struct EventBus {
    sender: broadcast::Sender<AgentLoopEvent>,
}

impl EventBus {
    /// Create a new event bus with the given channel capacity.
    pub fn new(capacity: usize) -> Arc<Self> {
        let (sender, _) = broadcast::channel(capacity);
        Arc::new(Self { sender })
    }

    /// Subscribe to events. Drops old events if the subscriber falls behind.
    pub fn subscribe(&self) -> broadcast::Receiver<AgentLoopEvent> {
        self.sender.subscribe()
    }

    /// Emit an event to all subscribers.
    pub fn emit(&self, event: AgentLoopEvent) {
        // Ignore send errors (no active subscribers)
        let _ = self.sender.send(event);
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn test_event_bus_basic() {
        let bus = EventBus::new(32);
        let mut rx = bus.subscribe();

        bus.emit(AgentLoopEvent::UserMessage("hello".to_string()));

        let event = rx.recv().await.unwrap();
        match event {
            AgentLoopEvent::UserMessage(msg) => assert_eq!(msg, "hello"),
            _ => panic!("expected UserMessage"),
        }
    }

    #[tokio::test]
    async fn test_event_bus_multiple_subscribers() {
        let bus = EventBus::new(32);
        let mut rx1 = bus.subscribe();
        let mut rx2 = bus.subscribe();

        bus.emit(AgentLoopEvent::TurnStarted);

        let e1 = rx1.recv().await.unwrap();
        let e2 = rx2.recv().await.unwrap();

        assert!(matches!(e1, AgentLoopEvent::TurnStarted));
        assert!(matches!(e2, AgentLoopEvent::TurnStarted));
    }
}
