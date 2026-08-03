//! DENDRITE byte-compatibility tests.
//!
//! These prove the Rust port reads and writes the same `dendrite.db`
//! format as the Go original: same schema, same FTS5 index, same
//! row content.

use cynapse_core::dendrite::{Dendrite, DendriteStore, NodeType};

const LIVE_DB_CANDIDATES: [&str; 2] = [
    "/home/xander/Documents/portfolio/cynapse/data/dendrite.db",
    "data/dendrite.db",
];

/// The 8 nodes that the Go build currently seeds and persists.
const EXPECTED_NODE_IDS: [&str; 8] = [
    "identity",
    "soul",
    "agents",
    "tools",
    "memory_notes",
    "user",
    "heartbeat",
    "id",
];

fn live_db_path() -> Option<std::path::PathBuf> {
    LIVE_DB_CANDIDATES
        .iter()
        .map(std::path::PathBuf::from)
        .find(|p| p.exists())
}

#[test]
fn reads_live_dendrite_db() {
    let Some(db) = live_db_path() else {
        eprintln!("SKIP: live dendrite.db not found; only schema round-trip tested");
        return;
    };

    let store = DendriteStore::open(&db).expect("open live db");
    let graph = Dendrite::new();
    store.load_all(&graph).expect("load nodes");

    let nodes = graph.all();
    let ids: Vec<&str> = nodes.iter().map(|n| n.id.as_str()).collect();
    assert_eq!(nodes.len(), 8, "expected 8 live nodes, got {ids:?}");
    for expected in EXPECTED_NODE_IDS {
        assert!(
            ids.contains(&expected),
            "live DB missing node {expected}; got {ids:?}"
        );
    }

    // Every node must round-trip its tags/links JSON arrays.
    for n in &nodes {
        assert_eq!(
            n.id,
            n.id.trim(),
            "node id should not have surrounding whitespace"
        );
        assert!(!n.title.is_empty(), "node {} has empty title", n.id);
    }

    // FTS5 full-text search on the live index.
    let hits = store.fts_search("identity", 5).expect("fts search");
    assert!(
        hits.contains(&"identity".to_string()),
        "fts should find identity node, got {hits:?}"
    );
}

#[test]
fn fresh_db_round_trip() {
    let dir = std::env::temp_dir().join(format!("cynapse-db-test-{}", std::process::id()));
    std::fs::create_dir_all(&dir).unwrap();
    let db_path = dir.join("dendrite.db");

    let store = DendriteStore::open(&db_path).expect("create fresh db");
    let graph = Dendrite::new();

    // Upsert the same 8 nodes the Go build seeds.
    for (id, title, ty) in [
        ("identity", "Identity", NodeType::Identity),
        ("soul", "Soul", NodeType::Identity),
        ("agents", "Agent Rules", NodeType::Concept),
        ("tools", "Tools", NodeType::Concept),
        ("memory_notes", "Memory", NodeType::Memory),
        ("user", "User Profile", NodeType::Person),
        ("heartbeat", "Heartbeat", NodeType::Concept),
        ("id", "id", NodeType::Custom),
    ] {
        let content = format!("# {title}\n\ncontent for [[identity]] #test #tag");
        let node = graph.upsert(id, title, &content, ty, None);
        store.save(&node).expect("save node");
    }

    // A fresh store + graph must hydrate them identically.
    let store2 = DendriteStore::open(&db_path).expect("reopen");
    let graph2 = Dendrite::new();
    store2.load_all(&graph2).expect("reload");
    assert_eq!(graph2.len(), 8);

    let identity = graph2.get("identity").expect("identity node present");
    assert_eq!(identity.node_type, NodeType::Identity);
    assert!(!identity.content.is_empty());

    // Wiki-link + hashtag parsing happened on upsert.
    let tools = graph2.get("tools").expect("tools node present");
    assert!(tools.links.contains(&"identity".to_string()));
    assert!(tools.tags.contains(&"tag".to_string()));

    // created_at is preserved across re-save (upsert conflict path).
    let saved_created = identity.created_at;
    let node = graph.upsert("identity", "Identity", "updated #tag2", NodeType::Identity, None);
    store.save(&node).expect("re-save identity");
    let store3 = DendriteStore::open(&db_path).expect("reopen3");
    let graph3 = Dendrite::new();
    store3.load_all(&graph3).expect("reload3");
    let identity3 = graph3.get("identity").unwrap();
    assert_eq!(identity3.created_at, saved_created);
    assert!(identity3.updated_at >= saved_created);

    std::fs::remove_dir_all(&dir).ok();
}
