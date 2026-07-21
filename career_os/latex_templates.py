"""LaTeX resume templates for Career OS."""

from __future__ import annotations

TEMPLATE = r"""\documentclass[10pt]{article}

\usepackage{geometry}
\geometry{margin=0.75in}
\usepackage{parskip}
\usepackage{hyperref}
\usepackage{enumitem}
\usepackage{fontenc}
\usepackage{inputenc}

\setlength{\parindent}{0pt}
\setlist{nosep, left=0pt, labelindent=0pt, listparindent=0pt}
\pagestyle{empty}

\begin{document}

\begin{center}
    {\LARGE\textbf{NAME_PLACEHOLDER}}\\[4pt]
    CONTACT_PLACEHOLDER
\end{center}

\hrule
\vspace{6pt}

SUMMARY_SECTION

SKILLS_SECTION

EXPERIENCE_SECTION

PROJECTS_SECTION

EDUCATION_SECTION

\end{document}
"""


def render_resume(
    *,
    name: str,
    contact_lines: list[str],
    summary: str,
    skills: list[str],
    experiences: list[dict],
    projects: list[dict],
    education: list[dict],
) -> str:
    contact = " $|$ ".join(contact_lines)
    summary_block = _section("Summary", summary)
    skills_block = _section("Skills", ", ".join(skills))
    exp_blocks = []
    for exp in experiences:
        title = exp.get("title", "")
        company = exp.get("company", "")
        bullets = exp.get("bullets", [])
        heading = f"\\textbf{{{_esc(title)}}}" if not company else f"\\textbf{{{_esc(title)}}} --- {_esc(company)}"
        items = "".join(f"\\item {_esc(b)}" for b in bullets)
        exp_blocks.append(f"{heading}\n\\begin{{itemize}}\n{items}\\end{{itemize}}")
    experience_block = _section("Experience", "\n".join(exp_blocks))
    proj_blocks = []
    for proj in projects:
        name_p = proj.get("name", "")
        bullets = proj.get("bullets", [])
        items = "".join(f"\\item {_esc(b)}" for b in bullets)
        proj_blocks.append(f"\\textbf{{{_esc(name_p)}}}\n\\begin{{itemize}}\n{items}\\end{{itemize}}")
    projects_block = _section("Projects", "\n".join(proj_blocks))
    edu_blocks = []
    for edu in education:
        parts = [str(edu.get(k, "")) for k in ["degree", "institution", "year"] if edu.get(k)]
        edu_blocks.append(" $|$ ".join(parts))
    education_block = _section("Education", "\n".join(edu_blocks))
    return (
        TEMPLATE.replace("NAME_PLACEHOLDER", _esc(name))
        .replace("CONTACT_PLACEHOLDER", contact)
        .replace("SUMMARY_SECTION", summary_block)
        .replace("SKILLS_SECTION", skills_block)
        .replace("EXPERIENCE_SECTION", experience_block)
        .replace("PROJECTS_SECTION", projects_block)
        .replace("EDUCATION_SECTION", education_block)
    )


def render_cover_letter(
    *,
    name: str,
    contact_lines: list[str],
    date: str,
    company: str,
    job_title: str,
    body: str,
) -> str:
    contact = " $|$ ".join(contact_lines)
    return f"""\\documentclass[11pt]{{letter}}
\\usepackage[letterpaper,margin=1in]{{geometry}}
\\usepackage{{parskip}}
\\pagestyle{{empty}}
\\begin{{document}}
\\begin{{flushright}}
{{{_esc(name)}}}\\\\
{contact}
\\end{{flushright}}
\\vspace{{12pt}}
{_esc(date)}
\\vspace{{12pt}}
Hiring Manager
\\vspace{{6pt}}
Re: {_esc(job_title)} position at {_esc(company)}
\\vspace{{12pt}}
{body}
\\vspace{{12pt}}
Sincerely,\\\\
{_esc(name)}
\\end{{document}}"""


def _section(title: str, content: str) -> str:
    if not content.strip():
        return ""
    return f"\\textbf{{\\large {_esc(title)}}}\\\\\n{content}\n\n"


def _esc(text: str | None) -> str:
    if text is None:
        return ""
    chars = {"\\": "\\textbackslash ", "&": "\\&", "%": "\\%", "$": "\\$", "#": "\\#", "_": "\\_", "{": "\\{", "}": "\\}", "~": "\\textasciitilde ", "^": "\\textasciicircum "}
    for char, replace in chars.items():
        text = text.replace(char, replace)
    return text
