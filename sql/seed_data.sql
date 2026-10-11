-- ==============================================================================
-- EdgeDB: Initial Seed Data Population (Review 1 DML)
-- Target: PostgreSQL 15+
-- Realistic data for devices, categories, canonical expenses, and activity.
-- ==============================================================================

-- 1. Populate Categories
INSERT INTO category (category_name, description) VALUES
('Food & Dining', 'Groceries, restaurants, cafes, snacks'),
('Travel & Transit', 'Cab fares, metro, train tickets, fuel'),
('Electronics & Tech', 'Hardware peripherals, cloud hosting, software licenses'),
('Utilities & Bills', 'Electricity, water, mobile and broadband recharge'),
('Health & Fitness', 'Gym memberships, sports gear, medical expenses'),
('Books & Education', 'Academic textbooks, course materials, certifications')
ON CONFLICT (category_name) DO NOTHING;

-- 2. Populate Devices (Supertype + Subtypes)
-- 2.1 Phone Device
INSERT INTO device (device_uuid, device_name, device_type)
VALUES ('phone-pixel-01', 'Google Pixel 8 (Vichruth)', 'PHONE')
ON CONFLICT (device_uuid) DO NOTHING;

INSERT INTO phone_device (device_id, os_version, imei)
SELECT device_id, 'Android 14 (Vanilla Ice Cream)', '864209040001234'
FROM device WHERE device_uuid = 'phone-pixel-01'
ON CONFLICT (device_id) DO NOTHING;

-- 2.2 Laptop Device
INSERT INTO device (device_uuid, device_name, device_type)
VALUES ('laptop-thinkpad-01', 'ThinkPad X1 Carbon (Vichruth)', 'LAPTOP')
ON CONFLICT (device_uuid) DO NOTHING;

INSERT INTO laptop_device (device_id, os_name, mac_address)
SELECT device_id, 'Ubuntu 24.04 LTS', '48:2A:E3:7F:1B:90'
FROM device WHERE device_uuid = 'laptop-thinkpad-01'
ON CONFLICT (device_id) DO NOTHING;

-- 2.3 Watch Device
INSERT INTO device (device_uuid, device_name, device_type)
VALUES ('watch-cmf-01', 'CMF Watch Pro 2 (Dark Grey)', 'WATCH')
ON CONFLICT (device_uuid) DO NOTHING;

INSERT INTO watch_device (device_id, watch_model, firmware_version)
SELECT device_id, 'CMF Watch Pro 2 D398', 'v1.0.0.52'
FROM device WHERE device_uuid = 'watch-cmf-01'
ON CONFLICT (device_id) DO NOTHING;

-- 3. Initial Baseline Sync Batches
INSERT INTO sync_batch (device_id, client_batch_seq, record_count, status)
SELECT device_id, 1, 3, 'COMPLETED' FROM device WHERE device_uuid = 'phone-pixel-01'
ON CONFLICT (device_id, client_batch_seq) DO NOTHING;

INSERT INTO sync_batch (device_id, client_batch_seq, record_count, status)
SELECT device_id, 1, 2, 'COMPLETED' FROM device WHERE device_uuid = 'laptop-thinkpad-01'
ON CONFLICT (device_id, client_batch_seq) DO NOTHING;

INSERT INTO sync_batch (device_id, client_batch_seq, record_count, status)
SELECT device_id, 1, 3, 'COMPLETED' FROM device WHERE device_uuid = 'watch-cmf-01'
ON CONFLICT (device_id, client_batch_seq) DO NOTHING;

-- 4. Initial Baseline Expenses
INSERT INTO expense (device_id, category_id, amount, description, confidence, event_time, version)
SELECT d.device_id, c.category_id, 240.00, 'Blue Tokai Cold Brew Coffee', 0.9850, '2026-10-10 10:15:00+05:30', 1
FROM device d, category c WHERE d.device_uuid = 'phone-pixel-01' AND c.category_name = 'Food & Dining';

INSERT INTO expense (device_id, category_id, amount, description, confidence, event_time, version)
SELECT d.device_id, c.category_id, 420.00, 'Uber auto to Katpadi Junction', 0.9920, '2026-10-10 14:30:00+05:30', 1
FROM device d, category c WHERE d.device_uuid = 'phone-pixel-01' AND c.category_name = 'Travel & Transit';

INSERT INTO expense (device_id, category_id, amount, description, confidence, event_time, version)
SELECT d.device_id, c.category_id, 850.00, 'Database System Concepts (Korth) Book', 0.9600, '2026-10-10 17:45:00+05:30', 1
FROM device d, category c WHERE d.device_uuid = 'phone-pixel-01' AND c.category_name = 'Books & Education';

INSERT INTO expense (device_id, category_id, amount, description, confidence, event_time, version)
SELECT d.device_id, c.category_id, 1100.00, 'GitHub Copilot Monthly Subscription', 0.9950, '2026-10-11 09:00:00+05:30', 1
FROM device d, category c WHERE d.device_uuid = 'laptop-thinkpad-01' AND c.category_name = 'Electronics & Tech';

INSERT INTO expense (device_id, category_id, amount, description, confidence, event_time, version)
SELECT d.device_id, c.category_id, 799.00, 'JioFiber 100Mbps Broadband Bill', 0.9800, '2026-10-11 11:20:00+05:30', 1
FROM device d, category c WHERE d.device_uuid = 'laptop-thinkpad-01' AND c.category_name = 'Utilities & Bills';

-- 5. Initial Physical Wearable Activity Entries
INSERT INTO activity_entry (device_id, entry_date, step_count, version)
SELECT d.device_id, '2026-10-09'::date, 8420, 1
FROM device d WHERE d.device_uuid = 'watch-cmf-01'
ON CONFLICT (device_id, entry_date) DO NOTHING;

INSERT INTO activity_entry (device_id, entry_date, step_count, version)
SELECT d.device_id, '2026-10-10'::date, 10150, 1
FROM device d WHERE d.device_uuid = 'watch-cmf-01'
ON CONFLICT (device_id, entry_date) DO NOTHING;

INSERT INTO activity_entry (device_id, entry_date, step_count, version)
SELECT d.device_id, '2026-10-11'::date, 7890, 1
FROM device d WHERE d.device_uuid = 'watch-cmf-01'
ON CONFLICT (device_id, entry_date) DO NOTHING;
