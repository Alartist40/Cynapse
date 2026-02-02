#!/usr/bin/env python3
"""
Owl OCR v2.0 - Optimized PII Redactor
Async Tesseract wrapper, PIL redaction, Hub-ready output
"""

import asyncio
import json
import re
import shutil
import subprocess
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import List, Optional, Tuple, Dict, Any
from PIL import Image, ImageDraw

# Optional PDF support - gracefully degrade if missing
try:
    import pypdf
    HAS_PYPDF = True
except ImportError:
    HAS_PYPDF = False


@dataclass
class PIIHit:
    """Structured PII detection result"""
    type: str
    value_masked: str
    bbox: Tuple[int, int, int, int]  # left, top, right, bottom
    page: int = 1
    confidence: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.type,
            "value": self.value_masked,
            "bbox": list(self.bbox),
            "page": self.page,
            "conf": round(self.confidence, 2)
        }


@dataclass
class RedactionResult:
    """Return object for Cynapse Hub integration"""
    original: Path
    redacted: Optional[Path]  # None if no PII found
    report: Path
    hits: List[PIIHit]
    pages_processed: int
    scrubbed_text: str  # Text content with PII replaced by [REDACTED]


class OwlRedactor:
    """
    Async PII redaction neuron.
    Non-blocking Tesseract calls for TUI responsiveness.
    """
    
    def __init__(self, tesseract_cmd: Optional[str] = None):
        self.tess_cmd = tesseract_cmd or shutil.which("tesseract") or "tesseract"
        
        # Compiled regex for performance
        self.patterns = {
            "EMAIL": re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"),
            "PHONE": re.compile(r"\b(?:\+\d{1,2}\s?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}\b"),
            "SSN": re.compile(r"\b\d{3}[-.]?\d{2}[-.]?\d{4}\b"),
            "CARD": re.compile(r"\b(?:\d[ -]*?){13,16}\b"),
            "API_KEY": re.compile(r"\b(sk-[a-zA-Z0-9]{32,})\b"),  # OpenAI-style keys
        }

    def _mask(self, text: str) -> str:
        """Show first 2 and last 2 chars only"""
        if len(text) <= 4:
            return "*" * len(text)
        return f"{text[:2]}...{text[-2:]}"

    async def _ocr_image(self, img_path: Path) -> List[Dict]:
        """
        Run Tesseract OCR asynchronously (non-blocking).
        Returns list of dicts with text, bbox, confidence.
        """
        # TSV format: level page_num block_num par_num line_num word_num left top width height conf text
        cmd = [
            self.tess_cmd, str(img_path), "stdout",
            "-l", "eng",
            "--psm", "6",
            "tsv"
        ]
        
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await proc.communicate()
            
            if proc.returncode != 0:
                print(f"Tesseract warning: {stderr.decode()}")
                return []
        except Exception as e:
            print(f"OCR execution failed: {e}")
            return []
        
        boxes = []
        output = stdout.decode("utf-8", errors="ignore").strip()
        if not output:
            return []
            
        lines = output.split("\n")[1:]  # Skip header

        for line in lines:
            parts = line.split("\t")
            if len(parts) < 12:
                continue
            
            try:
                conf = int(parts[10])
                if conf < 30:  # Filter garbage
                    continue

                text = parts[11]
                if not text.strip():
                    continue

                left = int(parts[6])
                top = int(parts[7])
                width = int(parts[8])
                height = int(parts[9])

                boxes.append({
                    "text": text,
                    "bbox": (left, top, left + width, top + height),
                    "conf": conf
                })
            except (ValueError, IndexError):
                continue

        return boxes

    def _find_pii(self, ocr_results: List[Dict], page_num: int = 1) -> List[PIIHit]:
        """Scan OCR results for regex patterns"""
        hits = []
        
        for item in ocr_results:
            text = item["text"]
            bbox = item["bbox"]
            conf = item["conf"]

            for pii_type, pattern in self.patterns.items():
                if pattern.search(text):
                    hits.append(PIIHit(
                        type=pii_type,
                        value_masked=self._mask(text),
                        bbox=bbox,
                        page=page_num,
                        confidence=conf
                    ))
                    break
        
        return hits
    
    async def _redact_image(self, img_path: Path, hits: List[PIIHit], output_path: Path):
        """Draw black boxes over PII (run in thread to not block)"""
        def _draw():
            with Image.open(img_path) as im:
                draw = ImageDraw.Draw(im)
                for hit in hits:
                    draw.rectangle(hit.bbox, fill="black")
                im.save(output_path)

        await asyncio.to_thread(_draw)
    
    async def redact(
        self,
        input_path: Path,
        output_dir: Optional[Path] = None,
        progress_callback: Optional[Any] = None
    ) -> RedactionResult:
        """
        Main entry point. Async, TUI-friendly.
        """
        input_path = Path(input_path)
        output_dir = Path(output_dir) if output_dir else input_path.parent
        
        if not input_path.exists():
            raise FileNotFoundError(f"Input not found: {input_path}")
        
        suffix = input_path.suffix.lower()
        all_hits: List[PIIHit] = []
        pages_processed = 0
        scrubbed_chunks = []
        redacted_path = None

        # --- IMAGE PROCESSING ---
        if suffix in (".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".gif"):
            if progress_callback:
                await progress_callback(f"OCR processing {input_path.name}...")

            ocr_data = await self._ocr_image(input_path)
            hits = self._find_pii(ocr_data)
            all_hits.extend(hits)
            pages_processed = 1
            
            # Build scrubbed text representation
            for item in ocr_data:
                txt = item["text"]
                is_redacted = False
                for hit in hits:
                    if hit.bbox == item["bbox"]:
                        is_redacted = True
                        break
                scrubbed_chunks.append("[REDACTED]" if is_redacted else txt)

            if hits:
                if progress_callback:
                    await progress_callback(f"Found {len(hits)} PII instances, redacting...")

                redacted_path = output_dir / f"{input_path.stem}_redacted{suffix}"
                await self._redact_image(input_path, hits, redacted_path)

        # --- PDF PROCESSING (Best effort) ---
        elif suffix == ".pdf" and HAS_PYPDF:
            if progress_callback:
                await progress_callback("Extracting PDF structure...")

            reader = pypdf.PdfReader(input_path)
            pages_processed = len(reader.pages)
            
            for i, page in enumerate(reader.pages):
                text = page.extract_text() or ""
                scrubbed_page = text

                for pii_type, pattern in self.patterns.items():
                    matches = pattern.findall(text)
                    for match in matches:
                        all_hits.append(PIIHit(
                            type=pii_type,
                            value_masked=self._mask(match),
                            bbox=(0, 0, 0, 0),
                            page=i+1
                        ))
                        scrubbed_page = scrubbed_page.replace(match, "[REDACTED]")

                scrubbed_chunks.append(scrubbed_page)

        else:
            if suffix == ".pdf" and not HAS_PYPDF:
                raise ImportError("PDF processing requires 'pypdf'. Install with pip.")
            raise ValueError(f"Unsupported format: {suffix}. Use image or PDF.")
        
        # --- REPORT GENERATION ---
        report_path = output_dir / f"{input_path.stem}_report.json"
        report_data = {
            "source": str(input_path),
            "redacted": str(redacted_path) if redacted_path else None,
            "pages": pages_processed,
            "pii_found": len(all_hits),
            "detections": [h.to_dict() for h in all_hits],
            "scrubbed_text_preview": " ".join(scrubbed_chunks)[:500] + "..."
        }

        def _write_report():
            with open(report_path, "w") as f:
                json.dump(report_data, f, indent=2)

        await asyncio.to_thread(_write_report)

        return RedactionResult(
            original=input_path,
            redacted=redacted_path,
            report=report_path,
            hits=all_hits,
            pages_processed=pages_processed,
            scrubbed_text=" ".join(scrubbed_chunks)
        )


async def main():
    import sys
    if len(sys.argv) < 2:
        print("Usage: owl_ocr.py <image.pdf/png>")
        sys.exit(1)

    owl = OwlRedactor()
    path = Path(sys.argv[1])

    async def progress(msg):
        print(f"[Owl] {msg}")

    try:
        result = await owl.redact(path, progress_callback=progress)
        print(f"\n✓ Complete: {len(result.hits)} PII items detected")
        print(f"  Report: {result.report}")
        if result.redacted:
            print(f"  Redacted: {result.redacted}")
    except Exception as e:
        print(f"✗ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
