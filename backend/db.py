"""
Persistenza su SQLite: misure + impostazioni.

Due tabelle:
  results  -> ogni misura (o fallimento)
  settings -> key/value JSON per la configurazione modificabile da UI
"""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

DB_PATH = Path(__file__).parent / "data" / "speedmon.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS results (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    ts            TEXT    NOT NULL,
    engine        TEXT    NOT NULL,
    download_mbps REAL,
    upload_mbps   REAL,
    ping_ms       REAL,
    jitter_ms     REAL,
    packet_loss   REAL,
    server        TEXT,
    server_id     TEXT,
    ok            INTEGER NOT NULL DEFAULT 1,
    error         TEXT
);
CREATE INDEX IF NOT EXISTS idx_results_ts ON results(ts);

CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""

# Impostazioni di default, applicate al primo avvio.
DEFAULT_SETTINGS = {
    "engine": "ookla",
    "interval_min": 60,
    "server_id": None,           # None = automatico
    "contract_download": 1000,   # Mbps promessi dall'ISP
    "thresholds": {"download": 600, "upload": 150, "ping": 60},
    "hourly_bands": [
        {"name": "Notte", "from": "00:00", "to": "07:00", "download_min": 400},
        {"name": "Lavoro", "from": "07:00", "to": "19:00", "download_min": 800},
        {"name": "Sera", "from": "19:00", "to": "23:00", "download_min": 600},
        {"name": "Tarda", "from": "23:00", "to": "00:00", "download_min": 500},
    ],
    "notify": {
        "email": {"enabled": False, "to": "", "smtp_host": "", "smtp_port": 587,
                  "smtp_user": "", "smtp_pass": ""},
        "telegram": {"enabled": False, "bot_token": "", "chat_id": ""},
    },
    "report": {"enabled": False, "frequency": "weekly", "time": "08:00", "to": ""},
}


def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _connect() as conn:
        conn.executescript(SCHEMA)
    # popola i default mancanti senza sovrascrivere quelli gia' salvati
    current = get_settings()
    for k, v in DEFAULT_SETTINGS.items():
        current.setdefault(k, v)
    save_settings(current)


@contextmanager
def _connect():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------- settings
def get_settings() -> dict:
    with _connect() as conn:
        rows = conn.execute("SELECT key, value FROM settings").fetchall()
    return {r["key"]: json.loads(r["value"]) for r in rows}


def save_settings(settings: dict) -> None:
    with _connect() as conn:
        for k, v in settings.items():
            conn.execute(
                "INSERT INTO settings(key, value) VALUES(?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (k, json.dumps(v)),
            )


