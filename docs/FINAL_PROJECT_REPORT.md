# EdgeDB: An Edge-Cloud Hybrid DBMS with Autonomous Multi-Master Synchronization and Semantic Conflict Reconciliation

**Course:** Database Management Systems (CSE)  
**Student:** Vichruth M (24BCE2300)  
**Programme:** B.Tech Computer Science and Engineering  
**Institution:** School of Computer Science and Engineering (SCOPE), VIT Vellore  
**Date:** October 2026  

---

## Abstract
Traditional relational database management systems assume persistent client-server connectivity, a model that fundamentally breaks down in ubiquitous edge computing. In a personal multi-device ecosystem—comprising smartphones, personal workstations, and smart wearables—devices frequently produce, modify, and store state while completely disconnected from the network. Naive central synchronization often leads to the catastrophic **lost-update anomaly**, wherein concurrent writes silently overwrite one another without an audit trail, or where multi-sensor discrepancies (such as smartwatches vs. smartphone pedometers) are arbitrarily dropped.

This project designs, implements, and rigorously stress-tests **EdgeDB**, an edge-cloud hybrid relational database management system. EdgeDB features:
1. **Autonomous Edge Storage:** Zero-network local persistence using flat SQLite engines on edge nodes (**Nothing Phone** and **Lenovo LOQ**), coupled with an on-device NLP expense categorizer.
2. **Normalized Central Cloud Store:** A Boyce-Codd Normal Form (BCNF) schema on **PostgreSQL 16** with Enhanced ER (EER) Table-per-Subtype specialization.
3. **DBMS-Native Concurrency Control:** Native PL/pgSQL triggers enforcing optimistic concurrency control, automatically rejecting stale writes and maintaining a transparent `conflict_log` audit trail.
4. **Biometric Multi-Sensor Reconciliation:** A domain-aware resolution engine resolving physical telemetry collisions between **CMF Watch Pro 2** and smartphone pocket sensors via dedicated wearable precedence.
5. **Bidirectional Delta Synchronization:** Multi-master delta replication enabling nodes to pull peer modifications.
6. **Empirical Benchmarking & Validation:** A formal experimental suite verifying ACID atomicity, offline durability, and a 10,000-row `EXPLAIN ANALYZE` query optimization benchmark demonstrating query latency reductions from 5.21ms to 3.60ms.

---

## 1. Introduction & Motivation
Most undergraduate database curricula examine single-client architectures: hospital records, student registration, or banking systems where every transaction immediately locks or commits against a central monolithic database. In reality, modern mobile and IoT applications are decentralized. When a user logs an expense on a flight, or walks 10,000 steps with their smartphone on a desk while wearing a smartwatch, the database must write locally first and reconcile centrally later.

### The Lost-Update Crisis
When two disconnected devices modify the same logical entity offline:
- Device A updates Expense #1 from ₹300 to ₹350.
- Device B updates Expense #1 from ₹300 to ₹400.
If both sync naively, whichever transaction lands last simply overwrites the first. The user's earlier financial or health log quietly vanishes. Standard database isolation levels like `READ COMMITTED` do not prevent this because the transactions run at distinct wall-clock times.

EdgeDB solves this problem directly within the relational database engine using native triggers and mathematical version tracking rather than relying on brittle client-side application logic.

---

## 2. System Architecture

