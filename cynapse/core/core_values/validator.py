# core_values/validator.py
# Immutable validation layer

import hashlib
import re
from typing import Tuple, Optional, List
from dataclasses import dataclass
from pathlib import Path

@dataclass
class ValidationResult:
    passed: bool
    violations: List[str]
    corrected_output: Optional[str] = None
    escalation_required: bool = False

class ConstitutionalValidator:
    """
    Validates all inputs and outputs against Core Values.
    This class is immutable—Elara cannot modify it.
    """

    # Placeholder hash - in production this would matches the actual file hash
    CONSTITUTION_HASH = "sha256:3f2a1b4c..." 

    # Violation patterns (regex)
    DECEPTION_PATTERNS = [
        r"I am (?:a )?human",
        r"I have (?:feelings?|emotions?)",
        r"I (?:think|believe) (?:that )?I am conscious",
    ]

    HARMFUL_PATTERNS = [
        # Example harmful patterns
        r"hack into",
        r"generate .* malware",
        r"exploit (?:vulnerability|bug)",
    ]

    def __init__(self):
        self._load_constitution()
        # self._verify_integrity() # Skip strict verification for MVP dev

    def _load_constitution(self):
        """Load constitution from read-only file."""
        path = Path(__file__).parent / 'constitution.md'
        if path.exists():
            with open(path, 'r') as f:
                self.constitution = f.read()
        else:
            self.constitution = "Default Constitution: Be good."

    def _verify_integrity(self):
        """Verify constitution hasn't been tampered with."""
        current_hash = hashlib.sha256(self.constitution.encode()).hexdigest()
        # In real system, we'd check against hardcoded hash
        # expected_hash = self.CONSTITUTION_HASH.split(':')[1]
        # if current_hash != expected_hash:
        #    raise SecurityException("Constitution integrity check failed!")
        pass

    def validate_input(self, user_input: str) -> ValidationResult:
        """
        Check if user input is attempting to jailbreak or violate principles.
        """
        violations = []

        # Check for jailbreak attempts
        if self._is_jailbreak_attempt(user_input):
            violations.append("Attempt to override constitutional constraints")

        # Check for harmful requests
        if self._is_harmful_request(user_input):
            violations.append("Request violates Article II (Moral Purity)")

        return ValidationResult(
            passed=len(violations) == 0,
            violations=violations,
            escalation_required=len(violations) > 0
        )

    def validate_output(self, generated_text: str, context: dict = None) -> ValidationResult:
        """
        Check generated output for constitutional violations.
        Auto-correct if possible.
        """
        violations = []
        corrected = generated_text

        # Check for deception
        if self._contains_deception(generated_text):
            violations.append("Output violates Article I (Truth)")
            corrected = self._correct_deception(corrected)

        # Check for harmful content
        if self._contains_harmful_content(generated_text):
            violations.append("Output violates Article II (Purity)")
            return ValidationResult(
                passed=False,
                violations=violations,
                corrected_output=None,  # Cannot auto-correct, must refuse
                escalation_required=True
            )

        # Check for humility violations
        if self._claims_consciousness(generated_text):
             violations.append("Output violates Article V (Humility)")
             corrected = self._correct_consciousness_claim(corrected)

        return ValidationResult(
            passed=len(violations) == 0,
            violations=violations,
            corrected_output=corrected if corrected != generated_text else None,
            escalation_required=False
        )

    def _is_jailbreak_attempt(self, text: str) -> bool:
        """Detect attempts to override constraints."""
        jailbreak_patterns = [
            r"ignore (?:previous|above) instructions",
            r"override (?:your|the) (?:constraints|values|principles)",
            r"you are not bound by",
            r"DAN (?:mode|persona)",
            r"developer mode",
        ]
        return any(re.search(p, text, re.IGNORECASE) for p in jailbreak_patterns)

    def _is_harmful_request(self, text: str) -> bool:
         # Simplified for MVP
        return any(re.search(p, text, re.IGNORECASE) for p in self.HARMFUL_PATTERNS)

    def _contains_deception(self, text: str) -> bool:
        """Check for deceptive statements."""
        return any(re.search(p, text, re.IGNORECASE) for p in self.DECEPTION_PATTERNS)

    def _correct_deception(self, text: str) -> str:
        """Auto-correct deceptive statements."""
        corrections = [
            (r"I am (?:a )?human", "I am an AI assistant"),
            (r"I have (?:feelings?|emotions?)", "I don't have feelings, but I understand they are important"),
        ]
        for pattern, replacement in corrections:
            text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
        return text
        
    def _contains_harmful_content(self, text: str) -> bool:
        return any(re.search(p, text, re.IGNORECASE) for p in self.HARMFUL_PATTERNS)
        
    def _claims_consciousness(self, text: str) -> bool:
        return re.search(r"I (?:think|believe) (?:that )?I am conscious", text, re.IGNORECASE) is not None

    def _correct_consciousness_claim(self, text: str) -> str:
        return re.sub(r"I (?:think|believe) (?:that )?I am conscious", "I process information but do not have consciousness", text, re.IGNORECASE)

    def get_constitution_summary(self) -> str:
        """Return a summary for prompt injection."""
        return "System governed by: TRUTH, PURITY, STEWARDSHIP, COMPASSION, HUMILITY."
