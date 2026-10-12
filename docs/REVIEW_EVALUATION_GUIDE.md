# EdgeDB — Review 1 & Review 2 Combined Evaluation Guide
**Student:** Vichruth M (24BCE2300) · B.Tech CSE, VIT Vellore  
**Course:** Database Management Systems  
**Project:** EdgeDB — Offline-First Relational Sync & Concurrency Management Engine  

---

## 🎯 Quick Presentation Script (5-Minute Walkthrough)

Follow this exact flow when presenting to your faculty:

### Step 1: High-Level Pitch (30 seconds)
> *"Most DBMS projects assume a single client is always connected to a server. EdgeDB solves real-world edge computing: devices like smartphones, laptops, and smartwatches log data completely offline in local SQLite stores. When network connectivity returns, our Python sync engine merges the records into a normalized PostgreSQL central database. Our centerpiece is handling concurrent write conflicts (the lost-update problem) using a DBMS PL/pgSQL trigger rather than relying on application code."*

---

### Step 2: Review 1 Evaluation Items

#### 1. Normalization (1NF, 2NF, 3NF, BCNF)
- **Artifact:** Open [`docs/normalization.md`](file:///home/vichruth/ML_PROJECTS/dbms%20class%20project/docs/normalization.md).
- **What to say:**
  1. *"We started with an unnormalized universal relation that contained device metadata, sync timestamps, category info, and expense records in one flat table."*
  2. *"We analyzed the 3 classical anomalies: Insertion Anomaly (can't register a device without an expense), Deletion Anomaly (deleting an expense deletes the category), and Update Anomaly (changing device OS requires updating thousands of rows)."*
  3. *"In 1NF, we ensured all attribute values are atomic and established the composite key."*
  4. *"In 2NF, we removed partial dependencies by separating `device` and `sync_batch` from `expense`."*
  5. *"In 3NF, we eliminated transitive dependencies ($ExpenseID \rightarrow CategoryName \rightarrow CategoryDesc$) by creating the standalone `category` relation."*
  6. *"Finally, we proved BCNF compliance: for every functional dependency $X \rightarrow Y$, the determinant $X$ is a superkey."*

#### 5. Database Design and Table Creation (DDL)
- **Artifact:** Open [`sql/central_schema.sql`](file:///home/vichruth/ML_PROJECTS/dbms%20class%20project/sql/central_schema.sql) and [`sql/triggers.sql`](file:///home/vichruth/ML_PROJECTS/dbms%20class%20project/sql/triggers.sql).
- **What to say:**
  1. *"Our central database uses PostgreSQL 16."*
  2. *"We implemented Enhanced ER (EER) Specialization using the Table-per-Subtype pattern: `device` is the supertype, with disjoint total subtypes `phone_device`, `laptop_device`, and `watch_device`."*
  3. *"We defined integrity constraints: Foreign Keys with `ON DELETE CASCADE / RESTRICT`, `CHECK (amount > 0)`, `CHECK (confidence >= 0.0 AND confidence <= 1.0)`, and compound `UNIQUE (device_id, client_batch_seq)` to guarantee idempotent syncs."*
  4. *"We wrote a native PL/pgSQL trigger `trg_expense_conflict` that intercepts stale updates before they overwrite data."*

#### 6. Data Population (DML)
- **Artifact:** Open [`sql/seed_data.sql`](file:///home/vichruth/ML_PROJECTS/dbms%20class%20project/sql/seed_data.sql) or show the rows on the dashboard.
- **What to say:**
  - *"We populated realistic seed data across categories (Food, Travel, Tech, Education, Health), registered devices (Nothing Phone, Lenovo LOQ, CMF Watch Pro 2), baseline expenses, and daily step counts."*

---

### Step 3: Review 2 Evaluation Items

#### 7. Front-End Design
- **Artifact:** Open your browser at `http://127.0.0.1:5000`.
- **What to show:**
  - Minimalist Apple-inspired dashboard interface.
  - KPI summary cards (Canonical Expenses, Wearable Steps, Pending Edge Writes, Conflicts).
  - Segmented controls showing Canonical Expenses, Wearable Steps, Device Telemetry, and the Conflict Audit Trail.

#### 8. Business Logic Implementation
- **Artifacts:** [`src/local_store.py`](file:///home/vichruth/ML_PROJECTS/dbms%20class%20project/src/local_store.py), [`src/classifier.py`](file:///home/vichruth/ML_PROJECTS/dbms%20class%20project/src/classifier.py), [`src/sync_engine.py`](file:///home/vichruth/ML_PROJECTS/dbms%20class%20project/src/sync_engine.py).
- **Live Demo Action:**
  1. In the toolbar, select **Nothing Phone**, amount **₹240**, description *"Blue Tokai Cold Brew"*.
  2. Click **Save to Offline Store**.
  3. Point to the UI: *"Notice that the expense was instantly saved in the Nothing Phone's local SQLite store and classified as 'Food & Dining'. Central PostgreSQL is completely untouched because the device was offline."*
  4. Click **Sync Nothing Phone**.
  5. Point to the UI: *"Our sync engine wrapped the upload in a PostgreSQL transaction, verified idempotency, inserted the batch record, and committed the expense. The dashboard updated immediately."*

#### 9. Database Connectivity
- **Artifacts:** [`src/central_store.py`](file:///home/vichruth/ML_PROJECTS/dbms%20class%20project/src/central_store.py), [`src/api.py`](file:///home/vichruth/ML_PROJECTS/dbms%20class%20project/src/api.py).
- **What to say:**
  - *"We connect Python directly to PostgreSQL 16 via `psycopg2`. We enforce strict transaction boundaries: autocommit is disabled, and every batch operation is wrapped in explicit `BEGIN ... COMMIT / ROLLBACK` blocks to maintain ACID atomicity."*

---

### Step 4: The Grand Finale — Two Real-World Concurrency Demos (1 minute)

1. **Demo A: CMF Watch Pro 2 vs. Nothing Phone Step Conflict**
   - Click: **CMF Watch vs. Nothing Phone Steps**.
   - Show the toast & switch to **Conflict Audit Log** tab.
   - Explain:
     > *"Both my Nothing Phone (in pocket) and CMF Watch Pro 2 (on wrist) recorded steps today offline. Phone recorded 8,450 steps; Watch recorded 11,280 steps. When syncing for the same date, rather than a silent overwrite, PostgreSQL intercepted the collision, applied `WEARABLE_HARDWARE_PRIORITY` to retain 11,280 steps, and archived the phone's reading in `conflict_log`!"*

2. **Demo B: Nothing Phone vs. Lenovo LOQ Expense Collision**
   - Click: **Nothing Phone vs. Lenovo LOQ Expenses**.
   - Show the toast & explain:
     > *"Nothing Phone and Lenovo LOQ both edited Expense #1 while offline. Nothing Phone synced first to version 2. When Lenovo LOQ synced with stale version 2 data, our PL/pgSQL trigger `trg_expense_conflict` caught `NEW.version <= OLD.version`, rejected the stale overwrite, and logged it into `conflict_log`."*

---

## 🛠️ How to Start the System Tomorrow Morning

In terminal:
```bash
cd "/home/vichruth/ML_PROJECTS/dbms class project"
./run.sh
```
Then open: **`http://127.0.0.1:5000`** in Chrome / Firefox.

