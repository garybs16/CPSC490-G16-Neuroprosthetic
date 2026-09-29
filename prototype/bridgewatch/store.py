"""
Durable state for the live service, in one SQLite file (Python standard library).

  transfers  every token transfer in or out of a monitored vault, stored once
             (primary key: transaction hash + log index), so re-reading a block
             range after a crash or restart never double-counts
  alerts     every alert, keyed by (bridge, rule, started) so rebuilding the
             detector after a restart doesn't duplicate them; holds the
             acknowledged / notified state that people and the notifier change
  meta       the ingest cursor (last fully processed block) and similar values

The detector keeps no state of its own on disk: on start it is rebuilt from
the stored transfers, which makes the transfers table the single source of truth.
"""

from __future__ import annotations
import sqlite3
import threading
from pathlib import Path

from .models import Alert

SCHEMA = """
CREATE TABLE IF NOT EXISTS transfers (
  tx TEXT NOT NULL, log_index INTEGER NOT NULL, block INTEGER NOT NULL, ts INTEGER NOT NULL,
  bridge TEXT NOT NULL, token TEXT NOT NULL, direction TEXT NOT NULL CHECK (direction IN ('in','out')),
  amount REAL NOT NULL, counterparty TEXT NOT NULL,
  PRIMARY KEY (tx, log_index)
);
CREATE INDEX IF NOT EXISTS transfers_ts ON transfers (ts);
CREATE TABLE IF NOT EXISTS alerts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  bridge TEXT NOT NULL, rule TEXT NOT NULL, severity TEXT NOT NULL,
  started REAL NOT NULL, last_seen REAL NOT NULL, observed REAL NOT NULL, expected REAL NOT NULL,
  message TEXT NOT NULL, worst TEXT NOT NULL DEFAULT '',
  acknowledged INTEGER NOT NULL DEFAULT 0, acknowledged_at REAL,
  notified_severity TEXT NOT NULL DEFAULT '',   -- '' = not sent; 'historical' = raised while backfilling, never sent
  UNIQUE (bridge, rule, started)
);
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
"""


class Store:
    def __init__(self, path: str | Path):
        self.path = str(path)
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.path, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.lock = threading.RLock()
        with self.lock:
            if self.path != ":memory:":
                self.db.execute("PRAGMA journal_mode=WAL")
            self.db.executescript(SCHEMA)
            self.db.commit()

    # --- meta ---------------------------------------------------------------
    def get(self, key: str, default: str | None = None) -> str | None:
        with self.lock:
            row = self.db.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else default

    def put(self, key: str, value) -> None:
        with self.lock:
            self.db.execute("INSERT INTO meta (key, value) VALUES (?, ?) "
                            "ON CONFLICT (key) DO UPDATE SET value = excluded.value", (key, str(value)))
            self.db.commit()

    # --- transfers ----------------------------------------------------------
    def add_transfers(self, rows: list[dict], cursor: int | None = None) -> int:
        """Insert transfers (ignoring ones already stored) and, in the same
        transaction, advance the cursor. Returns how many were new."""
        with self.lock:
            before = self.db.total_changes
            self.db.executemany(
                "INSERT OR IGNORE INTO transfers (tx, log_index, block, ts, bridge, token, direction, amount, counterparty) "
                "VALUES (:tx, :log_index, :block, :ts, :bridge, :token, :direction, :amount, :counterparty)", rows)
            new = self.db.total_changes - before
            if cursor is not None:
                self.db.execute("INSERT INTO meta (key, value) VALUES ('cursor', ?) "
                                "ON CONFLICT (key) DO UPDATE SET value = excluded.value", (str(cursor),))
            self.db.commit()
            return new

    def transfers_since(self, ts: float) -> list[dict]:
        with self.lock:
            rows = self.db.execute("SELECT * FROM transfers WHERE ts >= ? ORDER BY block, log_index", (ts,)).fetchall()
        return [dict(r) for r in rows]

    def transfer_counts(self) -> dict[str, int]:
        with self.lock:
            rows = self.db.execute("SELECT bridge, COUNT(*) AS n FROM transfers GROUP BY bridge").fetchall()
        return {r["bridge"]: r["n"] for r in rows}

    # --- alerts -------------------------------------------------------------
    def upsert_alert(self, a: Alert, historical: bool) -> int:
        """Store a new alert or update the live fields of an existing one. Returns its id."""
        with self.lock:
            self.db.execute(
                "INSERT INTO alerts (bridge, rule, severity, started, last_seen, observed, expected, message, worst, notified_severity) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT (bridge, rule, started) DO UPDATE SET "
                "severity = excluded.severity, last_seen = excluded.last_seen, observed = excluded.observed, worst = excluded.worst",
                (a.bridge, a.rule, a.severity, a.started, a.last_seen, a.observed, a.expected, a.message, a.worst,
                 "historical" if historical else ""))
            row = self.db.execute("SELECT id FROM alerts WHERE bridge = ? AND rule = ? AND started = ?",
                                  (a.bridge, a.rule, a.started)).fetchone()
            self.db.commit()
            return row["id"]

    def alerts(self, limit: int = 50, bridge: str | None = None, since: float | None = None) -> list[dict]:
        q, args = "SELECT * FROM alerts WHERE 1 = 1", []
        if bridge:
            q, args = q + " AND bridge = ?", args + [bridge]
        if since is not None:
            q, args = q + " AND started >= ?", args + [since]
        with self.lock:
            rows = self.db.execute(q + " ORDER BY started DESC, id DESC LIMIT ?", (*args, limit)).fetchall()
        return [{**dict(r), "acknowledged": bool(r["acknowledged"])} for r in rows]

    def acknowledge(self, alert_id: int, now: float) -> dict | None:
        with self.lock:
            cur = self.db.execute("UPDATE alerts SET acknowledged = 1, acknowledged_at = ? WHERE id = ?", (now, alert_id))
            self.db.commit()
            if not cur.rowcount:
                return None
            row = self.db.execute("SELECT * FROM alerts WHERE id = ?", (alert_id,)).fetchone()
        return {**dict(row), "acknowledged": True}

    def pending_notifications(self) -> list[dict]:
        """Alerts never sent, and alerts that became critical after a warning was sent."""
        with self.lock:
            rows = self.db.execute(
                "SELECT * FROM alerts WHERE notified_severity = '' "
                "OR (notified_severity = 'warning' AND severity = 'critical') ORDER BY started").fetchall()
        return [dict(r) for r in rows]

    def mark_notified(self, alert_id: int, severity: str) -> None:
        with self.lock:
            self.db.execute("UPDATE alerts SET notified_severity = ? WHERE id = ?", (severity, alert_id))
            self.db.commit()

    def alert_counts(self) -> dict[tuple[str, str], int]:
        with self.lock:
            rows = self.db.execute("SELECT bridge, rule, COUNT(*) AS n FROM alerts GROUP BY bridge, rule").fetchall()
        return {(r["bridge"], r["rule"]): r["n"] for r in rows}
