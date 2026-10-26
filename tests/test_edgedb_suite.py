"""
EdgeDB Automated Test Suite (Review 3 Item 10: Testing & Validation)
Covers:
  - Unit tests for on-device NLP classifier
  - Edge SQLite isolation & durability
  - Central PostgreSQL connectivity & schema constraints
  - Idempotent batch sequencing
  - Concurrency conflict trigger enforcement
"""

import unittest
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.classifier import classify_expense
from src.local_store import LocalStore
from src.central_store import CentralStore
from src.sync_engine import SyncEngine
from src.config import PHONE_UUID, LAPTOP_UUID

class TestEdgeDB(unittest.TestCase):

    def setUp(self):
        self.central = CentralStore()
        self.engine = SyncEngine()

    def test_01_nlp_classifier(self):
        """Test on-device keyword classifier accuracy and confidence score bounds."""
        cat, conf = classify_expense("Starbucks cold brew latte")
        self.assertEqual(cat, "Food & Dining")
        self.assertGreaterEqual(conf, 0.80)
        self.assertLessEqual(conf, 1.0)

        cat2, conf2 = classify_expense("Uber auto ride to campus")
        self.assertEqual(cat2, "Travel & Transit")

        cat3, conf3 = classify_expense("Database Systems Korth book")
        self.assertEqual(cat3, "Books & Education")

    def test_02_local_store_isolation(self):
        """Test offline edge SQLite isolation and batch sequence counter."""
        with tempfile.TemporaryDirectory() as tmp:
            db_path = os.path.join(tmp, "test_edge.sqlite")
            store = LocalStore(db_path, PHONE_UUID)

            lid = store.log_expense(250.0, "Campus Lunch")
            self.assertGreaterEqual(lid, 1)

            unsynced = store.get_unsynced()
            self.assertEqual(len(unsynced), 1)
            self.assertEqual(unsynced[0]["synced"], 0)

            seq1 = store.allocate_next_batch_seq()
            seq2 = store.allocate_next_batch_seq()
            self.assertEqual(seq2, seq1 + 1)

    def test_03_central_db_connectivity_and_views(self):
        """Verify PostgreSQL connection and analytical reporting view integrity."""
        kpis = self.central.get_kpis()
        self.assertIn("total_spent", kpis)
        self.assertIn("device_count", kpis)
        self.assertGreaterEqual(kpis["device_count"], 3)

        categories = self.central.get_category_totals()
        self.assertGreaterEqual(len(categories), 6)

        activity = self.central.get_daily_activity()
        self.assertIsInstance(activity, list)

    def test_04_concurrency_trigger_protection(self):
        """Verify PL/pgSQL trigger intercepts stale updates and records conflict_log."""
        res = self.engine.simulate_conflict_demo(expense_id=1)
        self.assertEqual(res["status"], "CONFLICT_DETECTED_AND_RESOLVED")
        self.assertIn("conflict_logged", res)
        self.assertEqual(res["conflict_logged"]["strategy"], "TRIGGER_REJECTED_STALE_WRITE")

    def test_05_wearable_sensor_discrepancy(self):
        """Verify wearable authority policy on multi-sensor step collision."""
        res = self.engine.simulate_watch_conflict_demo()
        self.assertEqual(res["status"], "WATCH_PHONE_CONFLICT_RESOLVED")
        self.assertEqual(res["strategy"], "WEARABLE_HARDWARE_PRIORITY")
        self.assertEqual(res["watch_sensor"]["steps"], 11280)

if __name__ == "__main__":
    unittest.main()

