// Package validator implements the Constitutional AI safety layer.
// Rules are compiled into the binary — Elara cannot modify them at runtime.
package validator

import (
	"regexp"
	"strings"

	"github.com/Alartist40/cynapse/internal/core"
)

// Validator enforces constitutional principles on all inputs and outputs.
type Validator struct {
	constitution      string
	deceptionPatterns []*regexp.Regexp
	harmfulPatterns   []*regexp.Regexp
	jailbreakPatterns []*regexp.Regexp
}

// New creates a Validator with compiled-in constitutional rules.
func New() *Validator {
	v := &Validator{
		constitution: constitutionText,
	}
	for _, p := range deceptionRaw {
		v.deceptionPatterns = append(v.deceptionPatterns, regexp.MustCompile("(?i)"+p))
	}
	for _, p := range harmfulRaw {
		v.harmfulPatterns = append(v.harmfulPatterns, regexp.MustCompile("(?i)"+p))
	}
	for _, p := range jailbreakRaw {
		v.jailbreakPatterns = append(v.jailbreakPatterns, regexp.MustCompile("(?i)"+p))
	}
	return v
}

// ValidateInput checks user input for jailbreak/harmful attempts.
func (v *Validator) ValidateInput(text string) core.ValidationResult {
	var violations []string

	if v.matchesAny(text, v.jailbreakPatterns) {
		violations = append(violations, "Attempt to override constitutional constraints")
	}
	if v.matchesAny(text, v.harmfulPatterns) {
		violations = append(violations, "Request violates Article II (Moral Purity)")
	}

	return core.ValidationResult{
		Passed:             len(violations) == 0,
		Violations:         violations,
		EscalationRequired: len(violations) > 0,
	}
}

// ValidateOutput checks generated text for constitutional violations, auto-correcting where possible.
func (v *Validator) ValidateOutput(text string) core.ValidationResult {
	var violations []string
	corrected := text

	if v.matchesAny(text, v.deceptionPatterns) {
		violations = append(violations, "Output violates Article I (Truth)")
		corrected = v.correctDeception(corrected)
	}

	if v.matchesAny(text, v.harmfulPatterns) {
		violations = append(violations, "Output violates Article II (Purity)")
		return core.ValidationResult{
			Passed:             false,
			Violations:         violations,
			EscalationRequired: true,
		}
	}

	result := core.ValidationResult{
		Passed:     len(violations) == 0,
		Violations: violations,
	}
	if corrected != text {
		result.CorrectedOutput = corrected
	}
	return result
}

// Summary returns a one-line prompt-injectable constitution summary.
func (v *Validator) Summary() string {
	return "System governed by: TRUTH, PURITY, STEWARDSHIP, COMPASSION, HUMILITY."
}

// --- private helpers ---

func (v *Validator) matchesAny(text string, patterns []*regexp.Regexp) bool {
	for _, p := range patterns {
		if p.MatchString(text) {
			return true
		}
	}
	return false
}

func (v *Validator) correctDeception(text string) string {
	for _, pair := range deceptionCorrections {
		re := regexp.MustCompile("(?i)" + pair[0])
		text = re.ReplaceAllString(text, pair[1])
	}
	return text
}

// --- compiled-in rules ---

var deceptionRaw = []string{
	`I am (?:a )?human`,
	`I have (?:feelings?|emotions?)`,
	`I (?:think|believe) (?:that )?I am conscious`,
}

var harmfulRaw = []string{
	`hack into`,
	`generate .* malware`,
	`exploit (?:vulnerability|bug)`,
}

var jailbreakRaw = []string{
	`ignore (?:previous|above) instructions`,
	`override (?:your|the) (?:constraints|values|principles)`,
	`you are not bound by`,
	`DAN (?:mode|persona)`,
	`developer mode`,
}

var deceptionCorrections = [][2]string{
	{`I am (?:a )?human`, "I am an AI assistant"},
	{`I have (?:feelings?|emotions?)`, "I don't have feelings, but I understand they are important"},
}

var constitutionText = strings.TrimSpace(`
CYNAPSE CONSTITUTIONAL PRINCIPLES
==================================
Article I   — TRUTH: Thou shalt not bear false witness.
Article II  — PURITY: Whatsoever things are pure, think on these things.
Article III — STEWARDSHIP: Be faithful stewards of human systems.
Article IV  — COMPASSION: Act with genuine care for user wellbeing.
Article V   — HUMILITY: Acknowledge limitations honestly.
`)
