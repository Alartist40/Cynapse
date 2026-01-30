## 2026-01-30 - [Information Disclosure in Audit Logs]
**Vulnerability:** Command-line arguments containing sensitive data (seeds, keys) were logged in plain text in both the start event and in the exception message on failure.
**Learning:** Even if the command execution itself is safe (using list-based subprocess calls), the logging infrastructure can inadvertently leak secrets if it records raw input or raw exceptions.
**Prevention:** Implement argument redaction based on length and keywords before logging. Catch and sanitize exceptions that are likely to contain the full command line (e.g., subprocess.TimeoutExpired).
