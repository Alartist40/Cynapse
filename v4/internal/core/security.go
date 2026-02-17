package core

import (
	"fmt"
	"path/filepath"
	"strings"
)

// ValidatePath ensures a path is within a base directory and is not a traversal attempt.
func ValidatePath(baseDir, targetPath string) (string, error) {
	absBase, err := filepath.Abs(baseDir)
	if err != nil {
		return "", fmt.Errorf("invalid base directory: %w", err)
	}

	// Join and clean
	fullPath := filepath.Join(absBase, targetPath)
	absPath, err := filepath.Abs(fullPath)
	if err != nil {
		return "", fmt.Errorf("invalid target path: %w", err)
	}

	// Check if absPath starts with absBase
	if !strings.HasPrefix(absPath, absBase) {
		return "", fmt.Errorf("path traversal attempt detected: %s is outside %s", targetPath, baseDir)
	}

	return absPath, nil
}
