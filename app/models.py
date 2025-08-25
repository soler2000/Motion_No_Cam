import sqlite3
from typing import Dict, Any, Iterable, Tuple, Optional

# Uses DB_PATH from your repo's config.py:
#   DB_PATH = os.environ.get("MOTION_DB", "/opt/Motion_No_Cam/motion.db")
from .config import DB_PATH


# ---------- Connection helper ----------
def get_conn() -> sqlite3.Connection:
    """
    Open a connection to the Motion_No_Cam SQLite database.
    Migrations are run by ExecStartPre, so we don't create tables here.
    """
    # check_same_thread=False lets us reuse the connection from Flask handlers.
    return sqlite3.connect(DB_PATH, timeout=10, check_same_thread=False)


# ---------- Settings key/value API ----------
def kv_get(key: str) -> Optional[str]:
    """
    Return the string value for a setting key, or None if not present.
    """
    with get_conn() as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        row = cur.execute(
            "SELECT value FROM settings WHERE key = ?",
            (key,),
        ).fetchone()
        return row["value"] if row else None


def kv_all() -> Dict[str, str]:
    """
    Return all settings as a dict {key: value}.
    """
    with get_conn() as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        rows = cur.execute("SELECT key, value FROM settings").fetchall()
        return {r["key"]: r["value"] for r in rows}


def kv_set_many(pairs: Dict[str, Any] | Iterable[Tuple[str, Any]]) -> None:
    """
    Upsert many settings at once.

    Accepts either:
      • a dict {key: value}
      • an iterable of (key, value) tuples

    Uses SQLite UPSERT so existing keys are updated.
    """
    # Normalize input to a list of 2-tuples (key, value as str)
    if isinstance(pairs, dict):
        items: Iterable[Tuple[str, Any]] = pairs.items()
    else:
        items = pairs

    normalized: list[Tuple[str, str]] = []
    for k, v in items:
        # Ensure keys are strings and values are stored as strings
        normalized.append((str(k), "" if v is None else str(v)))

    if not normalized:
        return

    with get_conn() as conn:
        cur = conn.cursor()
        # SQLite 3.24+ supports UPSERT (ON CONFLICT ... DO UPDATE)
        cur.executemany(
            """
            INSERT INTO settings (key, value)
            VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            normalized,
        )
        conn.commit()


def kv_set(key: str, value: Any) -> None:
    """
    Convenience single upsert.
    """
    kv_set_many({key: value})
