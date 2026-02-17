#!/usr/bin/env python3
"""
Owl Bridge Server — stdin/stdout JSON protocol.

Handles OCR and PII detection operations.
"""
import sys
import json
import asyncio
from pathlib import Path
from owl import OwlRedactor

# Global redactor
redactor = OwlRedactor()


async def handle_request(req: dict) -> dict:
    if req is None:
        return {"success": False, "error": "Empty request"}

    operation = req.get("operation", "")
    params = req.get("params") or {}
    payload = req.get("payload", "")

    if operation == "ocr" or operation == "redact":
        input_path = params.get("input_path", payload)
        if not input_path:
            return {"success": False, "error": "Missing input_path or payload"}

        try:
            result = await redactor.redact(Path(input_path))
            return {
                "success": True,
                "output": result.scrubbed_text,
                "details": {
                    "redacted_path": str(result.redacted) if result.redacted else None,
                    "report_path": str(result.report),
                    "pii_count": len(result.hits)
                }
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    elif operation == "health":
        return {"success": True, "output": "Owl OCR: ready"}

    else:
        return {"success": False, "error": f"Unknown operation: {operation}"}


async def main():
    while True:
        line = await asyncio.get_event_loop().run_in_executor(None, sys.stdin.readline)
        if not line:
            break

        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
            resp = await handle_request(req)
        except Exception as e:
            resp = {"success": False, "error": str(e)}

        sys.stdout.write(json.dumps(resp) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    asyncio.run(main())
