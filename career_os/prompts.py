"""Versioned prompt templates for Career OS.

Centralized prompt mgmt per Q11. Each prompt is a fn returning (system, user).
"""

from __future__ import annotations


PROMPT_VERSION = "1.0.0"


def resume_tailor(
    job_title: str,
    job_description: str,
    master_resume_text: str,
    knowledge_items: str,
) -> tuple[str, str]:
    system = (
        "You are a professional resume writer. Your job is to tailor a resume "
        "for a specific job opportunity. Rules:\n"
        "1. NEVER invent experience, skills, projects, or achievements.\n"
        "2. Only use information from the master resume and knowledge base.\n"
        "3. Prioritize relevant experience over less relevant experience.\n"
        "4. Rephrase bullets to highlight relevant keywords from the job description.\n"
        "5. Keep formatting ATS-friendly (no columns, no graphics, standard headings).\n"
        "6. Output JSON with keys: summary, skills (list), experience (list of {title, company, bullets}), "
        "projects (list of {name, bullets}), education (list).\n"
        "7. Include a provenance_notes field explaining which KB items were used."
    )
    user = (
        f"Job Title: {job_title}\n\n"
        f"Job Description:\n{job_description}\n\n"
        f"Master Resume:\n{master_resume_text}\n\n"
        f"Knowledge Base:\n{knowledge_items}\n\n"
        f"Produce tailored resume JSON for this opportunity."
    )
    return system, user


def opportunity_analysis(
    job_title: str,
    company: str,
    job_description: str,
    user_skills: str,
) -> tuple[str, str]:
    system = (
        "You are a job opportunity analyst. Analyze a listing and produce:\n"
        "1. required_skills: skills explicitly required\n"
        "2. preferred_skills: skills mentioned as preferred\n"
        "3. experience_required: years or level of experience\n"
        "4. technologies: technologies mentioned\n"
        "5. responsibilities: key responsibilities\n"
        "6. concerns: potential red flags (e.g., vague description, low pay mention)\n"
        "7. match_notes: which user skills match, which gaps exist\n"
        "8. relevance: brief explanation why this is or isn't worth applying\n"
        "Output JSON only."
    )
    user = (
        f"Job Title: {job_title}\n"
        f"Company: {company}\n"
        f"Description:\n{job_description}\n\n"
        f"User Skills:\n{user_skills}\n\n"
        f"Produce analysis JSON."
    )
    return system, user


def cover_letter(
    job_title: str,
    company: str,
    job_description: str,
    tailored_resume_text: str,
    user_profile: str,
) -> tuple[str, str]:
    system = (
        "Write a concise cover letter. Rules:\n"
        "1. Never invent qualifications.\n"
        "2. Reference specific job requirements and match them with user experience.\n"
        "3. Professional tone, 3-4 paragraphs.\n"
        "4. Output plain text only, no JSON."
    )
    user = (
        f"Job: {job_title} at {company}\n"
        f"Description:\n{job_description}\n\n"
        f"Resume:\n{tailored_resume_text}\n\n"
        f"Profile:\n{user_profile}\n\n"
        f"Write cover letter."
    )
    return system, user
