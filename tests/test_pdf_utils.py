from __future__ import annotations

import builtins
from pathlib import Path
from tempfile import TemporaryDirectory, NamedTemporaryFile
import unittest
from unittest.mock import patch

from career_os.pdf_utils import extract_text


class PdfExtractTests(unittest.TestCase):
    def test_extract_text_raises_when_import_fails(self) -> None:
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "test.pdf"
            path.write_bytes(b"%PDF-1.4 fake content")
            original_import = builtins.__import__

            def mock_import(name, *args, **kwargs):
                if name == "pdfplumber":
                    raise ImportError("no pdfplumber")
                return original_import(name, *args, **kwargs)

            with patch("builtins.__import__", side_effect=mock_import):
                with self.assertRaises(RuntimeError) as ctx:
                    extract_text(path)
            self.assertIn("pdfplumber", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
