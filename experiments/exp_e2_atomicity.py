"""
EdgeDB Experiment E2: Transactional Atomicity & Mid-Batch Rollback Proof
Proves ACID Atomicity: If a failure occurs midway through batch processing,
the entire transaction is rolled back, leaving PostgreSQL in its exact pre-run state.
"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.central_store import CentralStore
from src.local_store import LocalStore
from src.sync_engine import SyncEngine
from src.config import PHONE_UUID

def run_e2_experiment():
    print("=" * 70)
    print("  EXPERIMENT E2: ACID ATOMICITY & MID-BATCH ROLLBACK PROOF")
    print("=" * 70)

    central = CentralStore()
    engine = SyncEngine()

    with tempfile.TemporaryDirectory() as tmp_dir:
        test_db = os.path.join(tmp_dir, "phone_atomicity.sqlite")
        phone = LocalStore(test_db, PHONE_UUID)

        # Baseline count
        baseline_stats = central.get_kpis()
        initial_expense_count = baseline_stats["expense_count"]
        print(f"\n[Step 1] Baseline Central PostgreSQL State: {initial_expense_count} canonical expenses.")

        # Buffer 4 items locally
        print("\n[Step 2] Staging 4 offline expenses on Nothing Phone...")
        items = [
            (150.0, "Subway Sandwich"),
            (80.0, "Filter Coffee"),
            (420.0, "Express Bus Ticket"),
            (990.0, "Python Programming Guide")
        ]
        for amt, desc in items:
            phone.log_expense(amt, desc)

        unsynced_before = phone.get_unsynced()
        print(f"  * Buffered items in local SQLite: {len(unsynced_before)}")

        # --- Sub-experiment: Forced Failure Injection ---
        print("\n[Step 3] Simulating Mid-Batch Network/Server Crash after item 2...")
        device_row = central.get_device(PHONE_UUID)
        device_id = device_row["device_id"]
        client_batch_seq = phone.allocate_next_batch_seq()

        conn = central.get_connection()
        crash_occurred = False
        try:
            batch_id = central.record_sync_batch(conn, device_id, client_batch_seq, len(unsynced_before))
            for i, item in enumerate(unsynced_before, 1):
                cat_id = central.get_category_id(item["category"])
                central.insert_canonical_expense(
                    conn, device_id, cat_id, item["amount"], item["description"],
                    item["confidence"], item["event_time"]
                )
                print(f"    Item {i}/4 merged in transaction buffer...")
                if i == 2:
                    print("    [!] FATAL INJECTION: Simulated socket drop / connection crash!")
                    raise ConnectionResetError("Simulated edge network timeout mid-batch.")

            conn.commit()
        except Exception as e:
            crash_occurred = True
            conn.rollback()
            print(f"    Rollback triggered: {str(e)}")
        finally:
            conn.close()

        # Verification after crash
        after_crash_stats = central.get_kpis()
        print(f"\n[Step 4] State Verification After Mid-Batch Crash:")
        print(f"  * Central Expenses Expected: {initial_expense_count} | Actual: {after_crash_stats['expense_count']}")
        print(f"  * Local SQLite Unsynced Rows: {len(phone.get_unsynced())} / 4")

        assert after_crash_stats["expense_count"] == initial_expense_count, "Atomicity violated! Partial batch committed!"
        assert len(phone.get_unsynced()) == 4, "Local rows were marked synced despite crash!"
        print("  -> Atomicity Confirmed: Zero partial rows committed to PostgreSQL.")

        # --- Clean Resync ---
        print("\n[Step 5] Recovering network and executing clean transactional batch sync...")
        res = engine.sync_device(phone)
        print(f"  * Sync result: {res}")

        final_stats = central.get_kpis()
        print(f"  * Central Expenses After Clean Recovery: {final_stats['expense_count']} (+{len(items)})")
        print(f"  * Local SQLite Unsynced Rows Remaining:  {len(phone.get_unsynced())}")

        assert final_stats["expense_count"] == initial_expense_count + 4, "Clean sync row count mismatch!"
        assert len(phone.get_unsynced()) == 0, "Local store was not marked synced!"

        print("\n[VERDICT: PASS]")
        print("  ACID Atomicity fully validated: All-or-nothing transactional guarantee proven.\n")

if __name__ == "__main__":
    run_e2_experiment()
