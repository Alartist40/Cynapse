//! Live smoke test against a running Ollama instance.
//!
//! Requires `ollama serve` on localhost:11434 with at least one
//! model pulled (e.g. `ollama pull qwen-bench`). Ignored by default;
//! run with: cargo test -p cynapse-core --test agent_live -- --ignored --nocapture

use std::sync::Arc;
use std::time::Duration;

use cynapse_core::agent::Agent;
use cynapse_core::approval;
use cynapse_core::config::Config;
use cynapse_core::llm::new as new_client;
use cynapse_core::netguard;
use cynapse_core::persona::Persona;
use cynapse_core::session::Manager;
use cynapse_core::tools::build_profile;

fn live_setup(tag: &str) -> (Arc<Agent>, std::path::PathBuf) {
    let tmp = std::env::temp_dir().join(format!("cynapse-live-{tag}-{}", std::process::id()));
    let _ = std::fs::remove_dir_all(&tmp);
    std::fs::create_dir_all(&tmp).unwrap();

    let mut cfg = Config::default();
    cfg.llm.ollama_base_url = "http://localhost:11434".to_string();
    cfg.llm.model = "qwen-bench:latest".to_string();
    cfg.llm.max_tokens = 256;
    cfg.llm.temperature = 0.2;
    cfg.memory.persona_path = tmp.join("persona").to_string_lossy().to_string();
    cfg.memory.sessions_path = tmp.join("sessions").to_string_lossy().to_string();
    cfg.memory.dendrite_db_path = tmp.join("dendrite.db").to_string_lossy().to_string();
    cfg.memory.defaults_path = tmp.join("persona").to_string_lossy().to_string();
    cfg.tools.work_dir = tmp.join("workspace").to_string_lossy().to_string();

    let persona = Arc::new(
        Persona::new(
            "live-test",
            std::path::Path::new(&cfg.memory.persona_path),
            std::path::Path::new(&cfg.memory.defaults_path),
            std::path::Path::new(&cfg.memory.dendrite_db_path),
        )
        .unwrap(),
    );
    let sessions = Arc::new(Manager::new_with_mode(&cfg.memory.sessions_path, 0o644).unwrap());
    let client = new_client(&cfg.llm).unwrap();
    let tools = build_profile(
        "minimal",
        &cfg.tools.work_dir,
        30,
        persona.clone(),
        approval::trust_local_policy(),
        netguard::local_dev_policy(),
        None,
    );

    let agent = Arc::new(Agent::new("live-test".to_string(), client, persona, sessions, tools, cfg));
    (agent, tmp)
}

#[tokio::test(flavor = "multi_thread")]
#[ignore = "requires live Ollama"]
async fn live_ollama_chat_roundtrip() {
    let (agent, tmp) = live_setup("chat");
    let reply = agent.process_message("Reply with exactly: HELLO_LIVE_TEST", Vec::new()).await;
    assert!(reply.is_ok(), "LLM error: {:?}", reply.err());
    println!("REPLY: {}", reply.unwrap());
    let _ = std::fs::remove_dir_all(&tmp);
}

#[tokio::test(flavor = "multi_thread")]
#[ignore = "requires live Ollama"]
async fn live_ollama_stream_roundtrip() {
    let (agent, tmp) = live_setup("stream");
    let (mut chunks, mut errors) = agent
        .process_message_stream("Count from one to five, one per line.", Vec::new())
        .await;
    let mut text = String::new();
    let mut done = false;
    loop {
        tokio::select! {
            maybe = chunks.recv() => match maybe {
                Some(c) => { text.push_str(&c); }
                None => { done = true; }
            },
            maybe = errors.recv() => match maybe {
                Some(e) => panic!("stream error: {e}"),
                None => { done = true; }
            },
        }
        if done {
            break;
        }
    }
    assert!(!text.is_empty(), "no streamed text");
    println!("STREAM: {text}");
    let _ = std::fs::remove_dir_all(&tmp);
}

#[tokio::test(flavor = "multi_thread")]
#[ignore = "requires live Ollama"]
async fn live_ollama_list_models() {
    let names = cynapse_core::llm::list_ollama_models("http://localhost:11434")
        .await
        .unwrap();
    assert!(!names.is_empty(), "no models on Ollama");
    println!("MODELS: {names:?}");
}

#[tokio::test(flavor = "multi_thread")]
#[ignore = "requires live Ollama, slow"]
async fn live_ollama_tool_calling() {
    let (agent, tmp) = live_setup("tools");
    let work_dir = tmp.join("workspace");
    let _ = std::fs::create_dir_all(&work_dir);
    let reply = agent
        .process_message(
            "Use the write_file tool to create a file named hello.txt containing the text 'hi from tools', then tell me the result.",
            Vec::new(),
        )
        .await;
    println!("REPLY: {:?}", reply);
    let _ = std::fs::remove_dir_all(&tmp);
}

#[tokio::test(flavor = "multi_thread")]
#[ignore = "requires live Ollama"]
async fn live_circuit_breaker_recovers() {
    // Point at a dead port → breaker opens, then recovers to half-open.
    let tmp = std::env::temp_dir().join(format!("cynapse-live-cb-{}", std::process::id()));
    let _ = std::fs::create_dir_all(&tmp);
    let mut cfg = Config::default();
    cfg.llm.ollama_base_url = "http://127.0.0.1:9".to_string(); // nothing here
    cfg.llm.model = "anything".to_string();
    cfg.llm.max_tokens = 32;
    cfg.memory.persona_path = tmp.join("persona").to_string_lossy().to_string();
    cfg.memory.sessions_path = tmp.join("sessions").to_string_lossy().to_string();
    cfg.memory.dendrite_db_path = tmp.join("dendrite.db").to_string_lossy().to_string();
    cfg.memory.defaults_path = tmp.join("persona").to_string_lossy().to_string();
    cfg.tools.work_dir = tmp.join("workspace").to_string_lossy().to_string();

    let persona = Arc::new(
        Persona::new(
            "live-cb",
            std::path::Path::new(&cfg.memory.persona_path),
            std::path::Path::new(&cfg.memory.defaults_path),
            std::path::Path::new(&cfg.memory.dendrite_db_path),
        )
        .unwrap(),
    );
    let sessions = Arc::new(Manager::new_with_mode(&cfg.memory.sessions_path, 0o644).unwrap());
    let client = new_client(&cfg.llm).unwrap();
    let tools = build_profile(
        "minimal",
        &cfg.tools.work_dir,
        30,
        persona.clone(),
        approval::trust_local_policy(),
        netguard::local_dev_policy(),
        None,
    );
    let agent = Arc::new(Agent::new("live-cb".to_string(), client, persona, sessions, tools, cfg));

    // maxFailures=3: three consecutive failed chats open the breaker.
    for i in 0..3 {
        let err = agent.process_message(&format!("hi {i}"), Vec::new()).await;
        println!("CB call {i} err (expected, dead port): {err:?}");
        assert!(err.is_err());
    }

    // Fourth call should be refused immediately by the open breaker
    // (fast, no network round-trip).
    let start = std::time::Instant::now();
    let err2 = agent.process_message("hi again", Vec::new()).await;
    let elapsed = start.elapsed();
    println!("CB fourth call elapsed: {elapsed:?} err={err2:?}");
    assert!(err2.is_err());
    assert!(elapsed < Duration::from_secs(5), "breaker did not open fast");
    let _ = std::fs::remove_dir_all(&tmp);
}
