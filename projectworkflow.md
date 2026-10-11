# PROJECT INITIALIZATION REPORT
## EdgeDB — An Offline-First Expense & Activity Tracker with Conflict-Resilient Sync

**Course:** Database Management Systems
**Student:** Vichruth M (24BCE2300)
**Programme:** B.Tech Computer Science and Engineering, VIT Vellore

---

## 1. TITLE

**EdgeDB: An Offline-First Expense & Activity Tracker with Conflict-Resilient Synchronization, On-Device Categorization, and a Sync Dashboard**

---

## 2. PROBLEM STATEMENT

Most database coursework projects assume a single client always connected to one server — a library system, a hospital record system, a booking app. That model breaks down for something as ordinary as logging an expense on your phone while offline, then editing the same expense later from a laptop before either device has synced — or counting steps on a smartwatch that only reconciles with your phone's own step count once both come online.

Two problems fall out of this that standard single-client coursework rarely engages with:
- Each device must keep working and stay useful **with zero network** — it cannot block a write waiting for a server.
- When two devices that produced independent, possibly conflicting data finally reconnect, the central database must detect the collision and resolve it correctly — silently letting one write overwrite the other (a **lost update**) is a real, well-known correctness bug, not a hypothetical one.

**This project designs, implements, and stress-tests a small database system that solves this problem**, using two simulated devices (a phone and a laptop) for expenses, a **real smartwatch** (CMF Watch Pro 2, via Google Health Connect) for step data, a lightweight on-device model that categorizes each expense before it ever leaves the device, and a small dashboard that makes the sync/conflict story visible.

## 3. MOTIVATION

The author's background is in offline-first, edge-deployed AI systems (a multimodal engagement-detection system on a Raspberry Pi 8GB with no cloud dependency; a semantic video search system built to a 6GB VRAM budget). The recurring question after the ML question is always the database question: once a device produces data offline, how does it get to a central system reliably, and what happens when more than one device produces conflicting data before either has synced?

