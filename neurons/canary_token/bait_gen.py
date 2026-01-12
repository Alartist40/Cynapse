#!/usr/bin/env python3
import pathlib, json, os

CANARY = pathlib.Path('Canary')
CANARY.mkdir(exist_ok=True)

# 1. AWS creds
aws = {
  "AccessKeyId": "AKIAFAKEFAKEFAKEFAKE",
  "SecretAccessKey": "fakefakefakefakefakefakefakefakefakefake",
  "Region": "us-east-1"
}
(CANARY / "aws_credentials.json").write_text(json.dumps(aws, indent=2))

# 2. Fake ONNX (first 4 MB of garbage + real header)
with open(CANARY / "model_weights.onnx", "wb") as f:
    f.write(b"\x08\x05")  # ONNX magic
    f.write(os.urandom(4*1024*1024))

# 3. Chrome cookies format
cookies = [
  {"domain": ".fakebank.com", "expirationDate": 1912336000, "name": "session", "value": "f4k3"}
]
(CANARY / "Cookies.json").write_text(json.dumps(cookies))

print("[+] Baits created in", CANARY.resolve())
