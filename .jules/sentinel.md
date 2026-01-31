## 2026-01-30 - [Information Disclosure in Audit Logs]
**Vulnerability:** Command-line arguments containing sensitive data (seeds, keys) were logged in plain text in both the start event and in the exception message on failure.
**Learning:** Even if the command execution itself is safe (using list-based subprocess calls), the logging infrastructure can inadvertently leak secrets if it records raw input or raw exceptions.
**Prevention:** Implement argument redaction based on length and keywords before logging. Catch and sanitize exceptions that are likely to contain the full command line (e.g., subprocess.TimeoutExpired).
## 2026-01-30 - [Sanitizing Console Error Output]
**Vulnerability:** raw exception objects (e) printed to the console contained the full command line, including sensitive arguments (seeds, keys) passed to neurons.
**Learning:** Sanitizing logs is not enough; any output stream (stdout/stderr) that surfaces errors to the user must also be redacted to prevent secret leakage in shared or recorded terminal sessions.
**Prevention:** Always print sanitized error messages instead of raw exception objects when dealing with sensitive inputs.
