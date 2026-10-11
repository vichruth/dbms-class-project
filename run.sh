#!/usr/bin/env bash
# EdgeDB: One-command Launcher for Review Evaluation Demo

set -e

echo "=========================================================="
echo "  EdgeDB — Offline-First Relational Sync System"
echo "  Review 1 & Review 2 Evaluation Demo"
echo "=========================================================="

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Check Python dependencies
echo "[1/3] Verifying Python environment..."
python3 -c "import psycopg2, flask; print('Dependencies: OK')"

# Verify PostgreSQL connection and reload schema if requested
echo "[2/3] Checking central PostgreSQL database (edgedb)..."
python3 -c "from src.central_store import CentralStore; c = CentralStore(); print('PostgreSQL Connection: OK (Active)')"

# Start the Web Application
echo "[3/3] Starting Web Dashboard & REST API on http://127.0.0.1:5000 ..."
echo "----------------------------------------------------------"
echo "Open your browser at: http://127.0.0.1:5000"
echo "Press Ctrl+C to stop the server."
echo "----------------------------------------------------------"
python3 -m src.api

