# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Added
- **TLS Support**: Auto-generates self-signed certificates (`cert.pem`, `key.pem`) for secure HTTPS communication.
- **API Key Authentication**: Enforces `X-Api-Key` header verification against `keys.txt`.
- **Reverse Proxy**: Transparently proxies requests to `localhost:11434`.
- **Logging**: NDJSON structured logging to `gateway.log` capturing request details and token counts.
- **Single Binary Architecture**: Zero-dependency static logic for easy deployment.
