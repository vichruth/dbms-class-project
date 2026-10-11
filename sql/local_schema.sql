-- ==============================================================================
-- EdgeDB: Edge SQLite Schema (Review 1 DDL - Device Tier)
-- Target: SQLite 3
-- Philosophy: Flat, append-only, zero network overhead, offline-first.
-- ==============================================================================

-- Local staging table for offline expense entries
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

-- Key-value metadata store per device (stores device_uuid, next_batch_seq, last_sync)
CREATE TABLE IF NOT EXISTS device_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

-- Fast lookup for pending unsynced rows during batch formation
CREATE INDEX IF NOT EXISTS idx_local_unsynced ON local_expense(synced, local_id);
