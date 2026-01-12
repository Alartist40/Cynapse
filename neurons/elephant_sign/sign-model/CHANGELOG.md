# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Added
-   **Core Signing Logic**: Implemented `ed25519-dalek` for cryptographic operations.
-   **Key Generation**: Added `--gen-key` command to generate random Ed25519 keypairs.
-   **Signing Command**: Added `sign` command to hash file content (BLAKE3), sign the hash, and append a custom footer.
-   **Verification Command**: Added `verify` command to validate the file integrity and signature authenticity.
-   **Footer Structure**: Defined a 256-byte footer containing:
    -   64-byte Signature
    -   32-byte Public Key
    -   4-byte Magic Number (`0x53494721`)
    -   Padding
-   **CLI**: Simple command-line interface for interaction.

### Technical Notes
-   Built with Rust for performance and safety.
-   Zero runtime dependencies (produces a static binary).
-   Designed to be non-intrusive for tools reading from the start of the file (like LLM loaders).
