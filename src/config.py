import os

# Central PostgreSQL Configuration
PG_HOST = os.getenv("PG_HOST", "localhost")
PG_PORT = int(os.getenv("PG_PORT", 5432))
PG_DB = os.getenv("PG_DB", "edgedb")
PG_USER = os.getenv("PG_USER", "phase0")
PG_PASSWORD = os.getenv("PG_PASSWORD", "phase0")

# Local Data Directory
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)

# Device Configuration
PHONE_UUID = "phone-nothing-01"
LAPTOP_UUID = "laptop-loq-01"
WATCH_UUID = "watch-cmf-01"

PHONE_SQLITE_PATH = os.path.join(DATA_DIR, "nothing_phone.sqlite")
LAPTOP_SQLITE_PATH = os.path.join(DATA_DIR, "lenovo_loq.sqlite")

