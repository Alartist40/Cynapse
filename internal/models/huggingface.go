package models

import (
	"encoding/json"
	"fmt"
	"net/http"
	"net/url"
	"strings"
	"time"
)

const hfAPI = "https://huggingface.co/api"

// ModelFile represents a single file in a HF model repo.
type ModelFile struct {
	RFilename string `json:"rfilename"`
	Size      int64  `json:"size"`
	OID       string `json:"oid"`
	LFS       *struct {
		OID   string `json:"oid"`
		Size  int64  `json:"size"`
		PointerSize int64 `json:"pointerSize"`
	} `json:"lfs,omitempty"`
}

// HFModel represents a model from the HuggingFace API.
type HFModel struct {
	ID       string      `json:"id"`
	Author   string      `json:"author"`
	Sha      string      `json:"sha"`
	Private  bool        `json:"private"`
	Tags     []string    `json:"tags"`
	Likes    int         `json:"likes"`
	Downloads int        `json:"downloads"`
	Siblings []ModelFile `json:"siblings"`
	// GGUF-specific metadata if available
	GGUF struct {
		Architecture string `json:"architecture"`
		ContextLength int  `json:"context_length"`
	} `json:"gguf,omitempty"`
}

// HFSearcher provides HuggingFace model search.
type HFSearcher struct {
	client    *http.Client
	authToken string
}

// NewHFSearcher creates a new HF search client.
func NewHFSearcher() *HFSearcher {
	return &HFSearcher{
		client: &http.Client{Timeout: 30 * time.Second},
	}
}

// SetAuthToken sets the Bearer token for authenticated requests.
func (s *HFSearcher) SetAuthToken(token string) {
	s.authToken = token
}

func (s *HFSearcher) authHeader(req *http.Request) {
	if s.authToken != "" {
		req.Header.Set("Authorization", "Bearer "+s.authToken)
	}
}

// Search queries the HuggingFace model hub for GGUF models.
func (s *HFSearcher) Search(query string, limit int) ([]HFModel, error) {
	if limit <= 0 || limit > 50 {
		limit = 20
	}

	u, _ := url.Parse(hfAPI + "/models")
	q := u.Query()
	q.Set("search", query)
	q.Set("filter", "gguf")
	q.Set("sort", "downloads")
	q.Set("direction", "-1")
	q.Set("limit", fmt.Sprintf("%d", limit))
	q.Set("full", "true")
	u.RawQuery = q.Encode()

	req, err := http.NewRequest("GET", u.String(), nil)
	if err != nil {
		return nil, err
	}
	s.authHeader(req)
	resp, err := s.client.Do(req)
	if err != nil {
		return nil, fmt.Errorf("HF search request: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("HF search HTTP %d", resp.StatusCode)
	}

	var models []HFModel
	if err := json.NewDecoder(resp.Body).Decode(&models); err != nil {
		return nil, fmt.Errorf("HF search decode: %w", err)
	}

	return models, nil
}

// treeFile is the response format from the /tree/main endpoint.
type treeFile struct {
	Type string `json:"type"`
	OID  string `json:"oid"`
	Size int64  `json:"size"`
	Path string `json:"path"`
	LFS  *struct {
		OID   string `json:"oid"`
		Size  int64  `json:"size"`
		PointerSize int64 `json:"pointerSize"`
	} `json:"lfs,omitempty"`
}

// ListFiles returns all GGUF files for a given model ID.
func (s *HFSearcher) ListFiles(modelID string) ([]ModelFile, error) {
	url := fmt.Sprintf("%s/models/%s/tree/main", hfAPI, modelID)
	req, err := http.NewRequest("GET", url, nil)
	if err != nil {
		return nil, err
	}
	s.authHeader(req)
	resp, err := s.client.Do(req)
	if err != nil {
		// Try without /tree/main for some models
		url = fmt.Sprintf("%s/models/%s", hfAPI, modelID)
		resp, err = s.client.Get(url)
		if err != nil {
			return nil, fmt.Errorf("HF list files: %w", err)
		}
		// For single model endpoint, we get model info with siblings
		defer resp.Body.Close()
		if resp.StatusCode != http.StatusOK {
			return nil, fmt.Errorf("HF list files HTTP %d", resp.StatusCode)
		}
		var info struct {
			Siblings []ModelFile `json:"siblings"`
		}
		if err := json.NewDecoder(resp.Body).Decode(&info); err != nil {
			return nil, fmt.Errorf("HF list files decode: %w", err)
		}
		return filterGGUF(info.Siblings), nil
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("HF list files HTTP %d", resp.StatusCode)
	}

	var treeFiles []treeFile
	if err := json.NewDecoder(resp.Body).Decode(&treeFiles); err != nil {
		return nil, fmt.Errorf("HF list files decode: %w", err)
	}

	// Convert tree files to ModelFile format
	var files []ModelFile
	for _, tf := range treeFiles {
		files = append(files, ModelFile{
			RFilename: tf.Path,
			Size:      tf.Size,
			OID:       tf.OID,
			LFS:       tf.LFS,
		})
	}
	return filterGGUF(files), nil
}

// DownloadURL returns the direct download URL for a file in a model repo.
func DownloadURL(modelID, filename string) string {
	return fmt.Sprintf("https://huggingface.co/%s/resolve/main/%s", modelID, filename)
}

// ModelPageURL returns the web page URL for a model.
func ModelPageURL(modelID string) string {
	return fmt.Sprintf("https://huggingface.co/%s", modelID)
}

func filterGGUF(files []ModelFile) []ModelFile {
	var out []ModelFile
	for _, f := range files {
		if strings.HasSuffix(strings.ToLower(f.RFilename), ".gguf") {
			out = append(out, f)
		}
	}
	return out
}

// IsShardedGGUF checks if a filename is a sharded GGUF part.
func IsShardedGGUF(filename string) bool {
	return strings.Contains(filename, "-of-") && strings.HasSuffix(strings.ToLower(filename), ".gguf")
}
