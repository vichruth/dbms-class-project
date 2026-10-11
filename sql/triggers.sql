-- ==============================================================================
-- EdgeDB: PostgreSQL Concurrency & Conflict Triggers (Review 1 DDL)
-- Target: PostgreSQL 15+
-- Core DBMS Mechanism: PL/pgSQL BEFORE UPDATE triggers enforcing optimistic concurrency
-- and populating conflict_log automatically.
-- ==============================================================================

-- ------------------------------------------------------------------------------
-- 1. Trigger Function for EXPENSE Conflict Detection
-- ------------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION trg_fn_detect_expense_conflict()
RETURNS TRIGGER AS $$
BEGIN
    -- Check if incoming write is stale (optimistic locking violation)
    -- A valid update must present NEW.version = OLD.version + 1
    IF NEW.version <= OLD.version THEN
        -- Log the collision directly into conflict_log
        INSERT INTO conflict_log (
            expense_id,
            conflict_type,
            existing_value,
            incoming_value,
            existing_version,
            incoming_version,
            resolution_strategy,
            resolved_at
        ) VALUES (
            OLD.expense_id,
            'OPTIMISTIC_CONCURRENCY_VIOLATION',
            format('Amount: %s | Description: "%s" | CatID: %s', OLD.amount, OLD.description, OLD.category_id),
            format('Amount: %s | Description: "%s" | CatID: %s', NEW.amount, NEW.description, NEW.category_id),
            OLD.version,
            NEW.version,
            'TRIGGER_REJECTED_STALE_WRITE',
            CURRENT_TIMESTAMP
        );

        -- Preserve the database integrity by rejecting the stale overwrite
        -- Returning OLD ensures no lost update occurs
        RETURN OLD;
    END IF;

    -- Valid concurrent advancement: update timestamp and accept new version
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_expense_conflict ON expense;
CREATE TRIGGER trg_expense_conflict
BEFORE UPDATE ON expense
FOR EACH ROW
EXECUTE FUNCTION trg_fn_detect_expense_conflict();

-- ------------------------------------------------------------------------------
-- 2. Trigger Function for ACTIVITY_ENTRY Conflict Detection
-- ------------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION trg_fn_detect_activity_conflict()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.version <= OLD.version THEN
        INSERT INTO conflict_log (
            activity_id,
            conflict_type,
            existing_value,
            incoming_value,
            existing_version,
            incoming_version,
            resolution_strategy,
            resolved_at
        ) VALUES (
            OLD.activity_id,
            'STALE_ACTIVITY_UPDATE_PREVENTED',
            format('Steps: %s on %s', OLD.step_count, OLD.entry_date),
            format('Steps: %s on %s', NEW.step_count, NEW.entry_date),
            OLD.version,
            NEW.version,
            'TRIGGER_PRESERVED_EXISTING_RECORD',
            CURRENT_TIMESTAMP
        );

        RETURN OLD;
    END IF;

    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_activity_conflict ON activity_entry;
CREATE TRIGGER trg_activity_conflict
BEFORE UPDATE ON activity_entry
FOR EACH ROW
EXECUTE FUNCTION trg_fn_detect_activity_conflict();

