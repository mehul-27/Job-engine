from __future__ import annotations

import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory, NamedTemporaryFile
import unittest
from unittest.mock import MagicMock, patch

from career_os.ai import AIResult
from career_os.resume import (
    compile_latex,
    cover_letter_to_latex,
    generate_cover_letter,
    generate_tailored_resume,
    tailored_to_latex,
)


class GenerateTailoredResumeTests(unittest.TestCase):
    @patch("career_os.resume.extract_text", return_value="Mocked resume text: Built scalable systems")
    def test_generate_returns_parsed_data(self, mock_extract: MagicMock) -> None:
        mock_ai = MagicMock()
        mock_ai.chat.return_value = AIResult(
            content=json.dumps({
                "summary": "Experienced dev",
                "skills": ["Python"],
                "experience": [{"title": "SWE", "company": "Co", "bullets": ["Built stuff"]}],
                "projects": [],
                "education": [],
                "provenance_notes": "Used KB item ki_abc",
            }),
            model="llama3-70b-8192",
            latency_ms=500,
            input_tokens=100,
            output_tokens=50,
        )

        with TemporaryDirectory() as tmp:
            resume_path = Path(tmp) / "resume.pdf"
            resume_path.write_bytes(b"%PDF placeholder")

            result = generate_tailored_resume(
                job_title="Engineer",
                job_description="Python dev",
                master_resume_path=resume_path,
                knowledge_items=[{"kind": "project", "title": "Career OS", "body": "Built a tool"}],
                ai_provider=mock_ai,
            )

        self.assertEqual("Experienced dev", result["summary"])
        self.assertIn("Python", result["skills"])
        self.assertEqual("llama3-70b-8192", result["_ai_model"])
        self.assertEqual(500, result["_ai_latency_ms"])

    @patch("career_os.resume.extract_text", return_value="Mocked resume: Go expert")
    def test_generate_calls_ai_with_correct_prompts(self, mock_extract: MagicMock) -> None:
        mock_ai = MagicMock()
        mock_ai.chat.return_value = AIResult(
            content=json.dumps({"summary": "Dev", "skills": [], "experience": [], "projects": [], "education": []}),
            model="m",
            latency_ms=0,
        )

        with TemporaryDirectory() as tmp:
            resume_path = Path(tmp) / "r.pdf"
            resume_path.write_bytes(b"%PDF")

            generate_tailored_resume(
                job_title="Job",
                job_description="Desc",
                master_resume_path=resume_path,
                knowledge_items=[{"kind": "skill", "title": "Go", "body": "Used Go"}],
                ai_provider=mock_ai,
            )

        _, call_kwargs = mock_ai.chat.call_args
        self.assertIn("Job", call_kwargs["user"])
        self.assertIn("Desc", call_kwargs["user"])
        self.assertIn("Go", call_kwargs["user"])
        self.assertTrue(call_kwargs["json_mode"])


class TailoredToLatexTests(unittest.TestCase):
    def test_converts_to_latex(self) -> None:
        data = {
            "summary": "Dev",
            "skills": ["Python", "Go"],
            "experience": [{"title": "SWE", "company": "Co", "bullets": ["Built"]}],
            "projects": [{"name": "Proj", "bullets": ["Created"]}],
            "education": [{"degree": "BS", "institution": "U"}],
        }
        tex = tailored_to_latex(data, name="Alice", contact=["alice@test.com"])
        self.assertIn("Alice", tex)
        self.assertIn("Python", tex)
        self.assertIn("SWE", tex)
        self.assertIn("Proj", tex)
        self.assertIn("BS", tex)


class CompileLatexTests(unittest.TestCase):
    def test_compile_fails_gracefully_without_pdflatex(self) -> None:
        with TemporaryDirectory() as tmp:
            result = compile_latex(r"\documentclass{article}\begin{document}Hi\end{document}", tmp, stem="test")
            self.assertIsNone(result)


@patch("career_os.resume.datetime")
class CoverLetterGenerateTests(unittest.TestCase):
    def test_generate_calls_ai(self, mock_dt: MagicMock) -> None:
        mock_ai = MagicMock()
        mock_ai.chat.return_value = AIResult(
            content="Dear Hiring Manager, ... Sincerely, User",
            model="m",
            latency_ms=0,
        )
        body = generate_cover_letter(
            job_title="Engineer",
            company="Co",
            job_description="Build things",
            tailored_resume_text="Built things",
            user_profile_text="Name: John",
            ai_provider=mock_ai,
        )
        self.assertIn("Dear Hiring Manager", body)
        _, call_kwargs = mock_ai.chat.call_args
        self.assertIn("Engineer", call_kwargs["user"])
        self.assertIn("Co", call_kwargs["user"])

    def test_cover_letter_to_latex(self, mock_dt: MagicMock) -> None:
        mock_dt.now.return_value.strftime.return_value = "June 1, 2026"
        tex = cover_letter_to_latex("I am great for this role.", company="Acme", job_title="SWE")
        self.assertIn("Acme", tex)
        self.assertIn("SWE", tex)
        self.assertIn("June 1, 2026", tex)
        self.assertIn("I am great for this role.", tex)
        self.assertIn(r"\documentclass", tex)


if __name__ == "__main__":
    unittest.main()
