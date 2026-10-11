-- ==============================================================================
-- EdgeDB: Central PostgreSQL Relational Schema (Review 1 DDL)
-- Target: PostgreSQL 15+
-- Normalization: BCNF
-- Specialization: Enhanced ER (EER) Table-Per-Subtype (Phone, Laptop, Watch)
-- ==============================================================================

-- Drop tables in reverse dependency order for idempotent execution
DROP TABLE IF EXISTS conflict_log CASCADE;
DROP TABLE IF EXISTS expense CASCADE;
DROP TABLE IF EXISTS activity_entry CASCADE;
DROP TABLE IF EXISTS sync_batch CASCADE;
DROP TABLE IF EXISTS phone_device CASCADE;
DROP TABLE IF EXISTS laptop_device CASCADE;
DROP TABLE IF EXISTS watch_device CASCADE;
DROP TABLE IF EXISTS device CASCADE;
DROP TABLE IF EXISTS category CASCADE;

-- ------------------------------------------------------------------------------
-- 1. DEVICE (Supertype)
-- Represents any edge hardware node communicating with the central cluster.
-- ------------------------------------------------------------------------------
CREATE TABLE device (
    device_id SERIAL PRIMARY KEY,
    device_uuid VARCHAR(64) NOT NULL UNIQUE,
    device_name VARCHAR(100) NOT NULL,
    device_type VARCHAR(20) NOT NULL CHECK (device_type IN ('PHONE', 'LAPTOP', 'WATCH')),
    registered_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- ------------------------------------------------------------------------------
-- 1.1 EER Subtypes (Disjoint, Total Specialization)
-- ------------------------------------------------------------------------------
CREATE TABLE phone_device (
    device_id INT PRIMARY KEY REFERENCES device(device_id) ON DELETE CASCADE,
    os_version VARCHAR(50) NOT NULL,
    imei VARCHAR(30)
);

CREATE TABLE laptop_device (
    device_id INT PRIMARY KEY REFERENCES device(device_id) ON DELETE CASCADE,
    os_name VARCHAR(50) NOT NULL,
    mac_address VARCHAR(30)
);

CREATE TABLE watch_device (
    device_id INT PRIMARY KEY REFERENCES device(device_id) ON DELETE CASCADE,
    watch_model VARCHAR(50) NOT NULL,
    firmware_version VARCHAR(30)
);

-- ------------------------------------------------------------------------------
-- 2. CATEGORY (Lookup Entity)
-- Eliminates transitive dependencies from expense to enforce 3NF/BCNF.
-- ------------------------------------------------------------------------------
CREATE TABLE category (
    category_id SERIAL PRIMARY KEY,
    category_name VARCHAR(50) NOT NULL UNIQUE,
    description VARCHAR(255)
);

-- ------------------------------------------------------------------------------
-- 3. SYNC BATCH
-- Unit of atomicity and idempotency for offline batch pushes.
-- Compound unique constraint (device_id, client_batch_seq) blocks replay duplicates.
-- ------------------------------------------------------------------------------
CREATE TABLE sync_batch (
    batch_id SERIAL PRIMARY KEY,
    device_id INT NOT NULL REFERENCES device(device_id) ON DELETE CASCADE,
    client_batch_seq INT NOT NULL,
    received_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    record_count INT NOT NULL DEFAULT 0 CHECK (record_count >= 0),
    status VARCHAR(20) NOT NULL DEFAULT 'COMPLETED' CHECK (status IN ('PENDING', 'COMPLETED', 'FAILED')),
    CONSTRAINT uq_device_client_batch UNIQUE (device_id, client_batch_seq)
);

-- ------------------------------------------------------------------------------
-- 4. EXPENSE (Canonical Relational Store)
-- Incorporates optimistic versioning counter to catch concurrent stale writes.
-- ------------------------------------------------------------------------------
CREATE TABLE expense (
    expense_id SERIAL PRIMARY KEY,
    device_id INT NOT NULL REFERENCES device(device_id) ON DELETE RESTRICT,
    category_id INT NOT NULL REFERENCES category(category_id) ON DELETE RESTRICT,
    amount NUMERIC(12, 2) NOT NULL CHECK (amount > 0),
    description VARCHAR(255) NOT NULL,
    confidence NUMERIC(5, 4) DEFAULT 1.0 CHECK (confidence >= 0.0 AND confidence <= 1.0),
    event_time TIMESTAMP WITH TIME ZONE NOT NULL,
    version INT NOT NULL DEFAULT 1 CHECK (version >= 1),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- ------------------------------------------------------------------------------
-- 5. ACTIVITY ENTRY (Daily Physical Step Count)
-- Populated by smart wearable sync (CMF Watch Pro 2 via Google Health Connect).
-- ------------------------------------------------------------------------------
CREATE TABLE activity_entry (
    activity_id SERIAL PRIMARY KEY,
    device_id INT NOT NULL REFERENCES device(device_id) ON DELETE RESTRICT,
    entry_date DATE NOT NULL,
    step_count INT NOT NULL CHECK (step_count >= 0),
    version INT NOT NULL DEFAULT 1 CHECK (version >= 1),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_device_entry_date UNIQUE (device_id, entry_date)
);

-- ------------------------------------------------------------------------------
-- 6. CONFLICT LOG (Audit Trail for Concurrency Collisions)
-- Directly written by the DBMS trigger when a stale/conflicting update occurs.
-- ------------------------------------------------------------------------------
CREATE TABLE conflict_log (
    conflict_id SERIAL PRIMARY KEY,
    expense_id INT REFERENCES expense(expense_id) ON DELETE SET NULL,
    activity_id INT REFERENCES activity_entry(activity_id) ON DELETE SET NULL,
    batch_id INT REFERENCES sync_batch(batch_id) ON DELETE SET NULL,
    device_id INT REFERENCES device(device_id) ON DELETE SET NULL,
    conflict_type VARCHAR(40) NOT NULL,
    existing_value TEXT NOT NULL,
    incoming_value TEXT NOT NULL,
    existing_version INT NOT NULL,
    incoming_version INT NOT NULL,
    resolution_strategy VARCHAR(50) NOT NULL,
    resolved_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- ------------------------------------------------------------------------------
-- Indexes for Performance & Query Optimization
-- ------------------------------------------------------------------------------
CREATE INDEX idx_expense_device_event ON expense(device_id, event_time DESC);
CREATE INDEX idx_expense_category ON expense(category_id);
CREATE INDEX idx_activity_date ON activity_entry(entry_date DESC);
CREATE INDEX idx_sync_batch_device ON sync_batch(device_id, client_batch_seq);

