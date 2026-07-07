from __future__ import annotations

import hashlib
import sqlite3
from contextlib import closing
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

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
            self.assertIn("resume_record", tables)

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

    def test_registers_active_resume_without_parsing(self) -> None:
        with TemporaryDirectory() as temp_dir:
            resume = Path(temp_dir) / "resume.pdf"
            content = b"%PDF unchanged resume bytes"
            resume.write_bytes(content)
            store = CareerStore(Path(temp_dir) / "career-os.sqlite")
            store.initialize()

            record = store.register_resume(resume)

            self.assertEqual(resume.resolve(), Path(record.file_path))
            self.assertEqual("resume.pdf", record.filename)
            self.assertEqual(hashlib.sha256(content).hexdigest(), record.checksum_sha256)
            self.assertTrue(record.is_active)
            self.assertEqual(record, store.get_active_resume())

    def test_only_one_resume_is_active(self) -> None:
        with TemporaryDirectory() as temp_dir:
            first = Path(temp_dir) / "first.pdf"
            second = Path(temp_dir) / "second.pdf"
            first.write_bytes(b"first")
            second.write_bytes(b"second")
            store = CareerStore(Path(temp_dir) / "career-os.sqlite")
            store.initialize()

            first_record = store.register_resume(first)
            second_record = store.register_resume(second)
            records = store.list_resumes()

            self.assertEqual(second_record.id, store.get_active_resume().id)
            self.assertEqual(1, sum(record.is_active for record in records))
            self.assertFalse(next(record for record in records if record.id == first_record.id).is_active)


if __name__ == "__main__":
    unittest.main()
