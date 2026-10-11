"""
EdgeDB: Edge Device Storage Layer (SQLite)
Maintains local append-only storage for offline devices.
Works completely independently of central database connectivity.
"""

import sqlite3
import os
from datetime import datetime, timezone
from src.classifier import classify_expense

class LocalStore:
    def __init__(self, db_path: str, device_uuid: str):
        self.db_path = db_path
        self.device_uuid = device_uuid
        os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
        self._init_schema()

    def _get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS local_expense (
                local_id INTEGER PRIMARY KEY AUTOINCREMENT,
                amount REAL NOT NULL CHECK (amount > 0),
                description TEXT NOT NULL,
                category TEXT NOT NULL,
                confidence REAL DEFAULT 1.0,
                event_time TEXT NOT NULL,
                synced INTEGER DEFAULT 0 CHECK (synced IN (0, 1)),
                sent_in_batch INTEGER DEFAULT NULL,
                client_version INTEGER DEFAULT 1
            );
            """)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS device_meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_local_unsynced ON local_expense(synced, local_id);")

            # Initialize metadata
            cursor.execute("INSERT OR IGNORE INTO device_meta (key, value) VALUES ('device_uuid', ?)", (self.device_uuid,))
            cursor.execute("INSERT OR IGNORE INTO device_meta (key, value) VALUES ('next_batch_seq', '1')")
            conn.commit()

    def log_expense(self, amount: float, description: str, category: str = None, event_time: str = None) -> int:
        """
        Record an expense locally on the edge device. Zero network calls.
        """
        confidence = 1.0
        if not category:
            category, confidence = classify_expense(description)

        if not event_time:
            event_time = datetime.now(timezone.utc).isoformat()

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO local_expense (amount, description, category, confidence, event_time, synced, client_version)
                VALUES (?, ?, ?, ?, ?, 0, 1)
            """, (amount, description, category, confidence, event_time))
            conn.commit()
            return cursor.lastrowid

    def get_unsynced(self):
        """Fetch all pending local expenses that have not yet reached central Postgres."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM local_expense WHERE synced = 0 ORDER BY local_id ASC")
            return [dict(row) for row in cursor.fetchall()]

    def mark_synced(self, local_ids: list, batch_seq: int):
        """Mark records as successfully integrated into the central database."""
        if not local_ids:
            return
        placeholders = ",".join("?" * len(local_ids))
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f"""
                UPDATE local_expense 
                SET synced = 1, sent_in_batch = ?
                WHERE local_id IN ({placeholders})
            """, [batch_seq] + local_ids)
            conn.commit()

    def allocate_next_batch_seq(self) -> int:
        """Get the next sequential client batch ID and increment."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM device_meta WHERE key = 'next_batch_seq'")
            row = cursor.fetchone()
            current_seq = int(row["value"]) if row else 1
            next_seq = current_seq + 1
            cursor.execute("UPDATE device_meta SET value = ? WHERE key = 'next_batch_seq'", (str(next_seq),))
            conn.commit()
            return current_seq

    def get_all_expenses(self):
        """Retrieve all local expenses for display on edge UI."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM local_expense ORDER BY local_id DESC")
            return [dict(row) for row in cursor.fetchall()]
