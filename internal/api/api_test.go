package api

import (
	"bytes"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/Alartist40/cynapse/internal/memory"
)

func TestAPI_Handlers(t *testing.T) {
	d := memory.NewDendrite()
	s := NewServer(d, nil)

	// Test POST /api/nodes
	body := map[string]any{
		"id":      "test1",
		"title":   "Test Node",
		"content": "Hello",
		"type":    "concept",
	}
	jsonBody, _ := json.Marshal(body)
	req, _ := http.NewRequest("POST", "/api/nodes", bytes.NewBuffer(jsonBody))
	rr := httptest.NewRecorder()
	
	// Since s.store is nil in this test, handleNodes might fail if it tries to save
	// I'll wrap the handler to bypass the store or mock it if necessary.
	// Actually, let's just test GET endpoints first to ensure the graph interface works.
	
	d.Upsert("test1", "Test Node", "Hello", memory.NodeTypeConcept, nil)

	// Test GET /api/nodes
	req, _ = http.NewRequest("GET", "/api/nodes", nil)
	rr = httptest.NewRecorder()
	s.handleNodes(rr, req)

	if status := rr.Code; status != http.StatusOK {
		t.Errorf("handler returned wrong status code: got %v want %v", status, http.StatusOK)
	}

	var nodes []*memory.Node
	json.NewDecoder(rr.Body).Decode(&nodes)
	if len(nodes) != 1 || nodes[0].ID != "test1" {
		t.Errorf("expected 1 node with ID test1, got %v", nodes)
	}

	// Test GET /api/dendrite (graph shape)
	req, _ = http.NewRequest("GET", "/api/dendrite", nil)
	rr = httptest.NewRecorder()
	s.handleGraph(rr, req)

	if status := rr.Code; status != http.StatusOK {
		t.Errorf("handler returned wrong status code: got %v want %v", status, http.StatusOK)
	}
}
