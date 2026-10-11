"""
EdgeDB: Transactional Sync Engine & Conflict Orchestrator
Merges batched writes from edge SQLite stores into PostgreSQL with ACID guarantees.
Handles idempotency and demonstrates trigger-based conflict resolution.
"""

from src.central_store import CentralStore
from src.local_store import LocalStore

class SyncEngine:
    def __init__(self):
        self.central = CentralStore()

    def sync_device(self, local_store: LocalStore) -> dict:
        """
        Synchronizes an edge device's offline SQLite buffer into PostgreSQL.
        Guarantees Atomicity: either the whole batch lands, or nothing does.
        """
        device_uuid = local_store.device_uuid
        device_row = self.central.get_device(device_uuid)
        if not device_row:
            raise ValueError(f"Device UUID {device_uuid} is not registered in central database.")

        device_id = device_row["device_id"]
        unsynced_items = local_store.get_unsynced()

        if not unsynced_items:
            return {
                "status": "NO_OP",
                "message": "Device has no pending offline writes to sync.",
                "synced_count": 0
            }

        client_batch_seq = local_store.allocate_next_batch_seq()
        conn = self.central.get_connection()
        local_ids_to_mark = []

        try:
            # 1. Open Transaction & Record Sync Batch (Idempotency Key: device_id + seq)
            batch_id = self.central.record_sync_batch(conn, device_id, client_batch_seq, len(unsynced_items))

            # 2. Merge Each Expense Item
            for item in unsynced_items:
                cat_id = self.central.get_category_id(item["category"])
                self.central.insert_canonical_expense(
                    conn=conn,
                    device_id=device_id,
                    category_id=cat_id,
                    amount=item["amount"],
                    description=item["description"],
                    confidence=item["confidence"],
                    event_time=item["event_time"],
                    version=1
                )
                local_ids_to_mark.append(item["local_id"])

            # 3. Explicit Transaction Commit
            conn.commit()

            # 4. Only upon successful commit, advance the local edge cursor
            local_store.mark_synced(local_ids_to_mark, client_batch_seq)

            return {
                "status": "SUCCESS",
                "batch_id": batch_id,
                "client_batch_seq": client_batch_seq,
                "synced_count": len(local_ids_to_mark)
            }

        except Exception as e:
            # Atomic rollback on any error - central store remains clean
            conn.rollback()
            raise RuntimeError(f"Sync failed during batch execution: {str(e)}")
        finally:
            conn.close()

    def simulate_conflict_demo(self, expense_id: int = 1):
        """
        Demonstrates the centerpiece concurrency problem:
        Two devices attempt conflicting updates to the same expense.
        The PostgreSQL trigger catches the stale write and inserts into conflict_log.
        """
        conn = self.central.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT expense_id, amount, description, version FROM expense WHERE expense_id = %s", (expense_id,))
                row = cur.fetchone()
                if not row:
                    return {"status": "ERROR", "message": f"Expense ID {expense_id} not found."}
                
                exp_id, init_amount, init_desc, init_version = row

            # --- Transaction 1: Phone comes online and updates expense ---
            # Phone reads version V, increments to V+1 (Valid Update)
            phone_target_ver = init_version + 1
            before_t1, after_t1 = self.central.update_expense_concurrent(
                conn, exp_id, float(init_amount) + 50.0, f"{init_desc} (Updated by Phone)", phone_target_ver
            )
            conn.commit()

            # --- Transaction 2: Laptop was offline, attempts to update using stale version V ---
            # Laptop still thinks version is init_version, tries to write V+1 (which is now <= current DB version!)
            laptop_stale_ver = phone_target_ver # Stale! DB is already at phone_target_ver
            before_t2, after_t2 = self.central.update_expense_concurrent(
                conn, exp_id, 999.00, f"{init_desc} (Stale overwrite by Laptop)", laptop_stale_ver
            )
            conn.commit()

            # Fetch the latest conflict logged by the trigger
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT conflict_id, conflict_type, existing_version, incoming_version, 
                           existing_value, incoming_value, resolution_strategy, resolved_at
                    FROM conflict_log
                    ORDER BY conflict_id DESC LIMIT 1;
                """)
                conflict_row = cur.fetchone()

            return {
                "status": "CONFLICT_DETECTED_AND_RESOLVED",
                "expense_id": exp_id,
                "initial_state": {"amount": float(init_amount), "version": init_version},
                "phone_update": {"new_amount": float(after_t1["amount"]), "version": after_t1["version"], "status": "ACCEPTED"},
                "laptop_update": {"attempted_amount": 999.00, "attempted_version": laptop_stale_ver, "status": "REJECTED_BY_TRIGGER"},
                "conflict_logged": {
                    "conflict_id": conflict_row[0],
                    "type": conflict_row[1],
                    "existing_version": conflict_row[2],
                    "incoming_version": conflict_row[3],
                    "strategy": conflict_row[6]
                }
            }
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()
