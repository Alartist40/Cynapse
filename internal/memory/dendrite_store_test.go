package memory

import (
	"os"
	"path/filepath"
	"testing"
)

func TestDendriteStore_Operations(t *testing.T) {
	tmpDir, err := os.MkdirTemp("", "dendrite_store_test")
	if err != nil {
		t.Fatal(err)
	}
	defer os.RemoveAll(tmpDir)

	dbPath := filepath.Join(tmpDir, "test.db")
	store, err := NewDendriteStore(dbPath)
	if err != nil {
		t.Fatalf("failed to create store: %v", err)
	}
	defer store.Close()

	// Test Save
	n1 := &Node{
		ID:      "test1",
		Title:   "Test Node 1",
		Content: "Hello world #test",
		Type:    NodeTypeConcept,
		Tags:    []string{"test"},
		Links:   []string{"test2"},
	}
	if err := store.Save(n1); err != nil {
		t.Errorf("failed to save node: %v", err)
	}

	// Test LoadAll
	d := NewDendrite()
	if err := store.LoadAll(d); err != nil {
		t.Errorf("failed to load nodes: %v", err)
	}
	if d.Len() != 1 {
		t.Errorf("expected 1 node, got %d", d.Len())
	}
	loaded, _ := d.Get("test1")
	if loaded.Title != n1.Title {
		t.Errorf("expected title %s, got %s", n1.Title, loaded.Title)
	}

	// Test FTSSearch (requires sqlite_fts5 tag)
	ids, err := store.FTSSearch("hello", 10)
	if err != nil {
		// FTS5 might not be available in all environments, but we should test it if possible
		t.Logf("FTSSearch error (expected if fts5 missing): %v", err)
	} else if len(ids) != 1 || ids[0] != "test1" {
		t.Errorf("expected FTS match test1, got %v", ids)
	}

	// Test Delete
	if err := store.Delete("test1"); err != nil {
		t.Errorf("failed to delete node: %v", err)
	}
	d2 := NewDendrite()
	store.LoadAll(d2)
	if d2.Len() != 0 {
		t.Errorf("expected 0 nodes after delete, got %d", d2.Len())
	}
}
