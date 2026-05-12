package memory

import (
	"testing"
)

func TestDendrite_Upsert(t *testing.T) {
	d := NewDendrite()

	// Test basic upsert
	n1 := d.Upsert("node1", "Node 1", "Content with [[node2]]", NodeTypeConcept, nil)
	if n1.ID != "node1" {
		t.Errorf("expected ID node1, got %s", n1.ID)
	}
	if len(n1.Links) != 1 || n1.Links[0] != "node2" {
		t.Errorf("expected link to node2, got %v", n1.Links)
	}

	// Test backlink creation
	n2 := d.Upsert("node2", "Node 2", "Hello", NodeTypeConcept, nil)
	if len(n2.Backlinks) != 1 || n2.Backlinks[0] != "node1" {
		t.Errorf("expected backlink from node1, got %v", n2.Backlinks)
	}

	// Test update content and re-wire backlinks
	d.Upsert("node1", "Node 1", "Content with [[node3]]", NodeTypeConcept, nil)
	n2, _ = d.Get("node2")
	if len(n2.Backlinks) != 0 {
		t.Errorf("expected no backlinks for node2 after update, got %v", n2.Backlinks)
	}
	n3 := d.Upsert("node3", "Node 3", "Hi", NodeTypeConcept, nil)
	if len(n3.Backlinks) != 1 || n3.Backlinks[0] != "node1" {
		t.Errorf("expected backlink from node1 for node3, got %v", n3.Backlinks)
	}
}

func TestDendrite_Delete(t *testing.T) {
	d := NewDendrite()
	d.Upsert("node1", "Node 1", "[[node2]]", NodeTypeConcept, nil)
	d.Upsert("node2", "Node 2", "[[node1]]", NodeTypeConcept, nil)

	d.Delete("node1")

	if _, ok := d.Get("node1"); ok {
		t.Error("expected node1 to be deleted")
	}

	n2, _ := d.Get("node2")
	if len(n2.Links) != 0 {
		t.Errorf("expected node2 links to be cleaned up, got %v", n2.Links)
	}
}

func TestDendrite_Search(t *testing.T) {
	d := NewDendrite()
	d.Upsert("apple", "Apple", "Red fruit #fruit", NodeTypeConcept, []string{"fruit"})
	d.Upsert("banana", "Banana", "Yellow fruit #fruit", NodeTypeConcept, []string{"fruit"})
	d.Upsert("car", "Car", "Vehicle", NodeTypeConcept, nil)

	// Search by title
	results := d.Search("Apple")
	if len(results) != 1 || results[0].ID != "apple" {
		t.Errorf("expected apple, got %v", results)
	}

	// Search by tag
	results = d.ByTag("fruit")
	if len(results) != 2 {
		t.Errorf("expected 2 fruits, got %d", len(results))
	}

	// Search by content
	results = d.Search("vehicle")
	if len(results) != 1 || results[0].ID != "car" {
		t.Errorf("expected car, got %v", results)
	}
}

func TestDendrite_Neighbors(t *testing.T) {
	d := NewDendrite()
	d.Upsert("a", "A", "[[b]] [[c]]", NodeTypeConcept, nil)
	d.Upsert("b", "B", "[[d]]", NodeTypeConcept, nil)
	d.Upsert("c", "C", "", NodeTypeConcept, nil)
	d.Upsert("d", "D", "", NodeTypeConcept, nil)

	neighbors := d.Neighbors("a")
	if len(neighbors) != 2 {
		t.Errorf("expected 2 neighbors for a, got %d", len(neighbors))
	}

	neighbors = d.Neighbors("b")
	if len(neighbors) != 2 { // a (backlink) and d (link)
		t.Errorf("expected 2 neighbors for b, got %d", len(neighbors))
	}
}