# ---------------------------------------------------------------- results
def insert_result(result: dict, ok: bool = True, error: str | None = None) -> int:
    ts = datetime.now(timezone.utc).isoformat()
    with _connect() as conn:
        cur = conn.execute(
            """INSERT INTO results
               (ts, engine, download_mbps, upload_mbps, ping_ms, jitter_ms,
                packet_loss, server, server_id, ok, error)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (ts, result.get("engine", "unknown"), result.get("download_mbps"),
             result.get("upload_mbps"), result.get("ping_ms"), result.get("jitter_ms"),
             result.get("packet_loss"), result.get("server"), result.get("server_id"),
             1 if ok else 0, error),
        )
        return cur.lastrowid


def get_results(hours: int | None = None, limit: int = 5000) -> list[dict]:
    query = "SELECT * FROM results"
    params: list = []
    if hours:
        since = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
        query += " WHERE ts >= ?"
        params.append(since)
    query += " ORDER BY ts DESC LIMIT ?"
    params.append(limit)
    with _connect() as conn:
        rows = conn.execute(query, params).fetchall()
    return [dict(r) for r in rows]


def get_stats(hours: int = 24) -> dict:
    since = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    prev_since = (datetime.now(timezone.utc) - timedelta(hours=hours * 2)).isoformat()
    with _connect() as conn:
        agg = conn.execute(_STATS_SQL, (since,)).fetchone()
        prev = conn.execute(_STATS_SQL, (prev_since,)).fetchone()  # finestra precedente inclusa

    total = agg["total"] or 0
    ok = agg["ok_count"] or 0

    def r(v):
        return round(v, 2) if v is not None else None

    # delta % vs periodo precedente (confronto sulle medie download)
    dl_now = agg["avg_down"]
    dl_prev = _prev_only_avg(prev_since, since)
    delta_dl = round((dl_now - dl_prev) / dl_prev * 100, 1) if dl_prev else None

    return {
        "window_hours": hours,
        "total_tests": total,
        "failed_tests": total - ok,
        "uptime_pct": round(ok / total * 100, 1) if total else None,
        "download": {"avg": r(agg["avg_down"]), "min": r(agg["min_down"]), "max": r(agg["max_down"])},
        "upload": {"avg": r(agg["avg_up"]), "min": r(agg["min_up"]), "max": r(agg["max_up"])},
        "ping": {"avg": r(agg["avg_ping"]), "min": r(agg["min_ping"]), "max": r(agg["max_ping"])},
        "delta_download_pct": delta_dl,
    }


_STATS_SQL = """
SELECT COUNT(*) total, SUM(ok) ok_count,
  AVG(CASE WHEN ok=1 THEN download_mbps END) avg_down,
  MAX(CASE WHEN ok=1 THEN download_mbps END) max_down,
  MIN(CASE WHEN ok=1 THEN download_mbps END) min_down,
  AVG(CASE WHEN ok=1 THEN upload_mbps END) avg_up,
  MAX(CASE WHEN ok=1 THEN upload_mbps END) max_up,
  MIN(CASE WHEN ok=1 THEN upload_mbps END) min_up,
  AVG(CASE WHEN ok=1 THEN ping_ms END) avg_ping,
  MIN(CASE WHEN ok=1 THEN ping_ms END) min_ping,
  MAX(CASE WHEN ok=1 THEN ping_ms END) max_ping
FROM results WHERE ts >= ?
"""


def _prev_only_avg(prev_since: str, since: str) -> float | None:
    """Media download della finestra PRECEDENTE soltanto (prev_since <= ts < since)."""
    with _connect() as conn:
        row = conn.execute(
            "SELECT AVG(download_mbps) a FROM results "
            "WHERE ok=1 AND ts >= ? AND ts < ?",
            (prev_since, since),
        ).fetchone()
    return row["a"]


def get_hourly_worst(hours: int = 168) -> list[dict]:
    since = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    with _connect() as conn:
        rows = conn.execute(
            """SELECT CAST(strftime('%H', ts) AS INTEGER) hour,
                      AVG(download_mbps) avg_down, COUNT(*) samples
               FROM results WHERE ok=1 AND ts >= ?
               GROUP BY hour ORDER BY hour""",
            (since,),
        ).fetchall()
    return [{"hour": r["hour"], "avg_down": round(r["avg_down"], 2), "samples": r["samples"]}
            for r in rows]


def get_outages(hours: int = 720) -> list[dict]:
    """Raggruppa test falliti consecutivi in eventi di interruzione."""
    since = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT ts, ok FROM results WHERE ts >= ? ORDER BY ts ASC", (since,)
        ).fetchall()
    outages, start, last, count = [], None, None, 0
    for row in rows:
        if row["ok"] == 0:
            if start is None:
                start = row["ts"]
                count = 0
            last = row["ts"]
            count += 1
        else:
            if start is not None:
                outages.append(_outage(start, last, count))
                start = None
    if start is not None:
        outages.append(_outage(start, last, count))
    return list(reversed(outages))


def _outage(start: str, end: str, count: int) -> dict:
    dt_s = datetime.fromisoformat(start)
    dt_e = datetime.fromisoformat(end)
    return {"from": start, "to": end, "count": count,
            "duration_min": round((dt_e - dt_s).total_seconds() / 60)}
