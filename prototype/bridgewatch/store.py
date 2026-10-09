"""
Durable state, in one SQLite file (Python standard library).

  transfers  every token transfer in or out of a monitored vault, stored once
             (primary key: chain + transaction hash + log index), so re-reading a
             block range after a crash or restart never double-counts. Amounts are
             exact token units (amount_raw, text) plus the USD value priced when the
             transfer was ingested, so a restart never reprices history.
  alerts     every alert, keyed by (bridge, rule, started) so rebuilding the
             detector after a restart doesn't duplicate them; holds the
             acknowledged / notification state that people and the notifier change
  meta       the ingest cursor (last fully processed block) and similar values

The detector keeps no state of its own on disk: on start it is rebuilt from the
stored transfers, which makes the transfers table the single source of truth.

Schema versions live in `PRAGMA user_version`. To change the schema, add a
function to MIGRATIONS; an older database is upgraded step by step on open.
"""

from __future__ import annotations
import sqlite3
import threading
from decimal import Decimal
from pathlib import Path

from .models import Alert

SCHEMA_VERSION = 2

TRANSFERS_V2 = """
CREATE TABLE transfers (
  chain TEXT NOT NULL, tx_hash TEXT NOT NULL, log_index INTEGER NOT NULL,
  block_number INTEGER NOT NULL, block_hash TEXT, block_time INTEGER NOT NULL,
  bridge TEXT NOT NULL, vault TEXT NOT NULL DEFAULT '', token TEXT NOT NULL,
  direction TEXT NOT NULL CHECK (direction IN ('in','out')),
  amount_raw TEXT NOT NULL, decimals INTEGER NOT NULL, amount_usd REAL,
  counterparty TEXT NOT NULL,
  source TEXT NOT NULL DEFAULT 'rpc',          -- 'rpc' (live) or 'file:<dataset key>'
  PRIMARY KEY (chain, tx_hash, log_index)
);
CREATE INDEX transfers_bridge_time ON transfers (bridge, block_time);
"""

ALERTS = """
CREATE TABLE IF NOT EXISTS alerts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  bridge TEXT NOT NULL, rule TEXT NOT NULL, severity TEXT NOT NULL,
  started REAL NOT NULL, last_seen REAL NOT NULL, observed REAL NOT NULL, expected REAL NOT NULL,
  message TEXT NOT NULL, worst TEXT NOT NULL DEFAULT '',
  acknowledged INTEGER NOT NULL DEFAULT 0, acknowledged_at REAL,
  notified_severity TEXT NOT NULL DEFAULT '',
  UNIQUE (bridge, rule, started)
);
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
"""

# Columns added to alerts in v2.
ALERT_COLUMNS_V2 = (
    "confirmed_at REAL",                         # block time + confirmations of the triggering transfer
    "detected_at REAL",                          # when BridgeWatch raised it
    "incident TEXT NOT NULL DEFAULT ''",         # alerts of one incident share this; one notification each
    "notify_attempts INTEGER NOT NULL DEFAULT 0",
    "notify_next_at REAL NOT NULL DEFAULT 0",
)
# notified_severity: '' = not sent yet; 'warning' / 'critical' = sent at that level;
# 'historical' = found during the first backfill, never sent; 'failed' = gave up after retries.

# Decimals for databases written by v1, which stored amounts as floats without them.
V1_DECIMALS = {"USDT": 6, "USDC": 6, "DAI": 18, "WBTC": 8}


def _amount_raw(amount: float, decimals: int) -> str:
    return str(int(Decimal(str(amount)) * (Decimal(10) ** decimals)))


def _script(db: sqlite3.Connection, sql: str) -> None:
    # Statement by statement: executescript() would commit the migration's transaction early.
    for stmt in sql.split(";"):
        if stmt.strip():
            db.execute(stmt)


def _create_latest(db: sqlite3.Connection) -> None:
    _script(db, TRANSFERS_V2 + ALERTS)
    for col in ALERT_COLUMNS_V2:
        db.execute(f"ALTER TABLE alerts ADD COLUMN {col}")


def _v1_to_v2(db: sqlite3.Connection) -> None:
    """v1: transfers(tx, log_index, block, ts, bridge, token, direction, amount REAL, counterparty),
    one chain, no USD. Copy into the v2 table; amount_usd stays NULL and is filled at the
    next live start from the current price (what v1 would have used anyway)."""
    db.execute("ALTER TABLE transfers RENAME TO transfers_v1")
    db.execute("DROP INDEX IF EXISTS transfers_ts")
    _script(db, TRANSFERS_V2)
    rows = db.execute("SELECT * FROM transfers_v1").fetchall()
    db.executemany(
        "INSERT OR IGNORE INTO transfers (chain, tx_hash, log_index, block_number, block_time, bridge, token, "
        "direction, amount_raw, decimals, amount_usd, counterparty) VALUES ('ethereum', ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, ?)",
        [(r["tx"], r["log_index"], r["block"], r["ts"], r["bridge"], r["token"], r["direction"],
          _amount_raw(r["amount"], V1_DECIMALS.get(r["token"], 18)), V1_DECIMALS.get(r["token"], 18), r["counterparty"])
         for r in rows])
    db.execute("DROP TABLE transfers_v1")
    for col in ALERT_COLUMNS_V2:
        db.execute(f"ALTER TABLE alerts ADD COLUMN {col}")


