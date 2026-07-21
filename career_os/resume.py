"""Resume tailoring for Career OS V1."""

from __future__ import annotations

import json
import subprocess
from datetime import datetime
from pathlib import Path

from .ai import AIProvider, extract_json
from .latex_templates import render_cover_letter, render_resume
from .pdf_utils import extract_text
from .prompts import cover_letter, resume_tailor


def compile_latex(tex_content: str, output_dir: str | Path, stem: str = "resume") -> Path | None:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    tex_path = output_dir / f"{stem}.tex"
    tex_path.write_text(tex_content, encoding="utf-8")
    try:
        result = subprocess.run(
            ["pdflatex", "-interaction=nonstopmode", "-output-directory", str(output_dir), str(tex_path)],
            capture_output=True,
            text=True,
            timeout=30,
        )
        pdf_path = output_dir / f"{stem}.pdf"
        if pdf_path.exists():
            return pdf_path
        return None
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None


def generate_tailored_resume(
    *,
    job_title: str,
    job_description: str,
    master_resume_path: str | Path,
    knowledge_items: list[dict],
    ai_provider: AIProvider,
) -> dict:
    resume_text = extract_text(master_resume_path)
    kb_text = "\n\n".join(
        f"[{item.get('kind', '')}] {item.get('title', '')}:\n{item.get('body', '')}"
        for item in knowledge_items
    )
    system, user = resume_tailor(
        job_title=job_title,
        job_description=job_description,
        master_resume_text=resume_text,
        knowledge_items=kb_text,
    )
    result = ai_provider.chat(system=system, user=user, json_mode=True)
    data = extract_json(result.content)
    data["_ai_model"] = result.model
    data["_ai_latency_ms"] = result.latency_ms
    data["_provenance"] = data.get("provenance_notes", json.dumps({"master_resume": str(master_resume_path)}))
    return data


def tailored_to_latex(resume_data: dict, *, name: str = "User", contact: list[str] | None = None) -> str:
    return render_resume(
        name=name,
        contact_lines=contact or ["email@example.com", "github.com/user"],
        summary=resume_data.get("summary", ""),
        skills=resume_data.get("skills", []),
        experiences=resume_data.get("experience", []),
        projects=resume_data.get("projects", []),
        education=resume_data.get("education", []),
    )


def generate_cover_letter(
    *,
    job_title: str,
    company: str,
    job_description: str,
    tailored_resume_text: str,
    user_profile_text: str,
    ai_provider: AIProvider,
) -> str:
    system, user = cover_letter(
        job_title=job_title,
        company=company,
        job_description=job_description,
        tailored_resume_text=tailored_resume_text,
        user_profile=user_profile_text,
    )
    result = ai_provider.chat(system=system, user=user, json_mode=False, temperature=0.5)
    return result.content


def cover_letter_to_latex(
    body: str,
    *,
    name: str = "User",
    contact_lines: list[str] | None = None,
    company: str = "",
    job_title: str = "",
) -> str:
    return render_cover_letter(
        name=name,
        contact_lines=contact_lines or ["email@example.com"],
        date=datetime.now().strftime("%B %d, %Y"),
        company=company,
        job_title=job_title,
        body=body,
    )
