"""SQLite persistence for the first local Career OS milestone."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterable
from contextlib import closing
from pathlib import Path
from typing import Any
from uuid import uuid4

from .domain import Evidence, EvidenceKind, KnowledgeItem, KnowledgeItemKind, UserProfile

SCHEMA_VERSION = 1


def utc_now_sql() -> str:
    return "strftime('%Y-%m-%dT%H:%M:%fZ', 'now')"


class CareerStore:
    """Small SQLite store for user profile, knowledge items, and evidence."""

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

                INSERT OR IGNORE INTO schema_version (version) VALUES ({SCHEMA_VERSION});
                """
            )
            connection.commit()

    def upsert_user_profile(
        self,
        *,
        display_name: str,
        email: str | None = None,
        location: str | None = None,
        profile_id: str = "local-user",
    ) -> UserProfile:
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

    def add_knowledge_item(
        self,
        *,
        kind: KnowledgeItemKind,
        title: str,
        body: str,
        evidence_ids: Iterable[str] = (),
        status: str = "draft",
    ) -> KnowledgeItem:
        self._require_text(kind, "kind")
        self._require_text(title, "title")
        self._require_text(body, "body")
        self._require_status(status)
        item_id = self._new_id("ki")
        with closing(self.connect()) as connection:
            connection.execute(
                """
                INSERT INTO knowledge_item (id, kind, title, body, status)
                VALUES (?, ?, ?, ?, ?)
                """,
                (item_id, kind, title, body, status),
            )
            for evidence_id in evidence_ids:
                connection.execute(
                    """
                    INSERT INTO knowledge_item_evidence (knowledge_item_id, evidence_id)
                    VALUES (?, ?)
                    """,
                    (item_id, evidence_id),
                )
            row = connection.execute("SELECT * FROM knowledge_item WHERE id = ?", (item_id,)).fetchone()
            connection.commit()
        return self._knowledge_item_from_row(row)

    def add_evidence(self, *, kind: EvidenceKind, title: str, body: str) -> Evidence:
        self._require_text(kind, "kind")
        self._require_text(title, "title")
        self._require_text(body, "body")
        evidence_id = self._new_id("ev")
        with closing(self.connect()) as connection:
            connection.execute(
                """
                INSERT INTO evidence (id, kind, title, body)
                VALUES (?, ?, ?, ?)
                """,
                (evidence_id, kind, title, body),
            )
            row = connection.execute("SELECT * FROM evidence WHERE id = ?", (evidence_id,)).fetchone()
            connection.commit()
        return self._evidence_from_row(row)

    def list_knowledge_items(self) -> list[KnowledgeItem]:
        with closing(self.connect()) as connection:
            rows = connection.execute(
                """
                SELECT * FROM knowledge_item
                ORDER BY created_at DESC, title ASC
                """
            ).fetchall()
        return [self._knowledge_item_from_row(row) for row in rows]

    def list_evidence_for_item(self, knowledge_item_id: str) -> list[Evidence]:
        with closing(self.connect()) as connection:
            rows = connection.execute(
                """
                SELECT evidence.*
                FROM evidence
                JOIN knowledge_item_evidence ON knowledge_item_evidence.evidence_id = evidence.id
                WHERE knowledge_item_evidence.knowledge_item_id = ?
                ORDER BY evidence.created_at ASC
                """,
                (knowledge_item_id,),
            ).fetchall()
        return [self._evidence_from_row(row) for row in rows]

    @staticmethod
    def _new_id(prefix: str) -> str:
        return f"{prefix}_{uuid4().hex}"

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
        data: dict[str, Any] = dict(row)
        return KnowledgeItem(**data)

    @staticmethod
    def _evidence_from_row(row: sqlite3.Row | None) -> Evidence:
        if row is None:
            raise LookupError("evidence was not found")
        return Evidence(**dict(row))
