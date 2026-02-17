#!/usr/bin/env python3
"""
Owl Bridge Server — stdin/stdout JSON protocol.

Handles OCR and PII detection operations.
"""
import sys
import json


def handle_request(req: dict) -> dict:
    operation = req.get("operation", "")
    params = req.get("params", {})

    if operation == "ocr":
        image_path = params.get("image_path", "")
        return {
            "success": True,
            "output": f"(Owl Mock) OCR text extracted from: {image_path}",
            "confidence": 0.92,
        }

    elif operation == "detect_pii":
        text = req.get("payload", "")
        # Simple PII detection mock
        pii_found = []
        import re
        if re.search(r'\b\d{3}[-.]?\d{2}[-.]?\d{4}\b', text):
            pii_found.append("SSN pattern detected")
        if re.search(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', text):
            pii_found.append("Email address detected")

        return {
            "success": True,
            "output": f"PII scan: {len(pii_found)} findings" if pii_found else "No PII detected",
            "details": {"findings": pii_found},
        }

    elif operation == "health":
        return {"success": True, "output": "Owl OCR: ready (mock mode)"}

    else:
        return {"success": False, "error": f"Unknown operation: {operation}"}


def main():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
            resp = handle_request(req)
        except Exception as e:
            resp = {"success": False, "error": str(e)}

        sys.stdout.write(json.dumps(resp) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
