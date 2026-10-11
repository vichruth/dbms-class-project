# PHASE-WISE PLAN
## EdgeDB — Offline-First Expense & Activity Tracker

**Student:** Vichruth M (24BCE2300) · **Course:** Database Management Systems
**Plan version:** 2.0 · **Prepared:** 07 Sep 2026

**Companion documents**
- [PROJECT_PLAN.md](PROJECT_PLAN.md) — architecture, data model, experiment definitions, risks, definition of done
- [projectworkflow.md](projectworkflow.md) — initialization report (problem, motivation, scope rationale, demo script)

---

## How to use this document

Each phase below has: **entry condition**, a **task checklist**, the **artifacts** it produces, an **exit gate** (do not start the next phase until it passes), and a **cut-line** (what to drop first if that phase runs late). Experiment IDs (E1–E5) and milestones (M0–M6) refer to [PROJECT_PLAN.md](PROJECT_PLAN.md).

Every phase also produces a **report fragment** — the corresponding section of `docs/final-report.md`, written while the work is fresh.

---

## Phase rollup

| Phase | Focus | Milestone | Effort |
|---|---|---|---|
| 0 | Design: ER/EER diagrams, both schemas, normalization, strategy choice | M0 | 20% |
| 1 | Edge (local) layer + device simulators | M1 | 8% |
| 2 | Central layer + transactional sync engine | M2 | 15% |
| 3 | **Conflict reproduction and resolution via trigger (centerpiece)** | M3 | 25% |
| 4 | Indexing + views + query optimization | M4 | 15% |
| 5 | Watch integration (Health Connect) | M5 | 7% |
| 6 | ML classifier + dashboard + final report | M6 | 10% |

Phase 3 is the one to protect. If a phase slips, absorb it from Phase 5's window, never from Phase 3's.

---

## Phase 0 — Design

**Entry condition:** none — this is the starting phase.

### Tasks

- [ ] **D0.1** Set up the repo skeleton per [PROJECT_PLAN.md §7](PROJECT_PLAN.md) — `docs/`, `sql/`, `src/`, `watch-client/`, `dashboard/`, `experiments/`, `data/`, `requirements.txt`, `.gitignore` (exclude `data/*.sqlite`). Run `git init` — this project is not yet a git repository, and the before/after evidence in Phase 3 is much easier to trust with a commit history behind it.
- [ ] **D0.2** Install and smoke-test PostgreSQL 15+ on localhost. Record the exact setup method (native vs. Docker) in `docs/final-report.md`.
- [ ] **D0.3** Finalize the entity set: `Device` (+ `PhoneDevice`/`LaptopDevice`/`WatchDevice`), `Category`, `Expense`, `ActivityEntry`, `SyncBatch`, `ConflictLog`. Write one sentence per entity stating what it *is*.
- [ ] **D0.4** Draw the **ER diagram** (plain, no specialization) and the **EER diagram** (with the `Device` specialization) with cardinalities and participation. Export as images for the report; keep the Mermaid source so it's editable when the schema shifts.
- [ ] **D0.5** Write the **local (edge) schema** — flat, append-only `local_expense`, plus `device_meta`. Note explicitly that the watch has no local schema of its own — Health Connect serves that role.
- [ ] **D0.6** Write the **central schema** to BCNF. For each table, list attributes → functional dependencies → candidate keys → the BCNF check.
- [ ] **D0.7** Build the normalization walkthrough in `docs/normalization.md`: start from one deliberately wide table mixing device attributes with readings, then decompose 1NF → 2NF → 3NF → BCNF, naming the violating FD removed at each step.
- [ ] **D0.8** Choose the conflict-resolution strategy: **optimistic versioning enforced by a `BEFORE UPDATE` PL/pgSQL trigger**, plus pessimistic `SELECT … FOR UPDATE` as the comparison arm. Document what was considered and rejected (pure LWW, app-only version checks) and why.
- [ ] **D0.9** Decide how a device timestamp is treated: **untrusted**, with the central `received_at` recorded separately. State the no-shared-clock assumption explicitly.
- [ ] **D0.10** Write `sql/central_schema.sql` and `sql/local_schema.sql` as **idempotent** scripts. They will be re-run dozens of times across Phases 3–4.
- [ ] **D0.11** Load both schemas and insert a handful of rows by hand to confirm every FK/constraint behaves as intended.
- [ ] **Report fragment:** Design section — ER + EER diagrams, both schemas, normalization walkthrough, design-decision table.

