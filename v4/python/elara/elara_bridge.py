#!/usr/bin/env python3
"""
Elara Bridge Server — stdin/stdout JSON protocol.

Launched by Go bridge with: python3 elara_bridge.py --bridge
Reads JSON requests from stdin, writes JSON responses to stdout.
"""
import sys
import json
import asyncio
from inference import ElaraInference

# Global inference engine
engine = ElaraInference()


async def handle_request(req: dict) -> dict:
    """Process a bridge request and return a response."""
    if req is None:
        return {"success": False, "error": "Empty request"}

    operation = req.get("operation", "")
    params = req.get("params") or {}
    payload = req.get("payload", "")

    if operation == "generate":
        if not engine.is_ready():
            success = await engine.load_model()
            if not success:
                return {"success": False, "error": "Failed to load Elara model"}

        prompt = payload or params.get("prompt", "")
        max_tokens = int(params.get("max_tokens", 256))
        temperature = float(params.get("temperature", 0.7))

        output = await engine.generate(
            prompt=prompt,
            max_tokens=max_tokens,
            temperature=temperature
        )

        return {
            "success": True,
            "output": output,
            "confidence": 0.85,
        }

    elif operation == "health":
        ready = engine.is_ready()
        return {
            "success": True,
            "output": f"Elara model: {'ready' if ready else 'not loaded'}",
            "details": engine.loader.get_info() if ready else None
        }

    else:
        return {
            "success": False,
            "error": f"Unknown operation: {operation}",
        }


async def main():
    """Bridge loop: read JSON line from stdin, write JSON line to stdout."""
    # Pre-load model if needed or wait for first request

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
        except json.JSONDecodeError as e:
            resp = {"success": False, "error": f"JSON parse error: {e}"}
        except Exception as e:
            resp = {"success": False, "error": str(e)}

        sys.stdout.write(json.dumps(resp) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    asyncio.run(main())
