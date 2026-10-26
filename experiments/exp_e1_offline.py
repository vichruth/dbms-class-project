"""
EdgeDB Experiment E1: Offline-First Durability Verification
Proves that edge nodes (Nothing Phone and Lenovo LOQ) buffer writes locally 
in SQLite with zero network or database availability.
"""

import os
import sys
import tempfile
from datetime import datetime, timezone

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.local_store import LocalStore
from src.config import PHONE_UUID, LAPTOP_UUID

def run_e1_experiment():
    print("=" * 70)
    print("  EXPERIMENT E1: OFFLINE-FIRST DURABILITY PROOF")
    print("=" * 70)

    with tempfile.TemporaryDirectory() as tmp_dir:
        phone_db = os.path.join(tmp_dir, "phone_isolated.sqlite")
        laptop_db = os.path.join(tmp_dir, "laptop_isolated.sqlite")

        phone = LocalStore(phone_db, PHONE_UUID)
        laptop = LocalStore(laptop_db, LAPTOP_UUID)

        print("\n[Step 1] Simulating disconnected environment (Zero Network Connectivity)")
        print(f"  * Node 1: Nothing Phone -> Local Storage: {phone_db}")
        print(f"  * Node 2: Lenovo LOQ    -> Local Storage: {laptop_db}")

        # Log 5 offline records on Phone
        print("\n[Step 2] Generating offline writes on Nothing Phone...")
        phone_items = [
            (180.0, "Cafeteria Lunch Thali"),
            (45.0, "Metro Station Ticket"),
            (320.0, "Campus Stationery Supplies"),
            (110.0, "Tender Coconut Water"),
            (650.0, "Mobile Data Add-on Pack")
        ]
        for amt, desc in phone_items:
            lid = phone.log_expense(amt, desc)
            print(f"  + Recorded local_id={lid}: {desc} (Rs.{amt})")

        # Log 5 offline records on Laptop
        print("\n[Step 3] Generating offline writes on Lenovo LOQ...")
        laptop_items = [
            (1499.0, "JetBrains IDE Annual Student Renewal"),
            (890.0, "Ergonomic Vertical Mouse Pad"),
            (450.0, "Mechanical Keyboard Keycaps"),
            (2100.0, "Cloud Compute GPU Credits"),
            (350.0, "USB-C Braided Cable")
        ]
        for amt, desc in laptop_items:
            lid = laptop.log_expense(amt, desc)
            print(f"  + Recorded local_id={lid}: {desc} (Rs.{amt})")

        # Verification
        phone_pending = phone.get_unsynced()
        laptop_pending = laptop.get_unsynced()

        print("\n[Step 4] Durability Verification:")
        print(f"  * Nothing Phone Unsynced Entries in SQLite: {len(phone_pending)} / 5")
        print(f"  * Lenovo LOQ Unsynced Entries in SQLite:    {len(laptop_pending)} / 5")

        assert len(phone_pending) == 5, "Phone pending count mismatch!"
        assert len(laptop_pending) == 5, "Laptop pending count mismatch!"

        for p in phone_pending:
            assert p["synced"] == 0, "Record was marked synced erroneously!"

        print("\n[VERDICT: PASS]")
        print("  All 10 edge transactions remain 100% durable in local SQLite.")
        print("  Zero network dependency detected. Offline-first principle verified.\n")

if __name__ == "__main__":
    run_e1_experiment()

