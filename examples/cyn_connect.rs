//! Replicates TUI startup: resolve config, build llm client (spawns leafcutter),
//! then do a streamed chat.
use std::sync::Arc;
use std::time::Duration;

use cynapse_core::config::Config as _;
use cynapse_core::llm::{Message, Request, Role};
use cynapse_core::llm::providers::Cancelled;

#[tokio::main]
async fn main() {
    let cfg = cynapse_core::config::load(std::path::Path::new("config.yaml")).expect("load config");
    println!("provider={} model={}", cfg.llm.provider, cfg.llm.model);
    println!("leafcutter_path={}", cfg.llm.leafcutter_path);

    let client = cynapse_core::llm::new(&cfg.llm).expect("llm::new (spawns leafcutter)");
    println!("OK connected: provider={} model={}", client.provider(), client.current_model());

    let req = Request {
        system_prompt: String::new(),
        messages: vec![Message::text(Role::User, "Hello! What is 2+2? Reply in one short sentence.")],
        tools: vec![],
        max_tokens: 30,
        temperature: 0.0,
    };
    let cancelled: Cancelled = Arc::new(std::sync::atomic::AtomicBool::new(false));
    let mut handle = client.chat_stream(&req, cancelled);
    let mut chunks = 0usize;
    let mut text = String::new();
    let deadline = tokio::time::sleep(Duration::from_secs(200));
    tokio::pin!(deadline);
    loop {
        tokio::select! {
            _ = &mut deadline => { eprintln!("TIMEOUT"); break; }
            c = handle.chunks.recv() => match c {
                Some(c) => { chunks += 1; text.push_str(&c); }
                None => break,
            },
            e = handle.errors.recv() => match e {
                Some(e) => { eprintln!("STREAM ERROR: {e:#}"); break; }
                None => break,
            },
        }
    }
    println!("chunks={}", chunks);
    println!("TEXT: {}", text.replace('\n', "\\n"));
}
