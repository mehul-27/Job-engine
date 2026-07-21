from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from career_os.storage import CareerStore


class LearningRecordTests(unittest.TestCase):
    def _make_store(self) -> CareerStore:
        store = CareerStore(Path(self._temp_dir.name) / "career-os.sqlite")
        store.initialize()
        return store

    def setUp(self) -> None:
        self._temp_dir = TemporaryDirectory()

    def tearDown(self) -> None:
        self._temp_dir.cleanup()

    def test_upsert_creates_new_record(self) -> None:
        store = self._make_store()
        rec = store.upsert_learning_record("work_authorization", "US Citizen")
        self.assertEqual("work_authorization", rec.user_info_key)
        self.assertEqual("US Citizen", rec.value)
        self.assertEqual(1, rec.occurrences)

    def test_upsert_increments_occurrences(self) -> None:
        store = self._make_store()
        store.upsert_learning_record("gender", "Male")
        rec = store.upsert_learning_record("gender", "Male")
        self.assertEqual(2, rec.occurrences)

    def test_upsert_separate_values(self) -> None:
        store = self._make_store()
        store.upsert_learning_record("veteran", "No")
        rec = store.upsert_learning_record("veteran", "Yes")
        self.assertEqual(1, rec.occurrences)
        self.assertEqual("Yes", rec.value)

    def test_get_learning_records_empty(self) -> None:
        store = self._make_store()
        self.assertEqual([], store.get_learning_records())

    def test_get_learning_records_returns_all(self) -> None:
        store = self._make_store()
        store.upsert_learning_record("gender", "Male")
        store.upsert_learning_record("veteran", "No")
        records = store.get_learning_records()
        self.assertEqual(2, len(records))

    def test_get_learned_user_info_returns_best_per_key(self) -> None:
        store = self._make_store()
        store.upsert_learning_record("gender", "Male")
        store.upsert_learning_record("gender", "Male")
        store.upsert_learning_record("gender", "Female")
        info = store.get_learned_user_info()
        self.assertEqual("Male", info["gender"])

    def test_get_learned_user_info_empty(self) -> None:
        store = self._make_store()
        self.assertEqual({}, store.get_learned_user_info())

    def test_get_learned_user_info_multiple_keys(self) -> None:
        store = self._make_store()
        store.upsert_learning_record("gender", "Male")
        store.upsert_learning_record("veteran", "No")
        store.upsert_learning_record("veteran", "No")
        info = store.get_learned_user_info()
        self.assertEqual("Male", info["gender"])
        self.assertEqual("No", info["veteran"])

    def test_upsert_rejects_empty_key(self) -> None:
        store = self._make_store()
        with self.assertRaises(ValueError):
            store.upsert_learning_record("", "value")

    def test_upsert_rejects_empty_value(self) -> None:
        store = self._make_store()
        with self.assertRaises(ValueError):
            store.upsert_learning_record("key", "")