MIGRATIONS = {2: _v1_to_v2}   # version reached -> function that gets there from the one before


class Store:
    def __init__(self, path: str | Path):
        self.path = str(path)
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.path, check_same_thread=False, isolation_level=None)
        self.db.row_factory = sqlite3.Row
        self.lock = threading.RLock()
        with self.lock:
            if self.path != ":memory:":
                self.db.execute("PRAGMA journal_mode=WAL")
            self._migrate()

    def _migrate(self) -> None:
        version = self.db.execute("PRAGMA user_version").fetchone()[0]
        has_transfers = self.db.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'transfers'").fetchone()
        self.db.execute("BEGIN")
        try:
            if version == 0 and not has_transfers:       # a new database
                _create_latest(self.db)
                version = SCHEMA_VERSION
            elif version == 0:                            # written by v1, which had no user_version
                version = 1
            for target in sorted(MIGRATIONS):
                if target > version:
                    MIGRATIONS[target](self.db)
                    version = target
            self.db.execute(f"PRAGMA user_version = {version}")
            self.db.execute("COMMIT")
        except Exception:
            self.db.execute("ROLLBACK")
            raise

    @property
    def schema_version(self) -> int:
        with self.lock:
            return self.db.execute("PRAGMA user_version").fetchone()[0]

    # --- meta ---------------------------------------------------------------
    def get(self, key: str, default: str | None = None) -> str | None:
        with self.lock:
            row = self.db.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else default

    def put(self, key: str, value) -> None:
        with self.lock:
            self._put(key, value)

    def _put(self, key: str, value) -> None:
        self.db.execute("INSERT INTO meta (key, value) VALUES (?, ?) "
                        "ON CONFLICT (key) DO UPDATE SET value = excluded.value", (key, str(value)))

    # --- transfers ----------------------------------------------------------
    def add_transfers(self, transfers, cursor: int | None = None, source: str = "rpc",
                      cursor_key: str = "cursor") -> dict[str, int]:
        """Insert transfers (ignoring ones already stored) and, in the same transaction,
        advance the cursor. Returns how many were new, per bridge."""
        new: dict[str, int] = {}
        with self.lock:
            self.db.execute("BEGIN")
            try:
                for t in transfers:
                    cur = self.db.execute(
                        "INSERT OR IGNORE INTO transfers (chain, tx_hash, log_index, block_number, block_hash, block_time, "
                        "bridge, vault, token, direction, amount_raw, decimals, amount_usd, counterparty, source) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (t.chain, t.tx_hash, t.log_index, t.block_number, t.block_hash, t.block_time, t.bridge,
                         t.vault, t.token, t.direction, str(t.amount_raw), t.decimals, t.amount_usd,
                         t.counterparty, source))
                    if cur.rowcount:
                        new[t.bridge] = new.get(t.bridge, 0) + 1
                if cursor is not None:
                    self._put(cursor_key, cursor)
                self.db.execute("COMMIT")
            except Exception:
                self.db.execute("ROLLBACK")
                raise
        return new

    def transfers_since(self, ts: float, bridges: list[str] | None = None) -> list[dict]:
        """Stored transfers with block_time >= ts (optionally only some bridges), in chain order."""
        q, args = "SELECT * FROM transfers WHERE block_time >= ?", [ts]
        if bridges is not None:
            q += f" AND bridge IN ({','.join('?' * len(bridges))})"
            args += list(bridges)
        with self.lock:
            rows = self.db.execute(q + " ORDER BY block_time, block_number, log_index", args).fetchall()
        return [dict(r) for r in rows]

    def fill_missing_usd(self, token: str, price: float) -> int:
        """Price transfers that were stored without a USD value (e.g. migrated from v1)."""
        with self.lock:
            rows = self.db.execute("SELECT chain, tx_hash, log_index, amount_raw, decimals FROM transfers "
                                   "WHERE amount_usd IS NULL AND token = ?", (token,)).fetchall()
            self.db.executemany(
                "UPDATE transfers SET amount_usd = ? WHERE chain = ? AND tx_hash = ? AND log_index = ?",
                [(int(r["amount_raw"]) / 10 ** r["decimals"] * price, r["chain"], r["tx_hash"], r["log_index"])
                 for r in rows])
            return len(rows)

    def transfer_counts(self) -> dict[str, int]:
        """Full count per bridge (a table scan: call it at start-up, not per request)."""
        with self.lock:
            rows = self.db.execute("SELECT bridge, COUNT(*) AS n FROM transfers GROUP BY bridge").fetchall()
        return {r["bridge"]: r["n"] for r in rows}

    def prune(self, before_ts: float, source: str = "rpc") -> int:
        """Retention: delete live-ingested transfers older than before_ts. Imported
        datasets (source 'file:...') and alerts are kept."""
        with self.lock:
            cur = self.db.execute("DELETE FROM transfers WHERE source = ? AND block_time < ?", (source, before_ts))
            return cur.rowcount

    # --- alerts -------------------------------------------------------------
    def upsert_alert(self, a: Alert, historical: bool) -> int:
        """Store a new alert or update the live fields of an existing one. Returns its id.
        detected_at / confirmed_at / incident keep their first values."""
        with self.lock:
            self.db.execute(
                "INSERT INTO alerts (bridge, rule, severity, started, last_seen, observed, expected, message, worst, "
                "notified_severity, confirmed_at, detected_at, incident) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT (bridge, rule, started) DO UPDATE SET "
                "severity = excluded.severity, last_seen = excluded.last_seen, observed = excluded.observed, worst = excluded.worst",
                (a.bridge, a.rule, a.severity, a.started, a.last_seen, a.observed, a.expected, a.message, a.worst,
                 "historical" if historical else "", a.confirmed_at, a.detected_at, a.incident))
            row = self.db.execute("SELECT id FROM alerts WHERE bridge = ? AND rule = ? AND started = ?",
                                  (a.bridge, a.rule, a.started)).fetchone()
            return row["id"]

    def alerts(self, limit: int = 50, bridge: str | None = None, since: float | None = None,
               before_id: int | None = None) -> list[dict]:
        """Newest first (by id). Page with before_id = the last id of the previous page."""
        q, args = "SELECT * FROM alerts WHERE 1 = 1", []
        if bridge:
            q, args = q + " AND bridge = ?", args + [bridge]
        if since is not None:
            q, args = q + " AND started >= ?", args + [since]
        if before_id is not None:
            q, args = q + " AND id < ?", args + [before_id]
        with self.lock:
            rows = self.db.execute(q + " ORDER BY id DESC LIMIT ?", (*args, limit)).fetchall()
        return [_alert_row(r) for r in rows]

    def acknowledge(self, alert_id: int, now: float) -> dict | None:
        with self.lock:
            cur = self.db.execute("UPDATE alerts SET acknowledged = 1, acknowledged_at = ? WHERE id = ?", (now, alert_id))
            if not cur.rowcount:
                return None
            row = self.db.execute("SELECT * FROM alerts WHERE id = ?", (alert_id,)).fetchone()
        return _alert_row(row)

    def pending_notifications(self) -> list[dict]:
        """Alerts never sent, and alerts that became critical after a warning was sent."""
        with self.lock:
            rows = self.db.execute(
                "SELECT * FROM alerts WHERE notified_severity = '' "
                "OR (notified_severity = 'warning' AND severity = 'critical') ORDER BY started, id").fetchall()
        return [_alert_row(r) for r in rows]

    def incident_alerts(self, incident: str) -> list[dict]:
        with self.lock:
            rows = self.db.execute("SELECT * FROM alerts WHERE incident = ? ORDER BY started, id", (incident,)).fetchall()
        return [_alert_row(r) for r in rows]

    def mark_notified(self, alert_ids: list[int], severity: str) -> None:
        with self.lock:
            self.db.executemany("UPDATE alerts SET notified_severity = ?, notify_next_at = 0 WHERE id = ?",
                                [(severity, i) for i in alert_ids])

    def record_attempt(self, alert_ids: list[int], attempts: int, next_at: float) -> None:
        with self.lock:
            self.db.executemany("UPDATE alerts SET notify_attempts = ?, notify_next_at = ? WHERE id = ?",
                                [(attempts, next_at, i) for i in alert_ids])

    def notification_counts(self) -> dict[str, int]:
        with self.lock:
            rows = self.db.execute("SELECT notified_severity AS s, COUNT(*) AS n FROM alerts GROUP BY s").fetchall()
        return {r["s"]: r["n"] for r in rows}

    def alert_counts(self) -> dict[tuple[str, str], int]:
        with self.lock:
            rows = self.db.execute("SELECT bridge, rule, COUNT(*) AS n FROM alerts GROUP BY bridge, rule").fetchall()
        return {(r["bridge"], r["rule"]): r["n"] for r in rows}


def _alert_row(r) -> dict:
    return {**dict(r), "acknowledged": bool(r["acknowledged"])}
