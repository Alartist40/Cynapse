# Signed-Model Distribution (MVP)

> **"Cosign for LLMs" – A minimal, dependency-free CLI for cryptographically signing and verifying files.**

This tool allows you to cryptographically sign files (like LLM models, `.gguf`, `.onnx`, or any other file) using Ed25519 signatures. It appends a secure 256-byte footer to the file, enabling downstream users to verify that the file has not been tampered with and originates from a trusted source.

## Features

-   **Ed25519 Signing & Verification**: Uses high-speed, high-security Ed25519 elliptic curve cryptography.
-   **Footer-Based**: Appends a 256-byte footer containing the signature and public key. This format is designed to be compatible with model loaders (like `llama.cpp` or Ollama) which typically ignore trailing data.
-   **Tamper Proof**: Verifies the integrity of the entire file body. Any modification to the file content will result in a verification failure.
-   **Zero Dependencies (Runtime)**: The resulting binary is a standalone executable.
-   **Cross-Platform**: Built with Rust, runs on Windows, Linux, and macOS.

## Installation

### Prerequisites

-   **Rust Toolchain**: You need to have Rust installed to build this project. Visit [rustup.rs](https://rustup.rs/) to install.

### Build from Source

1.  Clone the repository:
    ```bash
    git clone https://github.com/Alartist40/Signed-Model-Distribution.git
    cd Signed-Model-Distribution/sign-model
    ```
2.  Build the release binary:
    ```bash
    cargo build --release
    ```
3.  The executable will be located at `target/release/sign-model` (or `sign-model.exe` on Windows).

## Usage

### 1. Generate Keypair

First, generate a secure keypair (private and public key).

```bash
./sign-model --gen-key
```

*   **Output**: Creates a `keypair.pem` file in the current directory.
*   **Security Warning**: Keep `keypair.pem` SECRET. It contains your private key used for signing.

### 2. Sign a File

To sign a file, use the `sign` command. This will calculate the hash of the file, sign it with your private key, and append the signature footer.

```bash
./sign-model sign <input_file> [--key keypair.pem]
```

*   **Example**: `./sign-model sign model.gguf`
*   **Output**: Creates `<input_file>.signed` (e.g., `model.gguf.signed`).
*   **Note**: The `.signed` file is exactly 256 bytes larger than the original.

### 3. Verify a File

To verify a file, you only need the sender's public key (or the keypair file, which contains the public key).

**Using the keypair file (if you are the signer):**
```bash
./sign-model verify <signed_file> --key keypair.pem
```

**Using a standalone public key (for distribution):**
(You can extract the public key part from the keypair manually or provide the `.pem` if it only contains the public key logic - *Self-note: Current MVP uses keypair file for simplicity, but verification only uses the public component.*)

*   **Example**: `./sign-model verify model.gguf.signed`
*   **Output**:
    *   **Success**: `[+] Signature valid – model untampered` (Exit code 0)
    *   **Failure**: `[-] Signature invalid – TAMPERED` or `[-] Magic mismatch` (Exit code 1)

## Technical Details

### Footer Format
The tool appends a fixed 256-byte footer to the end of the file:

```text
[ 64 bytes Signature ] [ 32 bytes Public Key ] [ 4 bytes Magic (0x53494721) ] [ 156 bytes Padding ]
```

### Verification Process
1.  Read the last 256 bytes (footer).
2.  Check the "Magic" bytes (`SIG!`) to confirm the file claims to be signed.
3.  Calculate the BLAKE3 hash of the file *excluding* the footer.
4.  Verify the signature against the calculated hash using the embedded public key and Ed25519 signature.
5.  (Optional but recommended in production) Verify that the embedded public key matches the expected signer's public key.

## Development

-   **Language**: Rust (2021 Edition)
-   **Dependencies**:
    -   `ed25519-dalek`: For elliptic curve signing/verification.
    -   `blake3`: For high-performance file hashing.
