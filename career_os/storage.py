"""SQLite persistence for Career OS local milestones."""

from __future__ import annotations

import hashlib
import sqlite3
from collections.abc import Iterable
from contextlib import closing
from pathlib import Path
from typing import Any
from uuid import uuid4

from .discovery import DiscoveredOpportunity
from .domain import ApplicationMaterial, ApplicationWorkspace, Approval, Company, Evidence, EvidenceKind, KnowledgeItem, KnowledgeItemKind, LearningRecord, Opportunity, ResumeRecord, RoleTarget, TailoredResume, UserProfile

SCHEMA_VERSION = 6


def utc_now_sql() -> str:
    return "strftime('%Y-%m-%dT%H:%M:%fZ', 'now')"


class CareerStore:
    """Small SQLite store for Career OS V1."""

    def __init__(self, database_path: str | Path) -> None:
        self.database_path = Path(database_path)

    def connect(self) -> sqlite3.Connection:
        parent = self.database_path.parent
        if str(parent):
            parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def initialize(self) -> None:
        with closing(self.connect()) as connection:
            connection.executescript(
                f"""
                CREATE TABLE IF NOT EXISTS schema_version (
                    version INTEGER PRIMARY KEY,
                    applied_at TEXT NOT NULL DEFAULT ({utc_now_sql()})
                );

                CREATE TABLE IF NOT EXISTS user_profile (
                    id TEXT PRIMARY KEY,
                    display_name TEXT NOT NULL,
                    email TEXT,
                    location TEXT,
                    created_at TEXT NOT NULL DEFAULT ({utc_now_sql()}),
                    updated_at TEXT NOT NULL DEFAULT ({utc_now_sql()})
                );

                CREATE TABLE IF NOT EXISTS knowledge_item (
                    id TEXT PRIMARY KEY,
                    kind TEXT NOT NULL,
                    title TEXT NOT NULL,
                    body TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'draft',
                    created_at TEXT NOT NULL DEFAULT ({utc_now_sql()}),
                    updated_at TEXT NOT NULL DEFAULT ({utc_now_sql()}),
                    CHECK (status IN ('draft', 'verified', 'deprecated'))
                );

                CREATE TABLE IF NOT EXISTS evidence (
                    id TEXT PRIMARY KEY,
                    kind TEXT NOT NULL,
                    title TEXT NOT NULL,
                    body TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT ({utc_now_sql()})
                );

                CREATE TABLE IF NOT EXISTS knowledge_item_evidence (
                    knowledge_item_id TEXT NOT NULL,
                    evidence_id TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT ({utc_now_sql()}),
                    PRIMARY KEY (knowledge_item_id, evidence_id),
                    FOREIGN KEY (knowledge_item_id) REFERENCES knowledge_item(id) ON DELETE CASCADE,
                    FOREIGN KEY (evidence_id) REFERENCES evidence(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS resume_record (
                    id TEXT PRIMARY KEY,
                    file_path TEXT NOT NULL,
                    filename TEXT NOT NULL,
                    checksum_sha256 TEXT NOT NULL,
                    is_active INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL DEFAULT ({utc_now_sql()}),
                    CHECK (is_active IN (0, 1))
                );

                CREATE TABLE IF NOT EXISTS role_target (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    keywords TEXT NOT NULL,
                    location TEXT,
                    remote_preference TEXT NOT NULL DEFAULT 'any',
                    job_type TEXT,
                    source_url TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT ({utc_now_sql()}),
                    updated_at TEXT NOT NULL DEFAULT ({utc_now_sql()}),
                    CHECK (remote_preference IN ('any', 'remote', 'hybrid', 'onsite'))
                );

                CREATE TABLE IF NOT EXISTS opportunity (
                    id TEXT PRIMARY KEY,
                    role_target_id TEXT NOT NULL,
                    source TEXT NOT NULL,
                    title TEXT NOT NULL,
                    company TEXT NOT NULL,
                    url TEXT NOT NULL,
                    location TEXT,
                    description TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'new',
                    content_hash TEXT NOT NULL UNIQUE,
                    created_at TEXT NOT NULL DEFAULT ({utc_now_sql()}),
                    updated_at TEXT NOT NULL DEFAULT ({utc_now_sql()}),
                    FOREIGN KEY (role_target_id) REFERENCES role_target(id) ON DELETE CASCADE,
                    CHECK (status IN ('new', 'saved', 'skipped', 'applying', 'blacklisted'))
                );

                CREATE TABLE IF NOT EXISTS company (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL UNIQUE,
                    url TEXT,
                    notes TEXT,
                    is_blacklisted INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL DEFAULT ({utc_now_sql()}),
                    updated_at TEXT NOT NULL DEFAULT ({utc_now_sql()}),
                    CHECK (is_blacklisted IN (0, 1))
                );

                CREATE TABLE IF NOT EXISTS tailored_resume (
                    id TEXT PRIMARY KEY,
                    opportunity_id TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    provenance TEXT NOT NULL,
                    version INTEGER NOT NULL DEFAULT 1,
                    is_approved INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL DEFAULT ({utc_now_sql()}),
                    updated_at TEXT NOT NULL DEFAULT ({utc_now_sql()}),
                    FOREIGN KEY (opportunity_id) REFERENCES opportunity(id) ON DELETE CASCADE,
                    CHECK (is_approved IN (0, 1))
                );

                CREATE TABLE IF NOT EXISTS application_workspace (
                    id TEXT PRIMARY KEY,
                    opportunity_id TEXT NOT NULL UNIQUE,
                    status TEXT NOT NULL DEFAULT 'created',
                    created_at TEXT NOT NULL DEFAULT ({utc_now_sql()}),
                    updated_at TEXT NOT NULL DEFAULT ({utc_now_sql()}),
                    FOREIGN KEY (opportunity_id) REFERENCES opportunity(id) ON DELETE CASCADE,
                    CHECK (status IN ('created','preparing','ready_for_review','browser_assisted','paused','submission_review','submitted','abandoned'))
                );

                CREATE TABLE IF NOT EXISTS application_material (
                    id TEXT PRIMARY KEY,
                    workspace_id TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    version INTEGER NOT NULL DEFAULT 1,
                    is_approved INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL DEFAULT ({utc_now_sql()}),
                    FOREIGN KEY (workspace_id) REFERENCES application_workspace(id) ON DELETE CASCADE,
                    CHECK (kind IN ('tailored_resume','cover_letter','answer_set','uploaded_document','screenshot','log','submission_summary')),
                    CHECK (is_approved IN (0, 1))
                );

                CREATE TABLE IF NOT EXISTS approval (
                    id TEXT PRIMARY KEY,
                    workspace_id TEXT NOT NULL,
                    action TEXT NOT NULL,
                    is_approved INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL DEFAULT ({utc_now_sql()}),
                    FOREIGN KEY (workspace_id) REFERENCES application_workspace(id) ON DELETE CASCADE,
                    CHECK (is_approved IN (0, 1))
                );

                CREATE TABLE IF NOT EXISTS learning_record (
                    id TEXT PRIMARY KEY,
                    user_info_key TEXT NOT NULL,
                    value TEXT NOT NULL,
                    occurrences INTEGER NOT NULL DEFAULT 1,
                    last_used TEXT NOT NULL DEFAULT ({utc_now_sql()}),
                    UNIQUE(user_info_key, value)
                );

                INSERT OR IGNORE INTO schema_version (version) VALUES ({SCHEMA_VERSION});
                """
            )
            connection.commit()

    def upsert_user_profile(self, *, display_name: str, email: str | None = None, location: str | None = None, profile_id: str = "local-user") -> UserProfile:
        self._require_text(display_name, "display_name")
        with closing(self.connect()) as connection:
            connection.execute(
                f"""
                INSERT INTO user_profile (id, display_name, email, location)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    display_name = excluded.display_name,
                    email = excluded.email,
                    location = excluded.location,
                    updated_at = {utc_now_sql()}
                """,
                (profile_id, display_name, email, location),
            )
            row = connection.execute("SELECT * FROM user_profile WHERE id = ?", (profile_id,)).fetchone()
            connection.commit()
        return self._profile_from_row(row)

    def add_knowledge_item(self, *, kind: KnowledgeItemKind, title: str, body: str, evidence_ids: Iterable[str] = (), status: str = "draft") -> KnowledgeItem:
        self._require_text(kind, "kind")
        self._require_text(title, "title")
        self._require_text(body, "body")
        self._require_status(status)
        item_id = self._new_id("ki")
        with closing(self.connect()) as connection:
            connection.execute("INSERT INTO knowledge_item (id, kind, title, body, status) VALUES (?, ?, ?, ?, ?)", (item_id, kind, title, body, status))
            for evidence_id in evidence_ids:
                connection.execute("INSERT INTO knowledge_item_evidence (knowledge_item_id, evidence_id) VALUES (?, ?)", (item_id, evidence_id))
            row = connection.execute("SELECT * FROM knowledge_item WHERE id = ?", (item_id,)).fetchone()
            connection.commit()
        return self._knowledge_item_from_row(row)

    def add_evidence(self, *, kind: EvidenceKind, title: str, body: str) -> Evidence:
        self._require_text(kind, "kind")
        self._require_text(title, "title")
        self._require_text(body, "body")
        evidence_id = self._new_id("ev")
        with closing(self.connect()) as connection:
            connection.execute("INSERT INTO evidence (id, kind, title, body) VALUES (?, ?, ?, ?)", (evidence_id, kind, title, body))
            row = connection.execute("SELECT * FROM evidence WHERE id = ?", (evidence_id,)).fetchone()
            connection.commit()
        return self._evidence_from_row(row)

    def register_resume(self, file_path: str | Path, *, make_active: bool = True, filename: str | None = None) -> ResumeRecord:
        path = Path(file_path).expanduser().resolve()
        if not path.is_file():
            raise FileNotFoundError(f"resume file not found: {path}")
        checksum = self._sha256(path)
        display_name = filename or path.name
        self._require_text(display_name, "filename")
        resume_id = self._new_id("rs")
        with closing(self.connect()) as connection:
            if make_active:
                connection.execute("UPDATE resume_record SET is_active = 0")
            connection.execute("INSERT INTO resume_record (id, file_path, filename, checksum_sha256, is_active) VALUES (?, ?, ?, ?, ?)", (resume_id, str(path), display_name, checksum, 1 if make_active else 0))
            row = connection.execute("SELECT * FROM resume_record WHERE id = ?", (resume_id,)).fetchone()
            connection.commit()
        return self._resume_from_row(row)

    def add_role_target(self, *, title: str, keywords: str, location: str | None, remote_preference: str, job_type: str | None, source_url: str) -> RoleTarget:
        self._require_text(title, "title")
        self._require_text(keywords, "keywords")
        self._require_text(source_url, "source_url")
        if remote_preference not in {"any", "remote", "hybrid", "onsite"}:
            raise ValueError("remote_preference must be any, remote, hybrid, or onsite")
        role_id = self._new_id("rt")
        with closing(self.connect()) as connection:
            connection.execute(
                """
                INSERT INTO role_target (id, title, keywords, location, remote_preference, job_type, source_url)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (role_id, title, keywords, location, remote_preference, job_type, source_url),
            )
            row = connection.execute("SELECT * FROM role_target WHERE id = ?", (role_id,)).fetchone()
            connection.commit()
        return self._role_from_row(row)

    def list_role_targets(self) -> list[RoleTarget]:
        with closing(self.connect()) as connection:
            rows = connection.execute("SELECT * FROM role_target ORDER BY created_at DESC, title ASC").fetchall()
        return [self._role_from_row(row) for row in rows]

    def get_role_target(self, role_id: str) -> RoleTarget:
        with closing(self.connect()) as connection:
            row = connection.execute("SELECT * FROM role_target WHERE id = ?", (role_id,)).fetchone()
        return self._role_from_row(row)

    def save_discovered_opportunities(self, role_id: str, jobs: Iterable[DiscoveredOpportunity]) -> list[Opportunity]:
        saved: list[Opportunity] = []
        with closing(self.connect()) as connection:
            for job in jobs:
                content_hash = self._opportunity_hash(role_id, job.url, job.title, job.company)
                opportunity_id = self._new_id("op")
                connection.execute(
                    """
                    INSERT INTO opportunity (id, role_target_id, source, title, company, url, location, description, content_hash)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(content_hash) DO UPDATE SET
                        title = excluded.title,
                        company = excluded.company,
                        location = excluded.location,
                        description = excluded.description,
                        updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
                    """,
                    (opportunity_id, role_id, job.source, job.title, job.company, job.url, job.location, job.description, content_hash),
                )
                row = connection.execute("SELECT * FROM opportunity WHERE content_hash = ?", (content_hash,)).fetchone()
                saved.append(self._opportunity_from_row(row))
            connection.commit()
        return saved

    def list_opportunities(self) -> list[Opportunity]:
        with closing(self.connect()) as connection:
            rows = connection.execute("SELECT * FROM opportunity ORDER BY created_at DESC, title ASC").fetchall()
        return [self._opportunity_from_row(row) for row in rows]

    def list_resumes(self) -> list[ResumeRecord]:
        with closing(self.connect()) as connection:
            rows = connection.execute("SELECT * FROM resume_record ORDER BY is_active DESC, created_at DESC").fetchall()
        return [self._resume_from_row(row) for row in rows]

    def get_active_resume(self) -> ResumeRecord | None:
        with closing(self.connect()) as connection:
            row = connection.execute("SELECT * FROM resume_record WHERE is_active = 1 ORDER BY created_at DESC LIMIT 1").fetchone()
        return None if row is None else self._resume_from_row(row)

    def set_active_resume(self, resume_id: str) -> ResumeRecord:
        self._require_text(resume_id, "resume_id")
        with closing(self.connect()) as connection:
            row = connection.execute("SELECT * FROM resume_record WHERE id = ?", (resume_id,)).fetchone()
            if row is None:
                raise LookupError("resume was not found")
            connection.execute("UPDATE resume_record SET is_active = 0")
            connection.execute("UPDATE resume_record SET is_active = 1 WHERE id = ?", (resume_id,))
            row = connection.execute("SELECT * FROM resume_record WHERE id = ?", (resume_id,)).fetchone()
            connection.commit()
        return self._resume_from_row(row)

    def list_knowledge_items(self) -> list[KnowledgeItem]:
        with closing(self.connect()) as connection:
            rows = connection.execute("SELECT * FROM knowledge_item ORDER BY created_at DESC, title ASC").fetchall()
        return [self._knowledge_item_from_row(row) for row in rows]

    def list_evidence_for_item(self, knowledge_item_id: str) -> list[Evidence]:
        with closing(self.connect()) as connection:
            rows = connection.execute(
                """
                SELECT evidence.* FROM evidence
                JOIN knowledge_item_evidence ON knowledge_item_evidence.evidence_id = evidence.id
                WHERE knowledge_item_evidence.knowledge_item_id = ?
                ORDER BY evidence.created_at ASC
                """,
                (knowledge_item_id,),
            ).fetchall()
        return [self._evidence_from_row(row) for row in rows]

    def upsert_company(self, name: str, *, url: str | None = None, notes: str | None = None, is_blacklisted: bool = False) -> Company:
        company_id = self._new_id("co")
        with closing(self.connect()) as connection:
            existing = connection.execute("SELECT * FROM company WHERE name = ?", (name,)).fetchone()
            if existing:
                connection.execute(
                    "UPDATE company SET url = ?, notes = ?, is_blacklisted = ?, updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now') WHERE id = ?",
                    (url, notes, 1 if is_blacklisted else 0, existing["id"]),
                )
                row = connection.execute("SELECT * FROM company WHERE id = ?", (existing["id"],)).fetchone()
            else:
                connection.execute(
                    "INSERT INTO company (id, name, url, notes, is_blacklisted) VALUES (?, ?, ?, ?, ?)",
                    (company_id, name, url, notes, 1 if is_blacklisted else 0),
                )
                row = connection.execute("SELECT * FROM company WHERE id = ?", (company_id,)).fetchone()
            connection.commit()
        return self._company_from_row(row)

    def list_companies(self) -> list[Company]:
        with closing(self.connect()) as connection:
            rows = connection.execute("SELECT * FROM company ORDER BY name ASC").fetchall()
        return [self._company_from_row(row) for row in rows]

    def get_company_by_name(self, name: str) -> Company | None:
        with closing(self.connect()) as connection:
            row = connection.execute("SELECT * FROM company WHERE name = ?", (name,)).fetchone()
        return None if row is None else self._company_from_row(row)

    def update_opportunity_status(self, opportunity_id: str, status: str) -> Opportunity:
        if status not in {"new", "saved", "skipped", "applying", "blacklisted"}:
            raise ValueError(f"invalid status: {status}")
        with closing(self.connect()) as connection:
            connection.execute(
                f"UPDATE opportunity SET status = ?, updated_at = {utc_now_sql()} WHERE id = ?",
                (status, opportunity_id),
            )
            row = connection.execute("SELECT * FROM opportunity WHERE id = ?", (opportunity_id,)).fetchone()
            if row is None:
                raise LookupError("opportunity not found")
            connection.commit()
        return self._opportunity_from_row(row)

    def get_opportunity(self, opportunity_id: str) -> Opportunity:
        with closing(self.connect()) as connection:
            row = connection.execute("SELECT * FROM opportunity WHERE id = ?", (opportunity_id,)).fetchone()
            if row is None:
                raise LookupError("opportunity not found")
        return self._opportunity_from_row(row)

    def save_tailored_resume(self, *, opportunity_id: str, file_path: str, provenance: str, version: int = 1) -> TailoredResume:
        resume_id = self._new_id("tr")
        with closing(self.connect()) as connection:
            connection.execute(
                "INSERT INTO tailored_resume (id, opportunity_id, file_path, provenance, version) VALUES (?, ?, ?, ?, ?)",
                (resume_id, opportunity_id, file_path, provenance, version),
            )
            row = connection.execute("SELECT * FROM tailored_resume WHERE id = ?", (resume_id,)).fetchone()
            connection.commit()
        return self._tailored_resume_from_row(row)

    def approve_tailored_resume(self, resume_id: str) -> TailoredResume:
        with closing(self.connect()) as connection:
            connection.execute(
                f"UPDATE tailored_resume SET is_approved = 1, updated_at = {utc_now_sql()} WHERE id = ?",
                (resume_id,),
            )
            row = connection.execute("SELECT * FROM tailored_resume WHERE id = ?", (resume_id,)).fetchone()
            if row is None:
                raise LookupError("tailored resume not found")
            connection.commit()
        return self._tailored_resume_from_row(row)

    def list_tailored_resumes(self, opportunity_id: str) -> list[TailoredResume]:
        with closing(self.connect()) as connection:
            rows = connection.execute(
                "SELECT * FROM tailored_resume WHERE opportunity_id = ? ORDER BY version DESC", (opportunity_id,)
            ).fetchall()
        return [self._tailored_resume_from_row(row) for row in rows]

    def create_workspace(self, opportunity_id: str) -> ApplicationWorkspace:
        ws_id = self._new_id("ws")
        with closing(self.connect()) as connection:
            connection.execute(
                "INSERT INTO application_workspace (id, opportunity_id, status) VALUES (?, ?, 'created')",
                (ws_id, opportunity_id),
            )
            row = connection.execute("SELECT * FROM application_workspace WHERE id = ?", (ws_id,)).fetchone()
            connection.commit()
        return self._workspace_from_row(row)

    def get_workspace(self, workspace_id: str) -> ApplicationWorkspace:
        with closing(self.connect()) as connection:
            row = connection.execute("SELECT * FROM application_workspace WHERE id = ?", (workspace_id,)).fetchone()
            if row is None:
                raise LookupError("workspace not found")
        return self._workspace_from_row(row)

    def get_workspace_by_opportunity(self, opportunity_id: str) -> ApplicationWorkspace | None:
        with closing(self.connect()) as connection:
            row = connection.execute(
                "SELECT * FROM application_workspace WHERE opportunity_id = ?", (opportunity_id,)
            ).fetchone()
        return None if row is None else self._workspace_from_row(row)

    def list_workspaces(self) -> list[ApplicationWorkspace]:
        with closing(self.connect()) as connection:
            rows = connection.execute(
                "SELECT * FROM application_workspace ORDER BY created_at DESC"
            ).fetchall()
        return [self._workspace_from_row(row) for row in rows]

    def update_workspace_status(self, workspace_id: str, status: str) -> ApplicationWorkspace:
        valid = {"created", "preparing", "ready_for_review", "browser_assisted", "paused", "submission_review", "submitted", "abandoned"}
        if status not in valid:
            raise ValueError(f"invalid workspace status: {status}")
        with closing(self.connect()) as connection:
            connection.execute(
                f"UPDATE application_workspace SET status = ?, updated_at = {utc_now_sql()} WHERE id = ?",
                (status, workspace_id),
            )
            row = connection.execute("SELECT * FROM application_workspace WHERE id = ?", (workspace_id,)).fetchone()
            if row is None:
                raise LookupError("workspace not found")
            connection.commit()
        return self._workspace_from_row(row)

    def add_material(self, *, workspace_id: str, kind: str, file_path: str, version: int = 1) -> ApplicationMaterial:
        mat_id = self._new_id("mat")
        with closing(self.connect()) as connection:
            connection.execute(
                "INSERT INTO application_material (id, workspace_id, kind, file_path, version) VALUES (?, ?, ?, ?, ?)",
                (mat_id, workspace_id, kind, file_path, version),
            )
            row = connection.execute("SELECT * FROM application_material WHERE id = ?", (mat_id,)).fetchone()
            connection.commit()
        return self._material_from_row(row)

    def approve_material(self, material_id: str) -> ApplicationMaterial:
        with closing(self.connect()) as connection:
            connection.execute(
                "UPDATE application_material SET is_approved = 1 WHERE id = ?", (material_id,)
            )
            row = connection.execute("SELECT * FROM application_material WHERE id = ?", (material_id,)).fetchone()
            if row is None:
                raise LookupError("material not found")
            connection.commit()
        return self._material_from_row(row)

    def list_materials(self, workspace_id: str) -> list[ApplicationMaterial]:
        with closing(self.connect()) as connection:
            rows = connection.execute(
                "SELECT * FROM application_material WHERE workspace_id = ? ORDER BY created_at DESC",
                (workspace_id,),
            ).fetchall()
        return [self._material_from_row(row) for row in rows]

    def add_approval(self, *, workspace_id: str, action: str, is_approved: bool) -> Approval:
        app_id = self._new_id("ap")
        with closing(self.connect()) as connection:
            connection.execute(
                "INSERT INTO approval (id, workspace_id, action, is_approved) VALUES (?, ?, ?, ?)",
                (app_id, workspace_id, action, 1 if is_approved else 0),
            )
            row = connection.execute("SELECT * FROM approval WHERE id = ?", (app_id,)).fetchone()
            connection.commit()
        return self._approval_from_row(row)

    def list_approvals(self, workspace_id: str) -> list[Approval]:
        with closing(self.connect()) as connection:
            rows = connection.execute(
                "SELECT * FROM approval WHERE workspace_id = ? ORDER BY created_at ASC", (workspace_id,)
            ).fetchall()
        return [self._approval_from_row(row) for row in rows]

    def upsert_learning_record(self, user_info_key: str, value: str) -> LearningRecord:
        self._require_text(user_info_key, "user_info_key")
        self._require_text(value, "value")
        record_id = self._new_id("lr")
        with closing(self.connect()) as connection:
            existing = connection.execute(
                "SELECT * FROM learning_record WHERE user_info_key = ? AND value = ?",
                (user_info_key, value),
            ).fetchone()
            if existing:
                connection.execute(
                    f"UPDATE learning_record SET occurrences = occurrences + 1, last_used = {utc_now_sql()} WHERE id = ?",
                    (existing["id"],),
                )
                row = connection.execute("SELECT * FROM learning_record WHERE id = ?", (existing["id"],)).fetchone()
            else:
                connection.execute(
                    "INSERT INTO learning_record (id, user_info_key, value, occurrences) VALUES (?, ?, ?, 1)",
                    (record_id, user_info_key, value),
                )
                row = connection.execute("SELECT * FROM learning_record WHERE id = ?", (record_id,)).fetchone()
            connection.commit()
        return self._learning_record_from_row(row)

    def get_learning_records(self) -> list[LearningRecord]:
        with closing(self.connect()) as connection:
            rows = connection.execute(
                "SELECT * FROM learning_record ORDER BY occurrences DESC, last_used DESC"
            ).fetchall()
        return [self._learning_record_from_row(row) for row in rows]

    def get_learned_user_info(self) -> dict[str, str]:
        """Return the most-used value per key from learned records."""
        with closing(self.connect()) as connection:
            rows = connection.execute(
                """
                SELECT user_info_key, value, occurrences
                FROM learning_record
                WHERE (user_info_key, occurrences) IN (
                    SELECT user_info_key, MAX(occurrences)
                    FROM learning_record
                    GROUP BY user_info_key
                )
                """
            ).fetchall()
        return {row["user_info_key"]: row["value"] for row in rows}

    @staticmethod
    def _new_id(prefix: str) -> str:
        return f"{prefix}_{uuid4().hex}"

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as file:
            for block in iter(lambda: file.read(1024 * 1024), b""):
                digest.update(block)
        return digest.hexdigest()

    @staticmethod
    def _opportunity_hash(role_id: str, url: str, title: str, company: str) -> str:
        return hashlib.sha256("|".join([role_id, url, title, company]).encode("utf-8")).hexdigest()

    @staticmethod
    def _require_text(value: str, field_name: str) -> None:
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{field_name} is required")

    @staticmethod
    def _require_status(value: str) -> None:
        if value not in {"draft", "verified", "deprecated"}:
            raise ValueError("status must be draft, verified, or deprecated")

    @staticmethod
    def _profile_from_row(row: sqlite3.Row | None) -> UserProfile:
        if row is None:
            raise LookupError("user profile was not found")
        return UserProfile(**dict(row))

    @staticmethod
    def _knowledge_item_from_row(row: sqlite3.Row | None) -> KnowledgeItem:
        if row is None:
            raise LookupError("knowledge item was not found")
        return KnowledgeItem(**dict(row))

    @staticmethod
    def _evidence_from_row(row: sqlite3.Row | None) -> Evidence:
        if row is None:
            raise LookupError("evidence was not found")
        return Evidence(**dict(row))

    @staticmethod
    def _resume_from_row(row: sqlite3.Row | None) -> ResumeRecord:
        if row is None:
            raise LookupError("resume was not found")
        data: dict[str, Any] = dict(row)
        data["is_active"] = bool(data["is_active"])
        return ResumeRecord(**data)

    @staticmethod
    def _role_from_row(row: sqlite3.Row | None) -> RoleTarget:
        if row is None:
            raise LookupError("role target was not found")
        return RoleTarget(**dict(row))

    @staticmethod
    def _opportunity_from_row(row: sqlite3.Row | None) -> Opportunity:
        if row is None:
            raise LookupError("opportunity was not found")
        return Opportunity(**dict(row))

    @staticmethod
    def _company_from_row(row: sqlite3.Row | None) -> Company:
        if row is None:
            raise LookupError("company was not found")
        data: dict[str, Any] = dict(row)
        data["is_blacklisted"] = bool(data["is_blacklisted"])
        return Company(**data)

    @staticmethod
    def _tailored_resume_from_row(row: sqlite3.Row | None) -> TailoredResume:
        if row is None:
            raise LookupError("tailored resume was not found")
        data: dict[str, Any] = dict(row)
        data["is_approved"] = bool(data["is_approved"])
        return TailoredResume(**data)

    @staticmethod
    def _workspace_from_row(row: sqlite3.Row | None) -> ApplicationWorkspace:
        if row is None:
            raise LookupError("workspace was not found")
        return ApplicationWorkspace(**dict(row))

    @staticmethod
    def _material_from_row(row: sqlite3.Row | None) -> ApplicationMaterial:
        if row is None:
            raise LookupError("material was not found")
        data: dict[str, Any] = dict(row)
        data["is_approved"] = bool(data["is_approved"])
        return ApplicationMaterial(**data)

    @staticmethod
    def _approval_from_row(row: sqlite3.Row | None) -> Approval:
        if row is None:
            raise LookupError("approval was not found")
        data: dict[str, Any] = dict(row)
        data["is_approved"] = bool(data["is_approved"])
        return Approval(**data)

    @staticmethod
    def _learning_record_from_row(row: sqlite3.Row | None) -> LearningRecord:
        if row is None:
            raise LookupError("learning record was not found")
        return LearningRecord(**dict(row))
