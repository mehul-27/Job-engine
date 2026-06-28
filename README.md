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

## Design Philosophy

Career OS follows several core principles.

* The user always remains in control.
* AI assists rather than replaces decision making.
* Deterministic software is preferred over AI whenever possible.
* AI is only used where it provides clear value.
* Resume tailoring must never fabricate experience.
* Every important action should be explainable.
* Unknown situations should pause rather than fail silently.

---

## Current Scope

The first version focuses on:

* Desktop application
* Manual search sessions
* Human-in-the-loop workflow
* Resume tailoring
* Application assistance
* Knowledge base
* Local-first architecture

Future versions may introduce additional features, but they should not compromise the project's core philosophy.

---

## Development Workflow

This repository follows a documentation-first workflow.

Every feature is implemented in four stages:

1. Define requirements.
2. Review architecture.
3. Implement a single milestone.
4. Review and improve.

Documentation always precedes implementation.

---

## AI Development Workflow

AI assistants are expected to:

* Read all documentation before making decisions.
* Challenge assumptions when appropriate.
* Recommend alternatives with trade-offs.
* Implement only approved milestones.
* Avoid unrelated refactoring.
* Update documentation when architecture changes.

The documentation describes **what** the project should accomplish.

Implementation details remain intentionally flexible.

---

## Repository Structure

```
career-os/

docs/
.github/

backend/
frontend/
knowledge/
resume/
tests/

README.md
```

The repository structure will evolve over time as implementation progresses.

---

## Project Status

Current Phase:

Architecture & Design

No production code should be written until the initial architecture review is complete.

---

## License

To be decided.

---

## Final Note

Career OS is not intended to become another autonomous job application bot.

Its objective is to become a reliable engineering tool that helps produce higher quality applications with less repetitive work while keeping every important decision under human control.
