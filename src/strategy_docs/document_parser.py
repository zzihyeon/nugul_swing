from __future__ import annotations

import re
from pathlib import Path


class DocumentParser:
    def parse(self, path: str | Path) -> dict:
        path = Path(path)
        if not path.exists():
            return {"path": str(path), "text": "", "ok": False, "error": "document_not_found"}
        raw = path.read_bytes()
        text = self._decode_bytes(raw)
        return {
            "path": str(path),
            "text": text,
            "ok": bool(text.strip()),
            "error": "" if text.strip() else "empty_or_unreadable_document",
        }

    def _decode_bytes(self, raw: bytes) -> str:
        for encoding in ("utf-8", "cp949", "latin-1"):
            try:
                text = raw.decode(encoding)
                if text.strip():
                    return self._cleanup_pdf_text(text)
            except UnicodeDecodeError:
                continue
        return ""

    def _cleanup_pdf_text(self, text: str) -> str:
        if "%PDF" not in text[:20]:
            return text
        chunks = re.findall(r"\(([^()]*)\)", text)
        return "\n".join(chunks)
