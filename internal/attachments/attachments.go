package attachments

import (
	"encoding/base64"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
)

// AttachmentType describes the kind of attachment.
type AttachmentType string

const (
	TypeImage AttachmentType = "image"
	TypeText  AttachmentType = "text"
	TypePDF   AttachmentType = "pdf"
	TypeBinary AttachmentType = "binary"
)

// Attachment is a file that can be sent to the model.
type Attachment struct {
	Type     AttachmentType `json:"type"`
	Filename string         `json:"filename"`
	MIME     string         `json:"mime"`
	Content  string         `json:"content"`  // text content or base64 for images
	Path     string         `json:"path"`     // original path
}

// AttachmentDir is the default directory users can place files in.
const AttachmentDir = "workspace"

// Load reads a file from the given path and returns an Attachment.
func Load(path string) (*Attachment, error) {
	info, err := os.Stat(path)
	if err != nil {
		return nil, fmt.Errorf("stat file: %w", err)
	}
	if info.IsDir() {
		return nil, fmt.Errorf("cannot attach a directory")
	}

	ext := strings.ToLower(filepath.Ext(path))
	att := &Attachment{
		Filename: filepath.Base(path),
		Path:     path,
	}

	switch ext {
	case ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp":
		att.Type = TypeImage
		att.MIME = mimeForExt(ext)
		data, err := os.ReadFile(path)
		if err != nil {
			return nil, fmt.Errorf("reading image: %w", err)
		}
		att.Content = base64.StdEncoding.EncodeToString(data)

	case ".txt", ".md", ".csv", ".json", ".yaml", ".yml", ".go", ".py", ".js", ".ts", ".html", ".css", ".sh", ".xml", ".log":
		att.Type = TypeText
		att.MIME = "text/plain"
		data, err := os.ReadFile(path)
		if err != nil {
			return nil, fmt.Errorf("reading text: %w", err)
		}
		att.Content = string(data)

	case ".pdf":
		att.Type = TypePDF
		att.MIME = "application/pdf"
		// Try to extract text with pdftotext if available
		if text, err := extractPDFText(path); err == nil {
			att.Content = text
		} else {
			// Fallback: base64 encode the PDF for models that support it
			data, err := os.ReadFile(path)
			if err != nil {
				return nil, fmt.Errorf("reading pdf: %w", err)
			}
			att.Content = base64.StdEncoding.EncodeToString(data)
		}

	default:
		att.Type = TypeBinary
		att.MIME = "application/octet-stream"
		data, err := os.ReadFile(path)
		if err != nil {
			return nil, fmt.Errorf("reading file: %w", err)
		}
		att.Content = base64.StdEncoding.EncodeToString(data)
	}

	return att, nil
}

// ToImageURL returns a data URI for image attachments.
func (a *Attachment) ToImageURL() string {
	if a.Type != TypeImage {
		return ""
	}
	return fmt.Sprintf("data:%s;base64,%s", a.MIME, a.Content)
}

// ToText returns text content for text/pdf attachments.
func (a *Attachment) ToText() string {
	if a.Type == TypeText || a.Type == TypePDF {
		return a.Content
	}
	return ""
}

// ToMarkdown returns a markdown representation of the attachment.
func (a *Attachment) ToMarkdown() string {
	switch a.Type {
	case TypeImage:
		return fmt.Sprintf("![%s](%s)", a.Filename, a.ToImageURL())
	case TypeText, TypePDF:
		return fmt.Sprintf("\n---\n**Attachment: %s**\n```\n%s\n```\n---\n", a.Filename, a.Content)
	default:
		return fmt.Sprintf("\n---\n**Attachment: %s** (binary, %d bytes base64)\n---\n", a.Filename, len(a.Content))
	}
}

// FindInWorkspace looks for a filename in the workspace directory and common subdirs.
func FindInWorkspace(filename, workspaceDir string) (string, error) {
	// Direct path
	if filepath.IsAbs(filename) {
		if _, err := os.Stat(filename); err == nil {
			return filename, nil
		}
		return "", fmt.Errorf("file not found: %s", filename)
	}

	// Try workspace root
	candidates := []string{
		filepath.Join(workspaceDir, filename),
		filepath.Join(workspaceDir, "uploads", filename),
		filepath.Join(workspaceDir, "images", filename),
		filepath.Join(workspaceDir, "documents", filename),
	}

	for _, c := range candidates {
		if _, err := os.Stat(c); err == nil {
			return c, nil
		}
	}

	return "", fmt.Errorf("file not found in workspace: %s", filename)
}

// ListWorkspaceFiles returns all files in the workspace that could be attached.
func ListWorkspaceFiles(workspaceDir string) ([]string, error) {
	var files []string
	err := filepath.Walk(workspaceDir, func(path string, info os.FileInfo, err error) error {
		if err != nil || info.IsDir() {
			return nil
		}
		files = append(files, path)
		return nil
	})
	return files, err
}

func mimeForExt(ext string) string {
	switch ext {
	case ".png":
		return "image/png"
	case ".jpg", ".jpeg":
		return "image/jpeg"
	case ".gif":
		return "image/gif"
	case ".bmp":
		return "image/bmp"
	case ".webp":
		return "image/webp"
	default:
		return "image/png"
	}
}

func extractPDFText(path string) (string, error) {
	cmd := execCommand("pdftotext", path, "-")
	out, err := cmd.Output()
	if err != nil {
		return "", err
	}
	return string(out), nil
}

// execCommand is overridden in tests.
var execCommand = exec.Command
