"""
EdgeDB: Central PostgreSQL Store & Connection Layer
Encapsulates PostgreSQL database operations, explicit transaction controls,
and access to analytical views.
"""

import psycopg2
from psycopg2.extras import RealDictCursor
from src.config import PG_HOST, PG_PORT, PG_DB, PG_USER, PG_PASSWORD

class CentralStore:
    def __init__(self):
        self.conn_params = {
            "host": PG_HOST,
            "port": PG_PORT,
            "dbname": PG_DB,
            "user": PG_USER,
            "password": PG_PASSWORD
        }

    def get_connection(self):
        """Returns a new psycopg2 connection with autocommit disabled."""
        conn = psycopg2.connect(**self.conn_params)
        conn.autocommit = False
        return conn

    def get_device(self, device_uuid: str):
        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT * FROM device WHERE device_uuid = %s", (device_uuid,))
                return cur.fetchone()

    def get_category_id(self, category_name: str) -> int:
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT category_id FROM category WHERE category_name = %s", (category_name,))
                row = cur.fetchone()
                if row:
                    return row[0]
                # Fallback to 'Utilities & Bills'
                cur.execute("SELECT category_id FROM category WHERE category_name = 'Utilities & Bills'")
                return cur.fetchone()[0]

    def record_sync_batch(self, conn, device_id: int, client_batch_seq: int, record_count: int) -> int:
        """
        Record a sync batch atomically.
        Enforces idempotency: if batch exists, returns existing batch_id.
        """
        with conn.cursor() as cur:
            cur.execute("""
                SELECT batch_id, status FROM sync_batch 
                WHERE device_id = %s AND client_batch_seq = %s
            """, (device_id, client_batch_seq))
            existing = cur.fetchone()
            if existing:
                return existing[0]

            cur.execute("""
                INSERT INTO sync_batch (device_id, client_batch_seq, record_count, status)
                VALUES (%s, %s, %s, 'COMPLETED')
                RETURNING batch_id;
            """, (device_id, client_batch_seq, record_count))
            return cur.fetchone()[0]

    def insert_canonical_expense(self, conn, device_id: int, category_id: int, amount: float,
                                 description: str, confidence: float, event_time: str, version: int = 1) -> int:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO expense (device_id, category_id, amount, description, confidence, event_time, version)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING expense_id;
            """, (device_id, category_id, amount, description, confidence, event_time, version))
            return cur.fetchone()[0]

    def update_expense_concurrent(self, conn, expense_id: int, new_amount: float, new_desc: str,
                                  attempted_version: int, device_id: int = None):
        """
        Attempts to update an existing expense record.
        The PostgreSQL PL/pgSQL trigger 'trg_expense_conflict' validates:
        If attempted_version <= current version, it rejects the update and logs to conflict_log.
        """
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Query version before
            cur.execute("SELECT version, amount, description FROM expense WHERE expense_id = %s", (expense_id,))
            before = cur.fetchone()

            cur.execute("""
                UPDATE expense
                SET amount = %s, description = %s, version = %s
                WHERE expense_id = %s
                RETURNING expense_id, amount, description, version;
            """, (new_amount, new_desc, attempted_version, expense_id))
            after = cur.fetchone()
            return before, after

    def get_recent_expenses(self, limit: int = 25):
        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT e.expense_id, d.device_name, d.device_type, c.category_name,
                           e.amount, e.description, e.confidence, e.event_time, e.version, e.updated_at
                    FROM expense e
                    JOIN device d ON e.device_id = d.device_id
                    JOIN category c ON e.category_id = c.category_id
                    ORDER BY e.expense_id DESC
                    LIMIT %s;
                """, (limit,))
                return cur.fetchall()

    def get_category_totals(self):
        """Query analytical view v_category_totals"""
        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT * FROM v_category_totals;")
                return cur.fetchall()

    def get_daily_activity(self):
        """Query analytical view v_daily_activity"""
        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT * FROM v_daily_activity LIMIT 20;")
                return cur.fetchall()

    def get_device_summary(self):
        """Query view v_device_sync_summary"""
        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT * FROM v_device_sync_summary;")
                return cur.fetchall()

    def get_conflicts(self):
        """Query view v_recent_conflicts"""
        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT * FROM v_recent_conflicts;")
                return cur.fetchall()

    def get_kpis(self):
        """Aggregate high-level system metrics for the dashboard KPI cards."""
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT COALESCE(SUM(amount), 0), COUNT(*) FROM expense;")
                total_spent, expense_count = cur.fetchone()

                cur.execute("SELECT COALESCE(SUM(step_count), 0) FROM activity_entry;")
                total_steps = cur.fetchone()[0]

                cur.execute("SELECT COUNT(*) FROM device;")
                device_count = cur.fetchone()[0]

                cur.execute("SELECT COUNT(*) FROM conflict_log;")
                conflict_count = cur.fetchone()[0]

                return {
                    "total_spent": float(total_spent),
                    "expense_count": expense_count,
                    "total_steps": int(total_steps),
                    "device_count": device_count,
                    "conflict_count": conflict_count
                }

    def get_peer_deltas(self, device_id: int, since_ts: str):
        """
        Retrieves all canonical records committed by OTHER devices since the given timestamp.
        Used for bidirectional peer delta synchronization.
        """
        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT e.expense_id, e.amount, e.description, c.category_name,
                           e.confidence, e.event_time, e.version, e.updated_at
                    FROM expense e
                    JOIN category c ON e.category_id = c.category_id
                    WHERE e.device_id != %s AND e.updated_at > %s
                    ORDER BY e.updated_at ASC;
                """, (device_id, since_ts))
                rows = cur.fetchall()
                # Convert timestamps to isoformat strings for JSON serialization
                for r in rows:
                    if r.get("event_time"):
                        r["event_time"] = r["event_time"].isoformat()
                    if r.get("updated_at"):
                        r["updated_at"] = r["updated_at"].isoformat()
                return rows