```
+-----------------------------------------------------------------------------------+
|                                  EDGE TIER                                        |
|                                                                                   |
|  +-----------------------+     +-----------------------+     +------------------+ |
|  |     Nothing Phone     |     |       Lenovo LOQ      |     | CMF Watch Pro 2  | |
|  |  (Nothing OS/Android) |     |   (Windows / Linux)   |     | (Biomedical PPG) | |
|  |  +-----------------+  |     |  +-----------------+  |     |  +-------------+ | |
|  |  |  SQLite Storage |  |     |  |  SQLite Storage |  |     |  | Google      | | |
|  |  | (nothing_phone) |  |     |  |   (lenovo_loq)  |  |     |  | Health Conn | | |
|  |  +-----------------+  |     |  +-----------------+  |     |  +-------------+ | |
|  |  | On-Device NLP   |  |     |  | Local Analytic  |  |     |  | Wearable    | | |
|  |  | Categorizer     |  |     |  | Delta Cache     |  |     |  | Accelerom.  | | |
|  +----------+------------+     +-----------+-----------+     +--------+---------+ |
+-------------|------------------------------|--------------------------|-----------+
              | (Push Batches / Pull Deltas) | (Bidirectional Sync)     | (HTTP POST)
              v                              v                          v
+-----------------------------------------------------------------------------------+
|                        TRANSACTIONAL SYNC & API LAYER                             |
|                                                                                   |
|  * Python 3 / Flask REST API (autocommit=False)                                   |
|  * Unit of Atomicity: Client Batch Sequence (device_id, client_batch_seq)         |
|  * Idempotency Guard & Delta Replication Cursor Tracking                          |
+------------------------------------+----------------------------------------------+
                                     | ACID Transactions (BEGIN/COMMIT/ROLLBACK)
                                     v
+-----------------------------------------------------------------------------------+
|                            CENTRAL CLOUD STORE                                    |
|                               PostgreSQL 16                                       |
|                                                                                   |
|  +------------------------------------------------------------------------------+ |
|  | Canonical Relational Tables (BCNF Normalized)                                 | |
|  | * device (Supertype) -> phone_device, laptop_device, watch_device (Subtypes)  | |
|  | * category (Lookup Entity)                                                   | |
|  | * expense (Canonical Versioned Ledger)                                       | |
|  | * activity_entry (Daily Biometric Rollup)                                    | |
|  | * sync_batch (Unit of Idempotency)                                           | |
|  | * conflict_log (Audit Trail)                                                 | |
|  +------------------------------------------------------------------------------+ |
|  | Native Database Mechanisms                                                   | |
|  | * PL/pgSQL Trigger: trg_expense_conflict (Optimistic Lock Overwrite Blocker) | |
|  | * PL/pgSQL Trigger: trg_activity_conflict (Sensor Discrepancy Manager)       | |
|  | * Reporting Views: v_category_totals, v_daily_activity, v_device_sync_summary  | |
|  | * Composite B-Tree Indexes: idx_expense_device_event, idx_activity_date       | |
+-----------------------------------------------------------------------------------+
```

---

## 3. Mathematical Normalization (Review 1)

### 3.1 The Universal Unnormalized Relation (UNF)
$$\text{UNF}(\underline{\text{DeviceUUID}}, \underline{\text{ClientBatchSeq}}, \underline{\text{ItemIndex}}, \text{DeviceName}, \text{DeviceType}, \text{HWInfo}, \text{CategoryName}, \text{CategoryDesc}, \text{Amount}, \text{ExpenseDesc}, \text{EventTime}, \text{SyncTime})$$

Classical Anomalies observed in UNF:
- **Insertion Anomaly:** A new hardware device cannot be registered without logging an expense.
- **Deletion Anomaly:** Deleting the only transaction in a category erases the category definition from existence.
- **Update Anomaly:** Updating a device's OS version requires updating $N$ historical rows.

### 3.2 1NF Decomposition
Eliminated non-atomic and repeating attributes. Established composite primary key:
$$K = \{\text{DeviceUUID}, \text{ClientBatchSeq}, \text{ItemIndex}\}$$

### 3.3 2NF Decomposition (Removal of Partial Dependencies)
Identified functional dependencies where non-prime attributes depend on proper subsets of $K$:
- $\{\text{DeviceUUID}\} \rightarrow \{\text{DeviceName}, \text{DeviceType}, \text{HWInfo}\}$ (Partial dependency on key subset)
- $\{\text{DeviceUUID}, \text{ClientBatchSeq}\} \rightarrow \{\text{SyncTime}\}$ (Partial dependency)
Decomposed into: `DEVICE`, `SYNC_BATCH`, and `EXPENSE_2NF`.

### 3.4 3NF Decomposition (Removal of Transitive Dependencies)
In `EXPENSE_2NF`:
$$\text{ExpenseID} \rightarrow \text{CategoryName} \quad \text{and} \quad \text{CategoryName} \rightarrow \text{CategoryDesc}$$
Decomposed `category` into its own relation, replacing the transitive string with Foreign Key `category_id`.

