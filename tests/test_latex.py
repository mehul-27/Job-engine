from __future__ import annotations

import unittest

from career_os.latex_templates import render_cover_letter, render_resume, _esc


class RenderResumeTests(unittest.TestCase):
    def test_renders_minimal_resume(self) -> None:
        tex = render_resume(
            name="Test User",
            contact_lines=["test@test.com"],
            summary="A summary.",
            skills=["Python"],
            experiences=[],
            projects=[],
            education=[{"degree": "BS CS", "institution": "MIT"}],
        )
        self.assertIn("Test User", tex)
        self.assertIn("test@test.com", tex)
        self.assertIn("A summary.", tex)
        self.assertIn("Python", tex)
        self.assertIn("BS CS", tex)
        self.assertIn("MIT", tex)
        self.assertIn(r"\documentclass", tex)

    def test_renders_experience(self) -> None:
        tex = render_resume(
            name="N",
            contact_lines=[],
            summary="",
            skills=[],
            experiences=[{"title": "Engineer", "company": "Co", "bullets": ["Built thing"]}],
            projects=[],
            education=[],
        )
        self.assertIn("Engineer", tex)
        self.assertIn("--- Co", tex)
        self.assertIn("Built thing", tex)

    def test_escapes_special_chars(self) -> None:
        self.assertEqual(r"\textbackslash ", _esc("\\"))
        self.assertEqual(r"\&", _esc("&"))
        self.assertEqual(r"\%", _esc("%"))
        self.assertEqual(r"\_", _esc("_"))

    def test_empty_contact(self) -> None:
        tex = render_resume(name="N", contact_lines=[], summary="", skills=[], experiences=[], projects=[], education=[])
        self.assertIn("N", tex)


class CoverLetterRenderTests(unittest.TestCase):
    def test_renders_cover_letter(self) -> None:
        tex = render_cover_letter(
            name="Alice",
            contact_lines=["alice@test.com", "555-0100"],
            date="June 1, 2026",
            company="Acme Corp",
            job_title="Software Engineer",
            body="I am writing to apply...",
        )
        self.assertIn("Alice", tex)
        self.assertIn("alice@test.com", tex)
        self.assertIn("Acme Corp", tex)
        self.assertIn("Software Engineer", tex)
        self.assertIn("I am writing to apply", tex)
        self.assertIn(r"\documentclass", tex)

    def test_handles_empty_contact(self) -> None:
        tex = render_cover_letter(name="B", contact_lines=[], date="D", company="C", job_title="J", body="B")
        self.assertIn("B", tex)


if __name__ == "__main__":
    unittest.main()
