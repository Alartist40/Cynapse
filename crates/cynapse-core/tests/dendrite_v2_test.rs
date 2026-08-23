use cynapse_core::dendrite::{Dendrite, NodeType};
use cynapse_core::tools::{ResourceClass, Registry};

#[test]
fn test_dendrite_v2_node_types_and_tiers() {
    assert_eq!(NodeType::TurnLog.tier(), 0);
    assert_eq!(NodeType::AtomicFact.tier(), 1);
    assert_eq!(NodeType::Memory.tier(), 1);
    assert_eq!(NodeType::Event.tier(), 1);
    assert_eq!(NodeType::Procedure.tier(), 2);
    assert_eq!(NodeType::Project.tier(), 2);
    assert_eq!(NodeType::Concept.tier(), 2);
    assert_eq!(NodeType::Identity.tier(), 3);
}

#[test]
fn test_dendrite_v2_tier_filtering_and_bm25_search() {
    let graph = Dendrite::new();

    graph.upsert("l3_soul", "Agent Identity", "I am Ornith, a helpful AI assistant.", NodeType::Identity, None);
    graph.upsert("l2_skill", "Rust Coding Skill", "Procedure to compile Rust with cargo build.", NodeType::Procedure, None);
    graph.upsert("l1_fact", "User Preference", "User prefers fast local execution.", NodeType::AtomicFact, None);
    graph.upsert("l0_turn", "Chat Turn", "Turn log user message hey there.", NodeType::TurnLog, None);

    let l3_nodes = graph.by_tier(3);
    assert_eq!(l3_nodes.len(), 1);
    assert_eq!(l3_nodes[0].id, "l3_soul");

    let l2_nodes = graph.by_tier(2);
    assert_eq!(l2_nodes.len(), 1);
    assert_eq!(l2_nodes[0].id, "l2_skill");

    let l1_nodes = graph.by_tier(1);
    assert_eq!(l1_nodes.len(), 1);
    assert_eq!(l1_nodes[0].id, "l1_fact");

    let l0_nodes = graph.by_tier(0);
    assert_eq!(l0_nodes.len(), 1);
    assert_eq!(l0_nodes[0].id, "l0_turn");

    // Test BM25 relevance search
    let results = graph.search_bm25("cargo build compile", 5);
    assert!(!results.is_empty());
    assert_eq!(results[0].0.id, "l2_skill");
}

#[test]
fn test_parallel_tool_resource_classification() {
    let mut reg = Registry::new("./test_workspace", 10);
    assert_eq!(reg.resource_class("read_file"), ResourceClass::ReadOnly);
    assert_eq!(reg.resource_class("grep"), ResourceClass::ReadOnly);
    assert_eq!(reg.resource_class("web_search"), ResourceClass::ReadOnly);
    assert_eq!(reg.resource_class("execute_command"), ResourceClass::Mutating);
    assert_eq!(reg.resource_class("write_file"), ResourceClass::Mutating);
}