### 3.5 BCNF Verification
A relation is in BCNF if for every non-trivial functional dependency $X \rightarrow Y$, $X$ is a superkey.

| Relation | Determinant ($X$) | Dependent ($Y$) | Is $X$ Superkey? | BCNF Valid? |
|---|---|---|:---:|:---:|
| `device` | `device_id` | `device_uuid, device_name, device_type` | Yes (PK) | **Yes** |
| `device` | `device_uuid` | `device_id, device_name, device_type` | Yes (Candidate) | **Yes** |
| `category` | `category_id` | `category_name, description` | Yes (PK) | **Yes** |
| `sync_batch` | `{device_id, client_batch_seq}` | `batch_id, received_at, status` | Yes (Candidate) | **Yes** |
| `expense` | `expense_id` | `device_id, category_id, amount, description, version` | Yes (PK) | **Yes** |
| `activity_entry` | `{device_id, entry_date}` | `activity_id, step_count, version` | Yes (Candidate) | **Yes** |

---

## 4. Enhanced ER (EER) Specialization
EdgeDB implements **Disjoint, Total Specialization** for edge nodes:
```
                [ DEVICE ] (Supertype)
                    |
        +-----------+-----------+
        | (d, t)    |           |
        v           v           v
  [ PhoneDevice ] [ LaptopDevice ] [ WatchDevice ]
```
- `phone_device` $(\underline{\text{device\_id}}, \text{os\_version}, \text{imei})$
- `laptop_device` $(\underline{\text{device\_id}}, \text{os\_name}, \text{mac\_address})$
- `watch_device` $(\underline{\text{device\_id}}, \text{watch\_model}, \text{firmware\_version})$

Each subtype table shares the exact primary key of the supertype `device(device_id)`, maintaining referential integrity via `ON DELETE CASCADE`.

---

## 5. DBMS-Native Concurrency Mechanisms

### 5.1 PL/pgSQL Trigger Algorithm for Optimistic Locking
```sql
CREATE OR REPLACE FUNCTION trg_fn_detect_expense_conflict()
RETURNS TRIGGER AS $$
BEGIN
    -- Check if incoming write is stale (Version mismatch)
    IF NEW.version <= OLD.version THEN
        -- Intercept and log directly into conflict_log
        INSERT INTO conflict_log (
            expense_id, conflict_type, existing_value, incoming_value,
            existing_version, incoming_version, resolution_strategy, resolved_at
        ) VALUES (
            OLD.expense_id, 'OPTIMISTIC_CONCURRENCY_VIOLATION',
            format('Amount: %s | Description: "%s"', OLD.amount, OLD.description),
            format('Amount: %s | Description: "%s"', NEW.amount, NEW.description),
            OLD.version, NEW.version, 'TRIGGER_REJECTED_STALE_WRITE', CURRENT_TIMESTAMP
        );
        -- Reject stale overwrite by retaining canonical OLD state
        RETURN OLD;
    END IF;

    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
```

---

## 6. Experimental Validation & Results (Review 3 Item 10)

Four formal experiments were designed, executed, and archived in the repository:

### Experiment E1: Offline Durability Verification
- **Protocol:** Disconnected edge nodes generated 10 transactions (5 on Nothing Phone, 5 on Lenovo LOQ) with PostgreSQL offline.
- **Result:** 100% of writes were durably retained in SQLite. Zero network exceptions occurred.
- **Outcome:** **PASS** (Evidence: `experiments/results/e1_offline.log`).

### Experiment E2: ACID Transactional Atomicity & Crash Rollback
- **Protocol:** Staged 4 expenses; injected a socket disconnect after item 2.
- **Result:** PostgreSQL transaction rolled back entirely; central row count remained unchanged (baseline: 6 rows). Local SQLite rows remained marked `synced=0`. Clean resync succeeded without duplicate anomalies.
- **Outcome:** **PASS** (Evidence: `experiments/results/e2_atomicity.log`).

### Experiment E3: Concurrency Race & Multi-Sensor Discrepancy
- **Run A (Naive):** Demonstrates the silent lost update where T2 overwrites T1 with zero audit logs.
- **Run B (EdgeDB Trigger):** `trg_expense_conflict` catches stale write (v2 attempted on v2), preserves canonical value (₹350.00), and records collision in `conflict_log`.
- **Run C (Multi-Sensor):** Reconciles CMF Watch Pro 2 (11,280 steps) vs. Nothing Phone (8,450 steps) on the same date via `WEARABLE_HARDWARE_PRIORITY`.
- **Outcome:** **PASS** (Evidence: `experiments/results/e3_concurrency.log`).

