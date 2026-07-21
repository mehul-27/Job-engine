"""Business domain types for Career OS."""

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


@dataclass(frozen=True)
class ResumeRecord:
    id: str
    file_path: str
    filename: str
    checksum_sha256: str
    is_active: bool
    created_at: str


@dataclass(frozen=True)
class RoleTarget:
    id: str
    title: str
    keywords: str
    location: str | None
    remote_preference: str
    job_type: str | None
    source_url: str
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class Company:
    id: str
    name: str
    url: str | None
    notes: str | None
    is_blacklisted: bool
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class Opportunity:
    id: str
    role_target_id: str
    source: str
    title: str
    company: str
    url: str
    location: str | None
    description: str
    status: str
    content_hash: str
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class TailoredResume:
    id: str
    opportunity_id: str
    file_path: str
    provenance: str
    version: int
    is_approved: bool
    created_at: str
    updated_at: str


OpportunityStatus = Literal["new", "saved", "skipped", "applying", "blacklisted"]

WorkspaceStatus = Literal[
    "created", "preparing", "ready_for_review",
    "browser_assisted", "paused", "submission_review",
    "submitted", "abandoned",
]
MaterialKind = Literal[
    "tailored_resume", "cover_letter", "answer_set",
    "uploaded_document", "screenshot", "log", "submission_summary",
]


@dataclass(frozen=True)
class ApplicationWorkspace:
    id: str
    opportunity_id: str
    status: WorkspaceStatus
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class ApplicationMaterial:
    id: str
    workspace_id: str
    kind: MaterialKind
    file_path: str
    version: int
    is_approved: bool
    created_at: str


@dataclass(frozen=True)
class Approval:
    id: str
    workspace_id: str
    action: str
    is_approved: bool
    created_at: str


@dataclass(frozen=True)
class LearningRecord:
    id: str
    user_info_key: str
    value: str
    occurrences: int
    last_used: str
