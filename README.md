# Career OS

> An AI-assisted desktop application that helps discover relevant opportunities, tailor application materials, automate repetitive parts of job applications, and keep the user in complete control throughout the process.

---

## Overview

Career OS is a personal application workflow assistant designed to reduce the time spent searching, evaluating, and applying for internships and jobs.

Unlike traditional job bots, Career OS is built around a simple principle:

> Automate repetitive work. Never automate important decisions.

The application assists with finding opportunities, tailoring resumes, generating application content when required, and completing application forms while always allowing the user to review, edit, or override every significant action.

This project is intended for personal use first. Every design decision prioritizes reliability, transparency, modularity, and long-term maintainability over maximizing automation.

---

## Core Goals

* Discover opportunities from multiple job sources.
* Filter irrelevant jobs before the user sees them.
* Build tailored resumes from a master resume and personal knowledge base.
* Generate cover letters only when required.
* Generate answers for application questions when requested.
* Automatically complete repetitive application fields.
* Pause whenever confidence is low or user input is required.
* Learn from previous interactions without inventing information.

---

## Current Status: v0.5 (Milestones 5-7)

| Area | Status |
|------|--------|
| Resume registration | ✅ Done |
| Knowledge base (CLI) | ✅ Done |
| Role target management | ✅ Done |
| Job discovery (JSON feeds) | ✅ Done |
| **AI provider abstraction (Groq)** | ✅ **New** |
| **Resume tailoring (LaTeX)** | ✅ **New** |
| **Company tracking + blacklist** | ✅ **New** |
| **Opportunity review + status** | ✅ **New** |
| **HTMX + Jinja2 web UI** | ✅ **New** |
| Application workspace | 🔜 Planned |
| Cover letter generation | 🔜 Planned |
| Browser assistance | 🔜 Planned |
| Learning system | 🔜 Planned |

---

## Setup

```bash
# Install dependencies
pip install groq jinja2 pdfplumber

# Optional: LaTeX for PDF generation
# Windows: Install MiKTeX (https://miktex.org)
# macOS: brew install basictex
# Linux: apt install texlive-latex-base

# Set your Groq API key
export GROQ_API_KEY="gsk_..."
```

## Usage

```bash
# Start web GUI
python -m career_os.web

# Open http://127.0.0.1:8765

# CLI tools
python -m career_os.cli --db career-os-data/career-os.sqlite init
python -m career_os.cli --db career-os-data/career-os.sqlite add-knowledge --kind project --title "Career OS" --body "Built a local-first job application assistant."

# Run tests
python -m unittest discover -s tests
```