### Artifacts
`docs/er-diagram.*`, `docs/eer-diagram.*`, `docs/normalization.md`, `sql/central_schema.sql`, `sql/local_schema.sql`, repo skeleton, report §Design

### Exit gate (M0)
Both schemas load clean from scratch; every central table has a written BCNF justification; the conflict strategy is chosen and documented; the ER/EER diagrams match the SQL exactly.

### Cut-line if late
Drop the wide-table decomposition *narrative* to a single worked table (keep the method visible). Never cut the FD/BCNF justification — it is directly graded.

---

## Phase 1 — Edge (Local) Layer

**Entry condition:** M0 passed — local schema is frozen.

### Tasks

- [ ] **D1.1** `src/config.py` — one place for DB connection settings, device count, event interval, batch size.
- [ ] **D1.2** `src/local_store.py` — open/create a per-device SQLite file under `data/`, append expenses, read unsynced rows, mark a batch synced, allocate `next_batch_seq`.
- [ ] **D1.3** `src/device_sim.py` — phone and laptop simulators: register a `device_uuid`, generate timestamped expenses at an interval, write locally, **never touch the network**.
- [ ] **D1.4** Make a subset of expenses **deliberately overlapping across phone and laptop** (same logical expense edited on both) — this is the hook Phase 3 needs to reproduce a conflict.
- [ ] **D1.5** Wire in the on-device classifier (`src/classifier.py`, stub or trained) — every locally-created expense gets a `category` + `confidence` before being marked ready to sync.
- [ ] **D1.6** **Run E1 (offline-first proof):** stop PostgreSQL. Run both simulators for a fixed interval. Confirm zero errors, all events present locally, nothing synced. Save console output to `experiments/results/e1_offline.log`.
- [ ] **Report fragment:** Edge layer section — local schema rationale, simulator design, E1 evidence.

### Artifacts
`src/config.py`, `src/local_store.py`, `src/device_sim.py`, `src/classifier.py`, `experiments/results/e1_offline.log`, report §Edge Layer

### Exit gate (M1)
E1 passes with the central tier stopped: both simulators run to completion, all events durable locally, nothing lost.

### Cut-line if late
Classifier can start as a rule-based stub (keyword → category) and be upgraded to a trained model in Phase 6 if time allows — do not let it block Phase 2.

---

## Phase 2 — Central Layer + Sync Engine

**Entry condition:** M1 passed — buffered local data exists to sync.

### Tasks

- [ ] **D2.1** `src/central_store.py` — connection handling, device registration, upsert of `expense`/`activity_entry`, `sync_batch` insert, `sync_cursor` maintenance. Explicit transaction control (no autocommit).
- [ ] **D2.2** `src/sync_engine.py` — for one device: read unsynced local rows → build a batch → open a transaction → insert `sync_batch` → merge each row → commit → mark local rows synced only after commit succeeds.
- [ ] **D2.3** Make sync **idempotent**: a re-sent `(device_id, client_batch_seq)` must be detected via the unique constraint and skipped. Test by deliberately re-running the same batch.
- [ ] **D2.4** Add an `--inject-failure-after N` flag that raises mid-batch.
- [ ] **D2.5** **Run E2 (atomicity):** capture row counts, run with failure injection, confirm counts unchanged and local rows still unsynced, then re-run clean and confirm the batch lands exactly once. Save to `experiments/results/e2_atomicity.log`.
- [ ] **D2.6** Sync both devices sequentially (no concurrency yet) and confirm central totals reconcile against local counts — this clean baseline is what Phase 3 will deliberately break.
- [ ] **Report fragment:** Central layer + transactions section — merge algorithm, E2 rollback evidence, ACID mapping.

