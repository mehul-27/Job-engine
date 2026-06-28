"""Business domain types for the first Career OS persistence milestone."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

KnowledgeItemKind = Literal[
    "project",
    "skill",
    "certification",
    "achievement",
    "story",
    "coursework",
    "research",
    "experiment",
    "other",
]

KnowledgeItemStatus = Literal["draft", "verified", "deprecated"]
EvidenceKind = Literal["master_resume", "user_note", "imported_document", "user_confirmation", "other"]


@dataclass(frozen=True)
class UserProfile:
    id: str
    display_name: str
    email: str | None
    location: str | None
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class KnowledgeItem:
    id: str
    kind: KnowledgeItemKind
    title: str
    body: str
    status: KnowledgeItemStatus
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class Evidence:
    id: str
    kind: EvidenceKind
    title: str
    body: str
    created_at: str
