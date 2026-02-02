# Changelog

All notable changes to this project will be documented in this file.

## [1.0.1] - 2026-02-02

### 🔒 Security Fixed

- **HIGH: API Key Information Disclosure (CVSS 6.5)**
  - API keys are now masked in logs (only first 4 characters visible)
  - Added SHA256 hash prefix for correlation without full key exposure
  - Changed log file permissions to 0600 (owner-only read/write)
  - Added `maskAPIKey()` and `hashAPIKey()` functions to `log.go`

### Changed
- Log field changed from `"key"` to `"key_prefix"` and `"key_hash"`
- Improved security of `gateway.log` file permissions

---

## [1.0.0] - 2026-01-15

### Added
- **TLS Support**: Auto-generates self-signed certificates (`cert.pem`, `key.pem`) for secure HTTPS communication.
- **API Key Authentication**: Enforces `X-Api-Key` header verification against `keys.txt`.
- **Reverse Proxy**: Transparently proxies requests to `localhost:11434`.
- **Logging**: NDJSON structured logging to `gateway.log` capturing request details and token counts.
- **Single Binary Architecture**: Zero-dependency static logic for easy deployment.

