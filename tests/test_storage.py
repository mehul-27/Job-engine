from __future__ import annotations

import hashlib
import sqlite3
from contextlib import closing
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from career_os.discovery import DiscoveredOpportunity
from career_os.storage import CareerStore
from career_os.domain import Company, TailoredResume


class CareerStoreTests(unittest.TestCase):
    def test_initialize_creates_schema(self) -> None:
        with TemporaryDirectory() as temp_dir:
            database = Path(temp_dir) / "career-os.sqlite"
            store = CareerStore(database)

            store.initialize()

            with closing(sqlite3.connect(database)) as connection:
                tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()}

            self.assertIn("user_profile", tables)
            self.assertIn("knowledge_item", tables)
            self.assertIn("evidence", tables)
            self.assertIn("knowledge_item_evidence", tables)
            self.assertIn("resume_record", tables)
            self.assertIn("role_target", tables)
            self.assertIn("opportunity", tables)
            self.assertIn("company", tables)
            self.assertIn("tailored_resume", tables)
            self.assertIn("application_workspace", tables)
            self.assertIn("application_material", tables)
            self.assertIn("approval", tables)
            self.assertIn("learning_record", tables)

    def test_adds_knowledge_item_with_evidence(self) -> None:
        with TemporaryDirectory() as temp_dir:
            store = CareerStore(Path(temp_dir) / "career-os.sqlite")
            store.initialize()
            evidence = store.add_evidence(kind="user_confirmation", title="Confirmed project", body="User confirmed this project is accurate.")

            item = store.add_knowledge_item(kind="project", title="Career OS", body="Built a local-first job application assistant.", status="verified", evidence_ids=[evidence.id])

            self.assertEqual([item], store.list_knowledge_items())
            self.assertEqual([evidence], store.list_evidence_for_item(item.id))

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

    def test_role_target_and_opportunity_dedup(self) -> None:
        with TemporaryDirectory() as temp_dir:
            store = CareerStore(Path(temp_dir) / "career-os.sqlite")
            store.initialize()
            role = store.add_role_target(title="Backend", keywords="python", location="Remote", remote_preference="remote", job_type="internship", source_url="http://example.test/jobs")
            job = DiscoveredOpportunity("source", "Python Intern", "Acme", "https://example.test/job", "Remote", "Python APIs")

            first = store.save_discovered_opportunities(role.id, [job])
            second = store.save_discovered_opportunities(role.id, [job])

            self.assertEqual(1, len(first))
            self.assertEqual(first[0].id, second[0].id)
            self.assertEqual(1, len(store.list_opportunities()))

    def test_upsert_company_creates_and_updates(self) -> None:
        with TemporaryDirectory() as temp_dir:
            store = CareerStore(Path(temp_dir) / "career-os.sqlite")
            store.initialize()

            c1 = store.upsert_company("Acme", url="https://acme.test")
            self.assertEqual("Acme", c1.name)
            self.assertFalse(c1.is_blacklisted)

            c2 = store.upsert_company("Acme", is_blacklisted=True)
            self.assertEqual(c1.id, c2.id)
            self.assertTrue(c2.is_blacklisted)

    def test_list_companies(self) -> None:
        with TemporaryDirectory() as temp_dir:
            store = CareerStore(Path(temp_dir) / "career-os.sqlite")
            store.initialize()
            store.upsert_company("A")
            store.upsert_company("B")
            self.assertEqual(2, len(store.list_companies()))

    def test_get_company_by_name(self) -> None:
        with TemporaryDirectory() as temp_dir:
            store = CareerStore(Path(temp_dir) / "career-os.sqlite")
            store.initialize()
            store.upsert_company("TestCo", url="https://test.co")
            found = store.get_company_by_name("TestCo")
            self.assertIsNotNone(found)
            self.assertEqual("TestCo", found.name)

    def test_update_opportunity_status(self) -> None:
        with TemporaryDirectory() as temp_dir:
            store = CareerStore(Path(temp_dir) / "career-os.sqlite")
            store.initialize()
            role = store.add_role_target(title="R", keywords="k", location=None, remote_preference="any", job_type=None, source_url="http://test")
            job = DiscoveredOpportunity("src", "Title", "Co", "http://job", "Loc", "Desc")
            saved = store.save_discovered_opportunities(role.id, [job])

            updated = store.update_opportunity_status(saved[0].id, "saved")
            self.assertEqual("saved", updated.status)

    def test_save_and_approve_tailored_resume(self) -> None:
        with TemporaryDirectory() as temp_dir:
            store = CareerStore(Path(temp_dir) / "career-os.sqlite")
            store.initialize()
            role = store.add_role_target(title="R", keywords="k", location=None, remote_preference="any", job_type=None, source_url="http://test")
            job = DiscoveredOpportunity("src", "Title", "Co", "http://job", "Loc", "Desc")
            saved = store.save_discovered_opportunities(role.id, [job])
            opp_id = saved[0].id

            tr = store.save_tailored_resume(opportunity_id=opp_id, file_path="/tmp/test.tex", provenance='{"src": "master_resume"}', version=1)
            self.assertFalse(tr.is_approved)
            self.assertEqual(1, len(store.list_tailored_resumes(opp_id)))

            approved = store.approve_tailored_resume(tr.id)
            self.assertTrue(approved.is_approved)

    def test_tailored_resume_versioning(self) -> None:
        with TemporaryDirectory() as temp_dir:
            store = CareerStore(Path(temp_dir) / "career-os.sqlite")
            store.initialize()
            role = store.add_role_target(title="R", keywords="k", location=None, remote_preference="any", job_type=None, source_url="http://test")
            job = DiscoveredOpportunity("src", "Title", "Co", "http://job", "Loc", "Desc")
            saved = store.save_discovered_opportunities(role.id, [job])
            opp_id = saved[0].id

            store.save_tailored_resume(opportunity_id=opp_id, file_path="/tmp/v1.tex", provenance="{}", version=1)
            store.save_tailored_resume(opportunity_id=opp_id, file_path="/tmp/v2.tex", provenance="{}", version=2)
            versions = store.list_tailored_resumes(opp_id)
            self.assertEqual(2, len(versions))
            self.assertEqual(2, versions[0].version)

    def test_create_workspace(self) -> None:
        with TemporaryDirectory() as temp_dir:
            store = CareerStore(Path(temp_dir) / "career-os.sqlite")
            store.initialize()
            role = store.add_role_target(title="R", keywords="k", location=None, remote_preference="any", job_type=None, source_url="http://test")
            opp = store.save_discovered_opportunities(role.id, [DiscoveredOpportunity("src", "T", "Co", "http://j", None, "D")])[0]

            ws = store.create_workspace(opp.id)

            self.assertEqual("created", ws.status)
            self.assertEqual(opp.id, ws.opportunity_id)
            self.assertEqual(ws.id, store.get_workspace(ws.id).id)
            self.assertEqual(ws.id, store.get_workspace_by_opportunity(opp.id).id)

    def test_workspace_lifecycle(self) -> None:
        with TemporaryDirectory() as temp_dir:
            store = CareerStore(Path(temp_dir) / "career-os.sqlite")
            store.initialize()
            role = store.add_role_target(title="R", keywords="k", location=None, remote_preference="any", job_type=None, source_url="http://test")
            opp = store.save_discovered_opportunities(role.id, [DiscoveredOpportunity("src", "T", "Co", "http://j", None, "D")])[0]
            ws = store.create_workspace(opp.id)

            for status in ["preparing", "ready_for_review", "browser_assisted", "paused", "browser_assisted", "submission_review", "submitted"]:
                ws = store.update_workspace_status(ws.id, status)

            self.assertEqual("submitted", ws.status)

    def test_workspace_materials(self) -> None:
        with TemporaryDirectory() as temp_dir:
            store = CareerStore(Path(temp_dir) / "career-os.sqlite")
            store.initialize()
            role = store.add_role_target(title="R", keywords="k", location=None, remote_preference="any", job_type=None, source_url="http://test")
            opp = store.save_discovered_opportunities(role.id, [DiscoveredOpportunity("src", "T", "Co", "http://j", None, "D")])[0]
            ws = store.create_workspace(opp.id)

            mat = store.add_material(workspace_id=ws.id, kind="tailored_resume", file_path="/tmp/t.pdf")
            self.assertEqual("tailored_resume", mat.kind)
            self.assertFalse(mat.is_approved)

            approved = store.approve_material(mat.id)
            self.assertTrue(approved.is_approved)
            self.assertEqual(1, len(store.list_materials(ws.id)))

    def test_workspace_approvals(self) -> None:
        with TemporaryDirectory() as temp_dir:
            store = CareerStore(Path(temp_dir) / "career-os.sqlite")
            store.initialize()
            role = store.add_role_target(title="R", keywords="k", location=None, remote_preference="any", job_type=None, source_url="http://test")
            opp = store.save_discovered_opportunities(role.id, [DiscoveredOpportunity("src", "T", "Co", "http://j", None, "D")])[0]
            ws = store.create_workspace(opp.id)

            a1 = store.add_approval(workspace_id=ws.id, action="use_generated_text", is_approved=True)
            a2 = store.add_approval(workspace_id=ws.id, action="submit_application", is_approved=False)
            approvals = store.list_approvals(ws.id)
            self.assertEqual(2, len(approvals))
            self.assertTrue(approvals[0].is_approved)
            self.assertFalse(approvals[1].is_approved)


if __name__ == "__main__":
    unittest.main()