### Artifacts
`src/central_store.py`, `src/sync_engine.py`, `experiments/results/e2_atomicity.log`, report §Central Layer & Transactions

### Exit gate (M2)
A mid-batch failure leaves the central store byte-for-byte as it was, and the batch can be re-synced afterwards. Sequential sync reconciles exactly.

### Cut-line if late
Skip bounded-batch-size logic (sync each device's full backlog as one batch). Do not cut idempotency or E2 — both are graded evidence.

---

## Phase 3 — Conflict Reproduction and Resolution ⭐ CENTERPIECE

**Entry condition:** M2 passed — sequential sync is correct, so any inconsistency observed here is attributable to concurrency alone.

### Tasks

**Step 1 — build the race**
- [ ] **D3.1** `experiments/exp_conflict_race.py` — phone and laptop both target the same expense with different amounts and close-but-different `event_time`.
- [ ] **D3.2** Launch their syncs **concurrently** (threads/processes) behind a synchronization barrier.
- [ ] **D3.3** Add a configurable delay between read and write inside the merge path to widen the race window reproducibly — state this explicitly in the report as a way to make a real race observable on demand.

**Step 2 — Run A: the failure**
- [ ] **D3.4** Run with the **trigger disabled** and no version check: naive read-modify-write.
- [ ] **D3.5** Capture the lost update: writes issued vs. reflected; the overwritten value; empty `conflict_log`. Save to `experiments/results/e3_run_a_lost_update.log`.
- [ ] **D3.6** Confirm it reproduces on repeat (≥3 of 5 runs).
- [ ] **D3.7** Write the mechanism as an interleaving table (T1 reads v=1 → T2 reads v=1 → T1 writes v=2 → T2 writes v=2, overwriting T1). This explanation is where the marks are.

**Step 3 — Run B: the trigger fix, and Run C: pessimistic locking**
- [ ] **D3.8** Write `sql/triggers.sql`: a `BEFORE UPDATE` PL/pgSQL trigger on `expense` (and `activity_entry`) that checks `NEW.version = OLD.version + 1`-style logic, and on mismatch, inserts a `conflict_log` row (existing value, incoming value, both timestamps, strategy) instead of allowing the blind overwrite.
- [ ] **D3.9** **Unit-test the trigger directly with raw SQL** (two manual `UPDATE`s in separate sessions) before wiring it to the sync engine — isolate trigger bugs from sync-engine bugs.
- [ ] **D3.10** Re-run the race under Run B (trigger enabled). Confirm: no lost update, `conflict_log` populated automatically by the trigger, not by application code. Save to `experiments/results/e3_run_b_trigger.log`.
- [ ] **D3.11** **Run C — pessimistic locking:** `SELECT … FOR UPDATE` on the target row before read-modify-write, implemented in the sync engine as the compared alternative. Confirm the second transaction serializes behind the first; log the observed wait. Save to `experiments/results/e3_run_c_locking.log`.
- [ ] **D3.12** Repeat Runs A/B for an `activity_entry` collision (two overlapping watch/simulated-source syncs for the same day) to show the same trigger mechanism generalizes across data types.

**Step 4 — analysis and evidence**
- [ ] **D3.13** Build the comparison table: A vs. B vs. C on correctness, conflict visibility, latency under contention, implementation complexity.
- [ ] **D3.14** Note the isolation level in use and what `SERIALIZABLE` would change instead.
- [ ] **D3.15** Capture screenshots/terminal transcripts of both the failing and fixed runs.
- [ ] **Report fragment:** Concurrency section — scenario, interleaving table, Run A failure, Runs B/C fixes, trigger source code walkthrough, comparison table.

### Artifacts
`sql/triggers.sql`, `experiments/exp_conflict_race.py`, three result logs (A/B/C) for both expense and activity collisions, comparison table, screenshots, report §Concurrency Control

### Exit gate (M3)
Run A demonstrably loses an update, repeatably. Runs B and C both prevent it, with B additionally producing a `conflict_log` row written by the trigger itself (verified independently of the sync engine). Both data types (expense, activity) shown.

### Cut-line if late
Drop the activity-entry repeat of the race (keep it to expenses only) and shorten Run C. **Never** cut Run A, Run B, or the trigger. If Phase 3 is running late, take the time from Phase 5.

---

## Phase 4 — Indexing, Views & Query Optimization

**Entry condition:** M3 passed; conflict evidence safely captured before bulk-loading.

### Tasks

- [ ] **D4.1** Bulk-generate data: thousands of `expense` and `activity_entry` rows via a burst mode in the simulators. State the chosen scale in the report.
- [ ] **D4.2** Run `ANALYZE` so the planner has current statistics.
- [ ] **D4.3** Write `sql/views.sql`: `category_totals` (sum by category), `activity_daily` (steps by device/day). Point the dashboard at these views, not raw SQL.
- [ ] **D4.4** Write `sql/queries/q1.sql … q4.sql` per [PROJECT_PLAN.md §5 E4](PROJECT_PLAN.md).
- [ ] **D4.5** Capture **before** state: full `EXPLAIN ANALYZE` output, chosen plan, median execution time over ≥5 runs. Note cache state.
- [ ] **D4.6** Write `sql/indexes.sql` with the candidate indexes.
- [ ] **D4.7** Capture **after** state under identical conditions. Fill the results table in PROJECT_PLAN.md §5.
- [ ] **D4.8** Explain *why* each index helped (predicate/sort served, composite column order, index-only scan where applicable).
- [ ] **D4.9** Record one honest non-win if one occurs, and explain why.
- [ ] **D4.10** Note the write-side cost of indexes (insert/merge throughput before vs. after) — directly relevant since the sync path is write-heavy.
- [ ] **Report fragment:** Indexing + views section — queries, plans before/after, timings table, view definitions and their role in the dashboard.

### Artifacts
`sql/indexes.sql`, `sql/views.sql`, `sql/queries/q1–q4.sql`, `experiments/results/e4_explain_before.txt`, `e4_explain_after.txt`, filled results table, report §Indexing

### Exit gate (M4)
Four queries measured before/after with real timings at a stated data scale; both views defined and used by at least one downstream consumer (dashboard or a report query).

### Cut-line if late
Reduce to Q1 and Q3 with full rigour rather than four queries measured sloppily. Keep `ANALYZE` and the views regardless.

---

## Phase 5 — Watch Integration (Health Connect)

**Entry condition:** M4 passed. This phase carries real external-dependency risk (R3) — start it with a fallback already in mind.

### Tasks

- [ ] **D5.1** Confirm the CMF Watch Pro 2's companion app is syncing steps into Google Health Connect (device settings / companion app data-sync menu).
- [ ] **D5.2** Build a minimal Android client (`watch-client/`): request Health Connect read permission for `StepsRecord`, read today's/recent step records.
- [ ] **D5.3** POST the read records to the Flask backend (`src/api.py`) as `ActivityEntry` rows tagged to a `WatchDevice`, using the same batch/idempotency shape as the phone/laptop path.
- [ ] **D5.4** **Run E5:** trigger a live sync from the actual watch, confirm the step count appears in `activity_entry` and matches what the watch/companion app shows. Save to `experiments/results/e5_watch_sync.log`.
- [ ] **D5.5** **Fallback if Health Connect access proves unreliable in the time box (risk R3):** export step history from the CMF companion app (CSV/JSON if supported, or manual transcription for a few days) and feed it through the same ingestion path — document this honestly as "real data, captured via export rather than a live read" rather than presenting it as fully live.
- [ ] **Report fragment:** Watch integration section — Health Connect data path, permission model, E5 evidence (or the documented fallback).

### Artifacts
`watch-client/`, `experiments/results/e5_watch_sync.log`, report §Watch Integration

### Exit gate (M5)
At least one real step-count record, traceable to the physical watch, is visible in the central database — live via Health Connect, or via the documented export fallback.

### Cut-line if late
Fall back to D5.5 immediately rather than spending more than 2 days debugging Health Connect permissions — this phase is 7% of effort and must not eat into Phase 6.

---

## Phase 6 — ML Classifier + Dashboard + Final Report

**Entry condition:** M5 passed (or its fallback); six report fragments already exist from Phases 0–5.

### Tasks

- [ ] **D6.1** If time allows, upgrade the Phase 1 rule-based classifier stub to a small trained model (logistic regression / naive Bayes over expense description text). If not, the rule-based stub is an acceptable, honestly-labeled fallback.
- [ ] **D6.2** Build `src/api.py` (Flask): `GET /expenses`, `GET /totals` (via `category_totals` view), `GET /activity` (via `activity_daily` view), `GET /conflicts`.
- [ ] **D6.3** Build `dashboard/index.html`: expense feed, totals-by-category, activity feed, conflict-log panel — plain HTML/JS `fetch()` calls, no build step.
- [ ] **D6.4** Assemble `docs/final-report.md` from the phase fragments: Title → Problem → Motivation → Objectives → Scope → Architecture → Design (ER/EER + normalization) → Edge Layer → Central Layer & Transactions → Concurrency (centerpiece) → Indexing & Views → Watch Integration → ML Classifier → Dashboard → Contemporary Issues → Limitations → Conclusion.
- [ ] **D6.5** Write the **contemporary issues** section: parallels to Firebase offline persistence, CouchDB/PouchDB replication, and fitness-app sync; a data-privacy subsection on locally-inferred spending categories and step/health data.
- [ ] **D6.6** Write the **limitations** section honestly: simulated phone/laptop, single real device, single-node central store, device clocks untrusted, no auth/multi-user support.
- [ ] **D6.7** Write `docs/syllabus-mapping.md` and reproduce it as a table in the report.
- [ ] **D6.8** Reproducibility check: from a clean state, run schema load → simulate → sync → E1–E5 end to end.
- [ ] **D6.9** Verify the [PROJECT_PLAN.md §13](PROJECT_PLAN.md) definition-of-done checklist item by item.
- [ ] **D6.10** Prepare the demo sequence from [projectworkflow.md — Demo Execution Plan](projectworkflow.md) and rehearse it once end to end, timed.
- [ ] **Report fragment:** ML + Dashboard sections; final assembly of all fragments.

### Artifacts
`src/api.py`, `dashboard/index.html`, `docs/final-report.md` (complete), `docs/syllabus-mapping.md`, reproducibility-verified repo, rehearsed demo script

### Exit gate (M6)
All nine objectives covered in the report; every experiment result traceable to a stored raw output; syllabus mapping table present; demo sequence rehearsed under the target time.

### Cut-line if late
Trim the contemporary-issues section to two platform comparisons instead of three. Never cut the syllabus mapping or the reproducibility check.

---

## Standing rules across all phases

1. **Close each phase with its report fragment.** A phase without its fragment is not finished.
2. **Never overwrite a result log.** Append a run number. Phase 3's evidence is irreplaceable once the database has been bulk-loaded in Phase 4.
3. **Commit after each exit gate**, tagged with the milestone (`M0`…`M6`).
4. **Scripts stay idempotent.**
5. **Frontend stays minimal.** Any drift toward frontend polish is scope creep (risk R4).
6. **Take slack from Phase 5, not Phase 3.** Phase 3 carries the largest share of the marks; Phase 5 has the documented fallback (R3/D5.5) precisely so it never blocks the rest of the timeline.
