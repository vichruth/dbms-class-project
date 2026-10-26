"""
EdgeDB Experiment E4: 10,000-Row Database Scale & Index Optimization Benchmark
Tests queries under PostgreSQL EXPLAIN ANALYZE before and after B-Tree indexes.
Measures execution time, planning time, and scan node mechanics.
"""

import os
import sys
import random
import time
import json
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.central_store import CentralStore

SAMPLE_DESCRIPTIONS = [
    ("Blue Tokai Cold Brew", 1),
    ("Starbucks Hazelnut Latte", 1),
    ("Campus Mess Meal", 1),
    ("Uber Auto Katpadi", 2),
    ("Vellore City Bus", 2),
    ("IRCTC Train Reservation", 2),
    ("GitHub Copilot Seat", 3),
    ("AWS EC2 Free Tier", 3),
    ("USB-C Hub Multiport", 3),
    ("JioFiber Monthly 100Mbps", 4),
    ("Hostel Electricity Recharge", 4),
    ("Gym Monthly Membership", 5),
    ("Multivitamin Complex", 5),
    ("Database System Concepts Korth", 6),
    ("Operating Systems Silberschatz", 6)
]

def seed_bulk_data(central: CentralStore, target_count=10000):
    conn = central.get_connection()
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM expense;")
        current_count = cur.fetchone()[0]

        if current_count >= target_count:
            print(f"  * Central database already contains {current_count} expenses. Proceeding to benchmark.")
            conn.close()
            return

        needed = target_count - current_count
        print(f"  * Populating {needed} realistic rows into PostgreSQL for scale benchmarking...")

        base_time = datetime.now(timezone.utc)
        batch = []
        for i in range(needed):
            desc, cat_id = random.choice(SAMPLE_DESCRIPTIONS)
            amt = round(random.uniform(50.0, 3500.0), 2)
            conf = round(random.uniform(0.85, 0.99), 4)
            dev_id = random.choice([1, 2])
            event_ts = base_time - timedelta(minutes=random.randint(1, 150000))
            batch.append((dev_id, cat_id, amt, f"{desc} #{i+1}", conf, event_ts, 1))

            if len(batch) >= 1000:
                cur.executemany("""
                    INSERT INTO expense (device_id, category_id, amount, description, confidence, event_time, version)
                    VALUES (%s, %s, %s, %s, %s, %s, %s);
                """, batch)
                batch = []

        if batch:
            cur.executemany("""
                INSERT INTO expense (device_id, category_id, amount, description, confidence, event_time, version)
                VALUES (%s, %s, %s, %s, %s, %s, %s);
            """, batch)

        # Also populate 365 daily activity entries
        cur.execute("SELECT COUNT(*) FROM activity_entry;")
        act_count = cur.fetchone()[0]
        if act_count < 300:
            act_batch = []
            for d in range(365):
                dt = (base_time - timedelta(days=d)).date()
                steps = random.randint(4500, 16000)
                act_batch.append((3, dt, steps, 1)) # CMF Watch
            cur.executemany("""
                INSERT INTO activity_entry (device_id, entry_date, step_count, version)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (device_id, entry_date) DO NOTHING;
            """, act_batch)

        conn.commit()
        # Refresh planner statistics
        cur.execute("ANALYZE expense;")
        cur.execute("ANALYZE activity_entry;")
        conn.commit()

    conn.close()
    print("  * Scale dataset generation & ANALYZE complete.")

def run_explain_analyze(conn, query, params=None):
    with conn.cursor() as cur:
        explain_sql = f"EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) {query}"
        cur.execute(explain_sql, params or ())
        plan_json = cur.fetchone()[0]
        plan_data = plan_json[0]
        exec_time = plan_data.get("Execution Time", 0.0)
        plan_time = plan_data.get("Planning Time", 0.0)
        node_type = plan_data["Plan"]["Node Type"]
        return exec_time, plan_time, node_type, plan_json

