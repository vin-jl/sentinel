import logging
import sqlite3
from pathlib import Path

logger = logging.getLogger(__name__)

DB_PATH = Path("/data/telemetry.db")
_SQLITE_TIMEOUT_SECONDS = 5

_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS query_logs (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id          TEXT,
    timestamp           DATETIME DEFAULT CURRENT_TIMESTAMP,
    model_routed_to     TEXT,
    input_tokens        INTEGER,
    pii_entities_masked INTEGER,
    latency_ms          INTEGER
)
"""

_INSERT_LOG_SQL = """
INSERT INTO query_logs (session_id, model_routed_to, input_tokens, pii_entities_masked, latency_ms)
VALUES (?, ?, ?, ?, ?)
"""

# Create the telemetry database and table if it does not exist
def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(str(DB_PATH), timeout=_SQLITE_TIMEOUT_SECONDS) as conn:
        conn.execute(_CREATE_TABLE_SQL)

# Insert a telemetry row using a fresh, thread-safe connection
def log_telemetry(
    session_id: str,
    model_routed_to: str,
    input_tokens: int,
    pii_entities_masked: int,
    latency_ms: int,
) -> None:
    # Called from FastAPI BackgroundTasks so the response is not blocked by database writes
    try:
        with sqlite3.connect(str(DB_PATH), timeout=_SQLITE_TIMEOUT_SECONDS) as conn:
            conn.execute(
                _INSERT_LOG_SQL,
                (session_id, model_routed_to, input_tokens, pii_entities_masked, latency_ms),
            )
    except sqlite3.Error:
        logger.exception("Failed to write telemetry for session %s", session_id)