Expense tracking and step counting are deliberately ordinary, personally lived versions of this problem — everyone has logged the same expense twice on two devices, and anyone with a phone pedometer *and* a smartwatch has seen two different step counts for the same day. Framing the project around real, owned hardware (the author's own CMF Watch Pro 2) rather than a purely simulated fleet keeps the demo concrete, live, and verifiable rather than an abstract IoT-fleet simulation.

## 4. OBJECTIVES

1. Design a normalized relational schema for the central database and a lightweight local schema for each device, including an EER specialization for device types (Phone / Laptop / Watch).
2. Implement offline-first local storage that buffers writes independently of network state.
3. Implement a batch synchronization mechanism that merges device data into the central store **atomically**.
4. Reproduce and then resolve the **lost-update / conflict problem** that occurs when two devices sync conflicting writes to the same record concurrently — for both expenses and activity entries.
5. Enforce conflict detection using a **database trigger** (not just application code), and expose reporting queries through a **database view**.
6. Apply indexing to optimize sync- and reporting-relevant queries, and demonstrate measurable improvement.
7. Add a small on-device ML classifier that categorizes each expense locally, and show how that field is used in the database (schema, query, index).
8. Integrate a real smartwatch (CMF Watch Pro 2) as a genuine third edge device via Google Health Connect, generating real step data that flows through the same sync/conflict pipeline as the simulated devices.
9. Build a minimal web dashboard that shows expenses, activity, categories, sync status, and the conflict log.

## 5. SCOPE

**In scope:**
- 2 simulated devices ("phone" and "laptop"), each with its own local SQLite database, generating and editing expense records independently and offline.
- 1 **real** device — the author's CMF Watch Pro 2 — syncing step data through Google Health Connect into the pipeline, via a small Android client.
- A central PostgreSQL database with a normalized schema, including a PL/pgSQL trigger for conflict detection and a view for reporting.
- A sync/merge engine handling batched uploads, conflict detection, and resolution.
- A small local ML classifier (lightweight, e.g. logistic regression / naive Bayes over expense description text) that assigns a category before sync.
- A minimal web dashboard (single page) showing expenses, activity, categories, totals, sync status, and the conflict log.
- Concurrency and indexing experiments with measured before/after results.

**Out of scope (explicitly, to protect timeline):**
- Real-time Bluetooth access to the watch — data flows through Google Health Connect, the documented and reliable path, not direct BLE reverse-engineering.
- A production-grade or polished UI — a minimal single-page dashboard is sufficient; this remains a database systems project.
- A NoSQL/document store component and the CAP-theorem argument — deliberately dropped from an earlier draft of this project to keep the database core (schema, transactions, concurrency control, indexing) as the dominant share of the work.
- Production-grade security/auth, real payment data, multi-user accounts, or a trained/production ML model — the classifier is intentionally small and is a supporting feature, not the subject of the project.

## 6. WHY THIS DIFFERS FROM EXISTING / TYPICAL DBMS COURSE PROJECTS

Typical course projects (library systems, hospital management, e-commerce/booking systems) assume a single always-connected client and demonstrate normalization and querying against static, centrally-owned data. This project's differentiator is architectural, not cosmetic — the app domain (expense tracking) is intentionally ordinary; the mechanism underneath it is the actual point:

- The central problem is **reconciling multiple independent, disconnected writers**, not serving one client — this surfaces conflict resolution and eventual consistency, topics standard coursework rarely engages with directly.
- The conflict scenario is **reproduced and captured as real database evidence** (logs, `EXPLAIN ANALYZE` output, a `conflict_log` audit trail) rather than described abstractly — most tutorials and even production write-ups on this pattern stop at "use last-write-wins," without demonstrating the failure they're solving.
- Conflict detection is enforced **inside the database itself**, via a trigger, rather than living entirely in application code — a deliberate choice to showcase core DBMS mechanisms (triggers, views) rather than treat Postgres as a dumb store behind a Python script.
- One of the edge devices is **real hardware the author owns** (a CMF Watch Pro 2), not a simulation — the same sync/conflict mechanism is shown working identically for two different kinds of data (expenses, steps) from real and simulated sources alike, which is the strongest evidence that the mechanism generalizes rather than being hardcoded to one scenario.
- The ML and frontend components are **small and load-bearing, not decorative**: the category field the on-device model produces is a real column, used in a real report query and a real index — and the dashboard exists specifically to make the conflict story visible instead of leaving it buried in logs.

## 7. TECHNOLOGY STACK

| Layer | Technology | Justification |
|---|---|---|
| Edge/local storage | SQLite | Lightweight, zero-config, realistic for a constrained/offline device |
| Central relational store | PostgreSQL | Full ACID support, mature indexing, `EXPLAIN ANALYZE`, PL/pgSQL for triggers/views |
| Watch integration | Google Health Connect (Android) + small Android client | Documented, reliable path for CMF Watch Pro 2 step data; direct BLE is unsupported/undocumented |
| On-device classifier | Lightweight Python model (e.g. scikit-learn logistic regression / naive Bayes over expense text) | Small, fast enough to run per-write on a constrained device, honest about being a supporting feature |
| Simulation / sync engine | Python | Device simulation scripts, sync/merge logic, concurrency test harness |
| Dashboard | A minimal single-page web app (Flask backend + plain HTML/JS) | Just enough surface to visualize expenses, activity, sync status, and conflicts — not a product build |

## 8. EXPECTED OUTCOMES / DELIVERABLES

1. ER and EER diagrams and normalized central schema (up to BCNF), with justification.
2. Working local + central database implementation, including a conflict-detection trigger and a reporting view.
3. A sync engine demonstrating atomic, transactional batch merges.
4. A documented, reproduced conflict scenario (concurrent conflicting writes to the same record from two sources) — first showing the failure (lost update), then the fix (locking/versioning via trigger).
5. Indexing benchmark: query performance before vs. after indexing on sync- and reporting-relevant columns, with real measured timings.
6. A working on-device categorization model whose output is stored, queried, and indexed in the database.
7. A working integration with a real CMF Watch Pro 2 via Google Health Connect, feeding real step data through the same pipeline.
8. A minimal dashboard showing expenses, activity, categories, sync status, and the resolved conflict log.
9. Final report covering all of the above.

---

# PROJECT FLOW

## Phase 0 — Design (Week 1)
1. Finalize entities: `Device` (+ subtypes `PhoneDevice`, `LaptopDevice`, `WatchDevice`), `Category`, `LocalExpense`, `Expense` (central), `ActivityEntry`, `SyncBatch`, `ConflictLog`.
2. Draw ER and EER diagrams; define cardinalities and the device specialization (disjoint, total).
3. Design the **local (device) schema** — deliberately simple/flat, optimized for fast local writes.
4. Design the **central schema** — normalized to 3NF/BCNF; walk through functional dependencies explicitly in the report.
5. Decide conflict-resolution strategy: optimistic versioning enforced via a PL/pgSQL trigger, compared against pessimistic `SELECT ... FOR UPDATE` locking.

## Phase 1 — Local (Device) Layer (Week 1–2)
1. Implement local SQLite storage for the phone and laptop simulators.
2. Write device simulation scripts: each device generates and edits timestamped expenses at intervals, entirely independent of network/central state.
3. Wire in the on-device classifier: every locally-created expense gets a `category` + `confidence` before it is marked ready to sync.
4. Confirm devices function correctly with zero connection to the central store (the "offline-first" proof).

## Phase 2 — Central Layer + Sync Engine (Week 2)
1. Implement the normalized PostgreSQL schema.
2. Build the sync/merge engine: batches of local expenses are pulled from a device and inserted centrally.
3. Wrap each batch merge in a **transaction** — demonstrate atomicity by forcing a failure mid-batch and showing full rollback (no partial merge).

## Phase 3 — Conflict Reproduction and Resolution (Week 2–3, the centerpiece)
1. Script a scenario: phone and laptop both edit the **same expense** offline (e.g. correcting the amount) and sync concurrently.
2. **First run without any concurrency control** — capture and document the resulting lost update / inconsistent state.
3. **Then implement the fix as a database trigger** — a `BEFORE UPDATE` PL/pgSQL trigger that checks `version`, rejects/redirects a stale write, and inserts into `ConflictLog` automatically — compared against a pessimistic `SELECT ... FOR UPDATE` alternative implemented in the sync engine.
4. Document both runs with logs/screenshots for the report — this before/after is the strongest demonstrable artifact in the whole project.

## Phase 4 — Indexing, Views & Query Optimization (Week 3)
1. Scale up simulated data (thousands of `Expense`/`ActivityEntry` rows across categories and dates).
2. Run key queries (e.g. "total spent per category," "my unsynced expenses," "steps per day") and capture `EXPLAIN ANALYZE` output.
3. Add appropriate indexes (e.g. composite index on `device_id, event_time`; index on `category_id`).
4. Define a `category_totals` view (and an `activity_daily` view) wrapping the reporting queries, so the dashboard queries a view rather than raw SQL.
5. Re-run the same queries, capture the new query plan and timing, and report the measured improvement.

## Phase 5 — Watch Integration, ML Classifier + Dashboard (Week 3–4)
1. Build the minimal Android client: request Health Connect permission, read step records, POST them to the Flask backend as `ActivityEntry` rows tagged to a `WatchDevice`.
2. Train/fit a small classifier that maps expense description text to a category, running locally per device.
3. Show the classifier's output feeding a real database column, a real report query, and a real index — not sitting inert.
4. Build the minimal dashboard: expense feed with category tags and device origin, activity feed (steps by day/device), a totals-by-category view, and a conflict-log panel showing a resolved conflict before/after.

## Phase 6 — Report, Discussion, and Contemporary Issues (Week 4)
1. Compile ER/EER diagrams, schema, normalization walkthrough, all benchmark results (before/after indexing, before/after concurrency control) into the final report.
2. Contemporary issues section: draw the parallel to real offline-sync systems (Firebase offline persistence, CouchDB/PouchDB replication, mobile budgeting/fitness apps' offline modes), and discuss data-privacy implications of locally-inferred categories and health/activity data.
3. Final review pass: confirm every module topic from the course syllabus is explicitly addressed and labeled in the report.

---

## TIMELINE SUMMARY

| Week | Focus |
|---|---|
| 1 | Design: ER/EER diagrams, local + central schema, normalization walkthrough |
| 2 | Build local layer (with on-device classifier) + central layer + sync engine with transactional merge |
| 3 | Conflict reproduction/resolution (centerpiece, via trigger) + indexing/view benchmarks |
| 4 | Watch integration, dashboard, final report compilation |

---

## DEMO EXECUTION PLAN (final review)

A single live sequence, each step under a minute, run in order:

1. **Offline proof** — stop the central DB. Run the phone/laptop simulators and the watch client (or a captured Health Connect export). Show local SQLite files/Android app populated with zero errors, nothing synced.
2. **Clean sync** — start the central DB, run the sync engine, show all records landing centrally, counts reconciled.
3. **Atomicity** — inject a mid-batch failure, show the batch fully rolled back (no partial merge), re-run clean.
4. **Run A — the bug** — phone and laptop edit the same expense offline, sync concurrently with the trigger disabled/naive path active. Show the lost update: one edit silently overwritten, `conflict_log` empty.
5. **Run B — the fix** — re-enable the trigger, re-run the same race. Show the update correctly rejected/detected (0 rows affected), and a new row appear live in `conflict_log` with both values and the resolution.
6. **Indexing** — run a reporting query on the pre-scaled dataset, show the `EXPLAIN ANALYZE` plan and timing before and after the index exists.
7. **Real watch data** — open the dashboard, show today's step count arriving from the actual CMF Watch Pro 2 via Health Connect, alongside the expense feed and the conflict-log panel.
8. **Close** — one sentence: *"Same mechanism, two data types, one real device — the database catches what a naive server would silently lose."*

---

*Prepared as a project initialization report for faculty review.*
