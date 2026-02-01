## 2026-01-30 - [Information Disclosure in Audit Logs]
**Vulnerability:** Command-line arguments containing sensitive data (seeds, keys) were logged in plain text in both the start event and in the exception message on failure.
**Learning:** Even if the command execution itself is safe (using list-based subprocess calls), the logging infrastructure can inadvertently leak secrets if it records raw input or raw exceptions.
**Prevention:** Implement argument redaction based on length and keywords before logging. Catch and sanitize exceptions that are likely to contain the full command line (e.g., subprocess.TimeoutExpired).
## 2026-01-30 - [Sanitizing Console Error Output]
**Vulnerability:** raw exception objects (e) printed to the console contained the full command line, including sensitive arguments (seeds, keys) passed to neurons.
**Learning:** Sanitizing logs is not enough; any output stream (stdout/stderr) that surfaces errors to the user must also be redacted to prevent secret leakage in shared or recorded terminal sessions.
**Prevention:** Always print sanitized error messages instead of raw exception objects when dealing with sensitive inputs.

## 2026-02-05 - [Command Injection in Neuron Scripts]
**Vulnerability:** Use of `os.system()` with formatted strings in neuron scripts allowed for potential command injection if parameters (like `event` or `filename`) were ever influenced by user input.
**Learning:** Even internal tool scripts must use secure execution patterns like `subprocess.run()` with argument lists to maintain a defense-in-depth posture.
**Prevention:** Replace `os.system()` with `subprocess.run(list_of_args)` across all neurons.

## 2026-02-12 - [Arbitrary Code Execution via Config File Injection]
**Vulnerability:** A "Poor Man's Configurator" pattern used `exec(open(config_file).read())` on a file path provided via command-line arguments, without validating that the path was safe or within expected boundaries. It also printed the file's content, leading to arbitrary file read.
**Learning:** Utilities that dynamically load and execute code from files are extremely high-risk. If they are necessary for flexibility, they MUST be strictly scoped to a trusted directory and use robust path validation.
**Prevention:** Use `pathlib.Path.resolve()` and `Path.relative_to()` to ensure any file being executed is within a restricted subdirectory (e.g., `config/`). Avoid printing file contents that are about to be executed.
