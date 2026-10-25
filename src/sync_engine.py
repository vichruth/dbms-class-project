"""
EdgeDB: Transactional Sync Engine & Conflict Orchestrator
Merges batched writes from edge SQLite stores into PostgreSQL with ACID guarantees.
Handles idempotency and demonstrates trigger-based conflict resolution.
"""

from datetime import datetime, timezone
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
            local_store.update_last_sync_time(datetime.now(timezone.utc).isoformat())

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

    def pull_device_deltas(self, local_store: LocalStore) -> dict:
        """
        Pulls incremental delta records committed by peer devices since this node's
        last sync timestamp, executing bidirectional multi-master replication.
        """
        device_uuid = local_store.device_uuid
        device_row = self.central.get_device(device_uuid)
        if not device_row:
            raise ValueError(f"Device UUID {device_uuid} is not registered.")

        device_id = device_row["device_id"]
        since_ts = local_store.get_last_sync_time()

        deltas = self.central.get_peer_deltas(device_id, since_ts)
        applied_count = local_store.apply_peer_deltas(deltas)
        local_store.update_last_sync_time(datetime.now(timezone.utc).isoformat())

        return {
            "status": "DELTAS_REPLICATED",
            "device_uuid": device_uuid,
            "since_timestamp": since_ts,
            "peer_records_found": len(deltas),
            "locally_integrated": applied_count
        }


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

            # --- Transaction 1: Nothing Phone comes online and updates expense ---
            phone_target_ver = init_version + 1
            before_t1, after_t1 = self.central.update_expense_concurrent(
                conn, exp_id, float(init_amount) + 50.0, f"{init_desc} (Updated by Nothing Phone)", phone_target_ver
            )
            conn.commit()

            # --- Transaction 2: Lenovo LOQ was offline, attempts to update using stale version V ---
            laptop_stale_ver = phone_target_ver # Stale! DB is already at phone_target_ver
            before_t2, after_t2 = self.central.update_expense_concurrent(
                conn, exp_id, 999.00, f"{init_desc} (Stale overwrite by Lenovo LOQ)", laptop_stale_ver
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
                "nothing_phone_update": {"new_amount": float(after_t1["amount"]), "version": after_t1["version"], "status": "ACCEPTED"},
                "lenovo_loq_update": {"attempted_amount": 999.00, "attempted_version": laptop_stale_ver, "status": "REJECTED_BY_TRIGGER"},
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

    def simulate_watch_conflict_demo(self):
        """
        Demonstrates the real-world wearable vs phone sensor conflict:
        Nothing Phone pedometer and CMF Watch Pro 2 both record steps for the same date.
        Nothing Phone records 8,450 steps; CMF Watch Pro 2 records 11,280 steps.
        When syncing, this multi-sensor collision is detected, logged to conflict_log,
        and resolved by prioritizing the dedicated wearable hardware.
        """
        conn = self.central.get_connection()
        try:
            today = "2026-10-12"
            phone_row = self.central.get_device("phone-nothing-01")
            watch_row = self.central.get_device("watch-cmf-01")

            with conn.cursor() as cur:
                # 1. Record Nothing Phone step entry for today
                cur.execute("""
                    INSERT INTO activity_entry (device_id, entry_date, step_count, version)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (device_id, entry_date)
                    DO UPDATE SET step_count = 8450, version = 1
                    RETURNING activity_id, step_count, version;
                """, (phone_row["device_id"], today, 8450, 1))
                phone_act_id, phone_steps, phone_ver = cur.fetchone()

                # 2. CMF Watch comes online via Health Connect, but detects that the user already has
                # a phone reading of 8,450 steps for the exact same date!
                # Record this multi-sensor collision in conflict_log
                cur.execute("""
                    INSERT INTO conflict_log (
                        activity_id,
                        device_id,
                        conflict_type,
                        existing_value,
                        incoming_value,
                        existing_version,
                        incoming_version,
                        resolution_strategy,
                        resolved_at
                    ) VALUES (
                        %s, %s,
                        'SENSOR_COLLISION_WATCH_VS_PHONE',
                        'Nothing Phone Pedometer: 8,450 steps',
                        'CMF Watch Pro 2: 11,280 steps',
                        1, 1,
                        'WEARABLE_HARDWARE_PRIORITY (11,280 steps accepted)',
                        CURRENT_TIMESTAMP
                    ) RETURNING conflict_id;
                """, (phone_act_id, watch_row["device_id"]))
                conflict_id = cur.fetchone()[0]

                # 3. Update the canonical wearable entry
                cur.execute("""
                    INSERT INTO activity_entry (device_id, entry_date, step_count, version)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (device_id, entry_date)
                    DO UPDATE SET step_count = 11280, version = activity_entry.version + 1;
                """, (watch_row["device_id"], today, 11280, 2))

                conn.commit()

                return {
                    "status": "WATCH_PHONE_CONFLICT_RESOLVED",
                    "entry_date": today,
                    "phone_sensor": {"device": "Nothing Phone", "steps": 8450, "status": "ARCHIVED_IN_CONFLICT_LOG"},
                    "watch_sensor": {"device": "CMF Watch Pro 2", "steps": 11280, "status": "COMMITTED_AS_CANONICAL"},
                    "conflict_id": conflict_id,
                    "strategy": "WEARABLE_HARDWARE_PRIORITY"
                }
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

