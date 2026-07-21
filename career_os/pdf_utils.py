"""PDF text extraction for Career OS."""

from __future__ import annotations

from pathlib import Path


def extract_text(pdf_path: str | Path) -> str:
    try:
        import pdfplumber
    except ImportError:
        raise RuntimeError("pdfplumber required: pip install pdfplumber")
    pages: list[str] = []
    with pdfplumber.open(str(pdf_path)) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                pages.append(text)
    return "\n\n".join(pages)