def run_e4_benchmark():
    print("=" * 70)
    print("  EXPERIMENT E4: SCALE BENCHMARK & QUERY OPTIMIZATION (EXPLAIN ANALYZE)")
    print("=" * 70)

    central = CentralStore()
    seed_bulk_data(central, target_count=10000)

    queries = [
        {
            "id": "Q1",
            "name": "Device Time-Range Filter",
            "sql": """
                SELECT expense_id, amount, description, event_time 
                FROM expense 
                WHERE device_id = 1 AND event_time >= NOW() - INTERVAL '60 days' 
                ORDER BY event_time DESC;
            """,
            "index_name": "idx_expense_device_event",
            "index_ddl": "CREATE INDEX idx_expense_device_event ON expense(device_id, event_time DESC);"
        },
        {
            "id": "Q2",
            "name": "Category Expenditure Rollup",
            "sql": """
                SELECT c.category_name, COUNT(e.expense_id) AS total_count, SUM(e.amount) AS total_val
                FROM category c 
                JOIN expense e ON c.category_id = e.category_id 
                GROUP BY c.category_name;
            """,
            "index_name": "idx_expense_category",
            "index_ddl": "CREATE INDEX idx_expense_category ON expense(category_id);"
        },
        {
            "id": "Q3",
            "name": "Wearable Step Calendar Scan",
            "sql": """
                SELECT activity_id, entry_date, step_count 
                FROM activity_entry 
                WHERE entry_date BETWEEN '2026-05-01' AND '2026-10-25' 
                ORDER BY entry_date DESC;
            """,
            "index_name": "idx_activity_date",
            "index_ddl": "CREATE INDEX idx_activity_date ON activity_entry(entry_date DESC);"
        }
    ]

    conn = central.get_connection()
    results = []
    raw_logs = []

    print("\n[Step 1] Dropping indexes to establish Unindexed Baseline...")
    with conn.cursor() as cur:
        for q in queries:
            cur.execute(f"DROP INDEX IF EXISTS {q['index_name']};")
        conn.commit()
        cur.execute("ANALYZE expense; ANALYZE activity_entry;")
        conn.commit()

    print("\n[Step 2] Measuring Baseline Queries (Sequential Scan)...")
    unindexed_metrics = {}
    for q in queries:
        exec_times = []
        for _ in range(5):
            e_time, p_time, node, raw = run_explain_analyze(conn, q["sql"])
            exec_times.append(e_time)
        median_exec = sorted(exec_times)[len(exec_times)//2]
        unindexed_metrics[q["id"]] = (median_exec, node, raw)
        print(f"  * {q['id']} ({q['name']}): Median Exec Time = {median_exec:.3f} ms [Scan: {node}]")
        raw_logs.append(f"--- BASELINE {q['id']}: {q['name']} ---\n{json.dumps(raw, indent=2)}\n")

    print("\n[Step 3] Applying B-Tree Indexes & Refreshing Statistics...")
    with conn.cursor() as cur:
        for q in queries:
            cur.execute(q["index_ddl"])
        conn.commit()
        cur.execute("ANALYZE expense; ANALYZE activity_entry;")
        conn.commit()

    print("\n[Step 4] Measuring Indexed Performance (Index / Bitmap Scan)...")
    for q in queries:
        exec_times = []
        for _ in range(5):
            e_time, p_time, node, raw = run_explain_analyze(conn, q["sql"])
            exec_times.append(e_time)
        median_exec = sorted(exec_times)[len(exec_times)//2]
        base_exec, base_node, _ = unindexed_metrics[q["id"]]

        speedup = (base_exec / median_exec) if median_exec > 0 else 1.0
        results.append({
            "id": q["id"],
            "name": q["name"],
            "before_ms": base_exec,
            "before_node": base_node,
            "after_ms": median_exec,
            "after_node": node,
            "speedup": speedup
        })
        print(f"  * {q['id']} ({q['name']}): Median Exec Time = {median_exec:.3f} ms [Scan: {node}] -> Speedup: {speedup:.1f}x")
        raw_logs.append(f"--- INDEXED {q['id']}: {q['name']} ---\n{json.dumps(raw, indent=2)}\n")

    conn.close()

    # Save evidence log
    log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results", "e4_indexing.log")
    with open(log_path, "w") as f:
        f.write("\n".join(raw_logs))
    print(f"\n[Artifact Saved] Raw EXPLAIN ANALYZE logs stored in {log_path}")

    # Print Formatted Evaluation Markdown Table
    print("\n" + "=" * 85)
    print("  EXPLAIN ANALYZE BENCHMARK PERFORMANCE TABLE (Review 3 Evidence)")
    print("=" * 85)
    print(f"| Query ID | Workload Description | Unindexed Plan | Before (ms) | Indexed Plan | After (ms) | Speedup |")
    print(f"|:--------:|:---------------------|:--------------:|:-----------:|:------------:|:----------:|:-------:|")
    for r in results:
        print(f"| {r['id']} | {r['name']} | {r['before_node']} | {r['before_ms']:.2f} ms | {r['after_node']} | {r['after_ms']:.2f} ms | **{r['speedup']:.1f}x** |")
    print("=" * 85 + "\n")

if __name__ == "__main__":
    run_e4_benchmark()

