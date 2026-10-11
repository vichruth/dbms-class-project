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
  - *"We populated realistic seed data across categories (Food, Travel, Tech, Education, Health), registered devices (Pixel 8, ThinkPad X1, CMF Watch Pro 2), baseline expenses, and daily step counts."*

---

### Step 3: Review 2 Evaluation Items

#### 7. Front-End Design
- **Artifact:** Open your browser at `http://127.0.0.1:5000`.
- **What to show:**
  - KPI summary cards (Total Expenditure, Smartwatch Activity, Offline Buffered Items, Conflicts).
  - Clean tabs showing Canonical PostgreSQL Expenses, Category Totals, Wearable Daily Activity, and the Concurrency Conflict Log.

#### 8. Business Logic Implementation
- **Artifacts:** [`src/local_store.py`](file:///home/vichruth/ML_PROJECTS/dbms%20class%20project/src/local_store.py), [`src/classifier.py`](file:///home/vichruth/ML_PROJECTS/dbms%20class%20project/src/classifier.py), [`src/sync_engine.py`](file:///home/vichruth/ML_PROJECTS/dbms%20class%20project/src/sync_engine.py).
- **Live Demo Action:**
  1. In the toolbar, select **📱 Phone**, amount **₹350**, description *"Blue Tokai cold brew coffee"*.
  2. Click **💾 Save to Offline SQLite**.
  3. Point to the UI: *"Notice that the expense was instantly saved in the phone's local SQLite database and categorized as 'Food & Dining' by our on-device NLP model. The central PostgreSQL database is completely untouched because the device is offline."*
  4. Click **🔄 Sync Phone Batch**.
  5. Point to the UI: *"Now our sync engine wrapped the upload in a database transaction, verified idempotency, inserted the batch record, and committed the expense into PostgreSQL. The dashboard updated immediately."*

#### 9. Database Connectivity
- **Artifacts:** [`src/central_store.py`](file:///home/vichruth/ML_PROJECTS/dbms%20class%20project/src/central_store.py), [`src/api.py`](file:///home/vichruth/ML_PROJECTS/dbms%20class%20project/src/api.py).
- **What to say:**
  - *"We connect Python directly to PostgreSQL 16 via `psycopg2`. We enforce strict transaction boundaries: autocommit is disabled, and every batch operation is wrapped in explicit `BEGIN ... COMMIT / ROLLBACK` blocks to maintain ACID atomicity."*

---

### Step 4: The Grand Finale — The Conflict Resolution Demo (1 minute)

This is the most impressive part of your project:
1. Click the red button: **⚡ Simulate Lost Update & Trigger Resolution**.
2. Switch to the **Conflict Audit Log** tab.
3. Explain the mechanism:
   > *"Here is the textbook lost-update problem in action: Phone and Laptop were both offline. Phone came online first and updated Expense #1 from version 1 to version 2. Split-seconds later, Laptop came online and tried to overwrite Expense #1 with stale version 2 data. Instead of silently losing the phone's data, our PostgreSQL BEFORE UPDATE trigger caught that the incoming version was stale, rejected the overwrite, and automatically inserted an audit record into `conflict_log`!"*

---

## 🛠️ How to Start the System Tomorrow Morning

In terminal:
```bash
cd "/home/vichruth/ML_PROJECTS/dbms class project"
./run.sh
```
Then open: **`http://127.0.0.1:5000`** in Chrome / Firefox.
