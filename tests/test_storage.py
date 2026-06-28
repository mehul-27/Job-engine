from __future__ import annotations

import sqlite3
from contextlib import closing
import unittest
from tempfile import TemporaryDirectory
from pathlib import Path

from career_os.storage import CareerStore


class CareerStoreTests(unittest.TestCase):
    def test_initialize_creates_schema(self) -> None:
        with TemporaryDirectory() as temp_dir:
            database = Path(temp_dir) / "career-os.sqlite"
            store = CareerStore(database)

            store.initialize()

            with closing(sqlite3.connect(database)) as connection:
                tables = {
                    row[0]
                    for row in connection.execute(
                        "SELECT name FROM sqlite_master WHERE type = 'table'"
                    ).fetchall()
                }

            self.assertIn("user_profile", tables)
            self.assertIn("knowledge_item", tables)
            self.assertIn("evidence", tables)
            self.assertIn("knowledge_item_evidence", tables)

    def test_adds_knowledge_item_with_evidence(self) -> None:
        with TemporaryDirectory() as temp_dir:
            store = CareerStore(Path(temp_dir) / "career-os.sqlite")
            store.initialize()
            evidence = store.add_evidence(
                kind="user_confirmation",
                title="Confirmed project",
                body="User confirmed this project is accurate.",
            )

            item = store.add_knowledge_item(
                kind="project",
                title="Career OS",
                body="Built a local-first job application assistant.",
                status="verified",
                evidence_ids=[evidence.id],
            )

            items = store.list_knowledge_items()
            linked_evidence = store.list_evidence_for_item(item.id)

            self.assertEqual([item], items)
            self.assertEqual([evidence], linked_evidence)

    def test_rejects_empty_knowledge_title(self) -> None:
        with TemporaryDirectory() as temp_dir:
            store = CareerStore(Path(temp_dir) / "career-os.sqlite")
            store.initialize()

            with self.assertRaises(ValueError):
                store.add_knowledge_item(kind="project", title=" ", body="Something true")


if __name__ == "__main__":
    unittest.main()