### Experiment E4: Scale Benchmark & EXPLAIN ANALYZE Optimization (10,000 Rows)
The central PostgreSQL instance was scaled to 10,000 canonical expense records and 365 daily activity logs. Queries were analyzed before and after B-Tree index creation:

| Query Workload | Unindexed Plan | Execution (Before) | Indexed Plan | Execution (After) | Speedup |
|---|:---:|:---:|:---:|:---:|:---:|
| **Q1: Device Time-Range Filter**<br>`WHERE device_id=1 AND event_time >= NOW() - 60d` | Sort / Seq Scan | 5.21 ms | Sort / Index Scan | 3.60 ms | **1.45×** |
| **Q2: Category Expenditure Rollup**<br>`JOIN category GROUP BY category_name` | Aggregate / Hash Join | 10.18 ms | Aggregate / Hash Join | 10.66 ms | **1.00×** (CPU-bound) |
| **Q3: Wearable Step Calendar Scan**<br>`WHERE entry_date BETWEEN '2026-05-01' AND '2026-10-25'` | Sort / Seq Scan | 0.17 ms | Index Scan (`idx_activity_date`) | 0.10 ms | **1.80×** |

*Raw execution plans verified and stored in `experiments/results/e4_indexing.log`.*

---

## 7. Automated Test Suite Coverage
EdgeDB includes an automated `unittest` suite (`tests/test_edgedb_suite.py`) providing 100% pass status across 5 system vectors:
1. `test_01_nlp_classifier`: Keyword extraction, categorization accuracy, confidence score bounds ($0.80 \le c \le 1.0$).
2. `test_02_local_store_isolation`: Offline SQLite isolation and monotonic sequence incrementation.
3. `test_03_central_db_connectivity_and_views`: PostgreSQL connection stability and view outputs.
4. `test_04_concurrency_trigger_protection`: Trigger-enforced rejection of stale version overwrites.
5. `test_05_wearable_sensor_discrepancy`: Multi-sensor resolution and hardware priority enforcement.

---

## 8. Contemporary Issues & Industrial Precedents
1. **Architectural Precedents:** EdgeDB implements the synchronization philosophies seen in industrial frameworks such as **PowerSync**, **ElectricSQL**, and **CouchDB/PouchDB**, demonstrating that conflict resolution is most durably enforced inside the database engine itself via stored procedures and triggers.
2. **Data Privacy at the Edge:** By deploying a local NLP classifier directly on the Nothing Phone and Lenovo LOQ, financial descriptions are categorized on-device before transmission, preventing raw personal spending text from exposing behavioral patterns unnecessarily.

---

## 9. Conclusion & Deliverables
EdgeDB successfully demonstrates that edge-cloud architectures can maintain strict ACID guarantees and mathematical consistency without sacrificing disconnected edge availability. 

### Deliverables Checklist (Review 2 & Review 3):
- [x] Normalized PostgreSQL Central Schema (BCNF) with EER Specialization (`sql/central_schema.sql`)
- [x] Concurrency Detection PL/pgSQL Triggers (`sql/triggers.sql`)
- [x] Analytical Views for Real-Time Reporting (`sql/views.sql`)
- [x] Seed Dataset Populating Devices, Categories, and Activity (`sql/seed_data.sql`)
- [x] Edge SQLite Layer (`src/local_store.py`) & On-Device ML Classifier (`src/classifier.py`)
- [x] Transactional Sync Engine with Bidirectional Delta Pull (`src/sync_engine.py`)
- [x] Apple-Inspired Minimalist Web Dashboard (`dashboard/index.html`)
- [x] Experimental Validation Suite E1–E4 with Stored Logs (`experiments/`)
- [x] Automated Unit Test Suite (`tests/test_edgedb_suite.py`)
- [x] Project Execution Launcher (`run.sh`)
- [x] Complete Technical Project Report (`docs/FINAL_PROJECT_REPORT.md`)

