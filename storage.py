import json
from pathlib import Path
from datetime import datetime, timezone


DATA_DIR = Path("data")
CONTENT_FILE = DATA_DIR / "content_store.json"
AUDIT_LOG_FILE = DATA_DIR / "audit_log.json"


def ensure_data_files():
    DATA_DIR.mkdir(exist_ok=True)

    if not CONTENT_FILE.exists():
        CONTENT_FILE.write_text("{}")

    if not AUDIT_LOG_FILE.exists():
        AUDIT_LOG_FILE.write_text("[]")


def load_json(path, default):
    ensure_data_files()

    try:
        with open(path, "r") as file:
            return json.load(file)
    except json.JSONDecodeError:
        return default


def save_json(path, data):
    ensure_data_files()

    with open(path, "w") as file:
        json.dump(data, file, indent=2)


def save_content_decision(content_id, decision):
    content_store = load_json(CONTENT_FILE, {})
    content_store[content_id] = decision
    save_json(CONTENT_FILE, content_store)


def get_content_decision(content_id):
    content_store = load_json(CONTENT_FILE, {})
    return content_store.get(content_id)


def update_content_with_appeal(content_id, creator_reasoning):
    content_store = load_json(CONTENT_FILE, {})

    if content_id not in content_store:
        return None

    content_store[content_id]["status"] = "under_review"
    content_store[content_id]["appeal_reasoning"] = creator_reasoning
    content_store[content_id]["appealed_at"] = datetime.now(timezone.utc).isoformat()

    save_json(CONTENT_FILE, content_store)

    return content_store[content_id]


def write_audit_log(entry):
    logs = load_json(AUDIT_LOG_FILE, [])

    entry_with_timestamp = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        **entry
    }

    logs.append(entry_with_timestamp)
    save_json(AUDIT_LOG_FILE, logs)


def get_recent_logs(limit=20):
    logs = load_json(AUDIT_LOG_FILE, [])
    return logs[-limit:]