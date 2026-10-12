"""
EdgeDB: Flask Application Backend & REST API (Review 2 Connectivity Layer)
Bridges the web dashboard to PostgreSQL and edge SQLite instances.
"""

import os
from flask import Flask, jsonify, request, send_from_directory
from src.config import BASE_DIR, PHONE_UUID, LAPTOP_UUID, PHONE_SQLITE_PATH, LAPTOP_SQLITE_PATH
from src.central_store import CentralStore
from src.local_store import LocalStore
from src.sync_engine import SyncEngine

app = Flask(__name__, static_folder=os.path.join(BASE_DIR, "dashboard"))
central = CentralStore()
sync_engine = SyncEngine()

phone_store = LocalStore(PHONE_SQLITE_PATH, PHONE_UUID)
laptop_store = LocalStore(LAPTOP_SQLITE_PATH, LAPTOP_UUID)

@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")

@app.route("/api/kpis", methods=["GET"])
def get_kpis():
    try:
        data = central.get_kpis()
        # Also add pending offline counts
        data["phone_pending"] = len(phone_store.get_unsynced())
        data["laptop_pending"] = len(laptop_store.get_unsynced())
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/expenses", methods=["GET"])
def get_expenses():
    try:
        expenses = central.get_recent_expenses(limit=30)
        return jsonify([dict(r) for r in expenses])
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/categories", methods=["GET"])
def get_categories():
    try:
        rows = central.get_category_totals()
        return jsonify([dict(r) for r in rows])
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/activity", methods=["GET"])
def get_activity():
    try:
        rows = central.get_daily_activity()
        return jsonify([dict(r) for r in rows])
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/devices", methods=["GET"])
def get_devices():
    try:
        rows = central.get_device_summary()
        return jsonify([dict(r) for r in rows])
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/conflicts", methods=["GET"])
def get_conflicts():
    try:
        rows = central.get_conflicts()
        return jsonify([dict(r) for r in rows])
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/local-status", methods=["GET"])
def get_local_status():
    return jsonify({
        "phone": {
            "uuid": PHONE_UUID,
            "pending_count": len(phone_store.get_unsynced()),
            "pending_items": phone_store.get_unsynced(),
            "all_items": phone_store.get_all_expenses()[:10]
        },
        "laptop": {
            "uuid": LAPTOP_UUID,
            "pending_count": len(laptop_store.get_unsynced()),
            "pending_items": laptop_store.get_unsynced(),
            "all_items": laptop_store.get_all_expenses()[:10]
        }
    })

@app.route("/api/log-expense", methods=["POST"])
def log_expense():
    """Simulates an edge device user logging an expense while offline."""
    payload = request.json or {}
    device = payload.get("device", "phone")
    amount = float(payload.get("amount", 100))
    description = payload.get("description", "Misc expense")

    target_store = phone_store if device == "phone" else laptop_store
    row_id = target_store.log_expense(amount=amount, description=description)

    return jsonify({
        "status": "LOGGED_OFFLINE",
        "device": device,
        "local_id": row_id,
        "amount": amount,
        "description": description,
        "message": "Expense saved to local SQLite. Central DB unaffected until sync."
    })

@app.route("/api/sync", methods=["POST"])
def trigger_sync():
    """Triggers batch synchronization for a selected device."""
    payload = request.json or {}
    device = payload.get("device", "phone")
    target_store = phone_store if device == "phone" else laptop_store

    try:
        result = sync_engine.sync_device(target_store)
        return jsonify(result)
    except Exception as e:
        return jsonify({"status": "FAILED", "error": str(e)}), 500

@app.route("/api/simulate-conflict", methods=["POST"])
def simulate_conflict():
    """Executes the expense concurrency conflict demonstration."""
    try:
        result = sync_engine.simulate_conflict_demo(expense_id=1)
        return jsonify(result)
    except Exception as e:
        return jsonify({"status": "FAILED", "error": str(e)}), 500

@app.route("/api/simulate-watch-conflict", methods=["POST"])
def simulate_watch_conflict():
    """Executes the wearable watch vs phone sensor step collision demonstration."""
    try:
        result = sync_engine.simulate_watch_conflict_demo()
        return jsonify(result)
    except Exception as e:
        return jsonify({"status": "FAILED", "error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)

