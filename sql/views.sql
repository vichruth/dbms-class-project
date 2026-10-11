-- ==============================================================================
-- EdgeDB: Analytical & Reporting Views (Review 1 DDL)
-- Target: PostgreSQL 15+
-- Purpose: Encapsulate analytical queries and power the Review 2 web dashboard.
-- ==============================================================================

-- 1. Category Totals View
-- Aggregates total expenditure, item counts, and average spent per category
DROP VIEW IF EXISTS v_category_totals CASCADE;
CREATE VIEW v_category_totals AS
SELECT 
    c.category_id,
    c.category_name,
    c.description AS category_description,
    COALESCE(COUNT(e.expense_id), 0) AS total_transactions,
    COALESCE(SUM(e.amount), 0.00) AS total_amount,
    COALESCE(ROUND(AVG(e.amount), 2), 0.00) AS avg_transaction_amount
FROM category c
LEFT JOIN expense e ON c.category_id = e.category_id
GROUP BY c.category_id, c.category_name, c.description
ORDER BY total_amount DESC;

-- 2. Daily Activity Summary View
-- Wearable physical activity by date, joined with device info
DROP VIEW IF EXISTS v_daily_activity CASCADE;
CREATE VIEW v_daily_activity AS
SELECT 
    a.activity_id,
    d.device_name,
    d.device_type,
    a.entry_date,
    a.step_count,
    a.version,
    a.updated_at
FROM activity_entry a
JOIN device d ON a.device_id = d.device_id
ORDER BY a.entry_date DESC, a.activity_id DESC;

-- 3. Device Sync Status View
-- Overall synchronization health and telemetry per device
DROP VIEW IF EXISTS v_device_sync_summary CASCADE;
CREATE VIEW v_device_sync_summary AS
SELECT 
    d.device_id,
    d.device_uuid,
    d.device_name,
    d.device_type,
    COUNT(DISTINCT sb.batch_id) AS total_sync_batches,
    MAX(sb.client_batch_seq) AS latest_batch_seq,
    MAX(sb.received_at) AS last_sync_time,
    COUNT(DISTINCT e.expense_id) AS total_expenses_synced,
    COUNT(DISTINCT a.activity_id) AS total_activity_days_synced
FROM device d
LEFT JOIN sync_batch sb ON d.device_id = sb.device_id
LEFT JOIN expense e ON d.device_id = e.device_id
LEFT JOIN activity_entry a ON d.device_id = a.device_id
GROUP BY d.device_id, d.device_uuid, d.device_name, d.device_type
ORDER BY d.device_id ASC;

-- 4. Recent Conflicts View
-- Clean view formatting audit trail for the Review 2 frontend
DROP VIEW IF EXISTS v_recent_conflicts CASCADE;
CREATE VIEW v_recent_conflicts AS
SELECT 
    cl.conflict_id,
    cl.conflict_type,
    cl.expense_id,
    cl.activity_id,
    cl.existing_version,
    cl.incoming_version,
    cl.existing_value,
    cl.incoming_value,
    cl.resolution_strategy,
    cl.resolved_at
FROM conflict_log cl
ORDER BY cl.resolved_at DESC;

