
import json
import uuid
from .db import get_conn
from datetime import datetime, timezone

def log_payload(direction: str, payload: dict):
    # direction in {'in','out'}
    rec = {
        "log_id": str(uuid.uuid4()),
        "direction": direction,
        "payload_json": json.dumps(payload, ensure_ascii=False),
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO logs(log_id, direction, payload_json, created_at) VALUES(?,?,?,?)",
            (rec["log_id"], rec["direction"], rec["payload_json"], rec["created_at"])
        )
