# Zero-Trust LLM Gateway

> A single-binary reverse-proxy that adds TLS + API-key auth in front of any Ollama instance.

## 🚀 Impact
"150-line Go binary adds TLS + auth to any Ollama endpoint"

## 🛠 Setup

### Prerequisites
- Go 1.23+
- An Ollama instance running on `localhost:11434`

### Installation
1. Clone the repository:
   ```bash
   git clone https://github.com/Alartist40/Zero-Trust-LLM-Gateway.git
   cd Zero-Trust-LLM-Gateway
   ```

2. Build the binary:
   ```bash
   go build -o gateway
   ```

3. Run the gateway:
   ```bash
   # Add a demo key
   echo "demo-key" > keys.txt
   
   # Start the gateway
   ./gateway
   ```

   Expected output:
   ```
   Gateway listening on :8443
   ```

## 📖 Usage

### Parameters
- **Listen**: `0.0.0.0:8443`
- **Upstream**: `localhost:11434`
- **Auth header**: `X-Api-Key: <key>`
- **Keys source**: `keys.txt` (plain text, one per line)

### API Surface
 Identical to Ollama, but requires `X-Api-Key` header and https.

### Examples

#### 1. Success (with key)
```bash
curl -k https://localhost:8443/api/chat \
  -H "X-Api-Key: demo-key" \
  -d '{"model":"llama3.2","messages":[{"role":"user","content":"hi"}]}'
```

#### 2. Forbidden (without key or invalid key)
```bash
curl -k https://localhost:8443/api/chat \
  -d '{"model":"llama3.2","messages":[{"role":"user","content":"hi"}]}'
# Returns 403 Forbidden
```

### Files Created
- `cert.pem` / `key.pem`: Auto-generated self-signed certificates on first run.
- `gateway.log`: NDJSON log of all requests.

## 🤝 Contributing
1. Fork the repo
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request
