"""
Live monitoring of real bridge vaults on Ethereum mainnet.

Loop (every BRIDGEWATCH_POLL_SECONDS):
  1. Ask a node for the chain head; only blocks BRIDGEWATCH_CONFIRMATIONS deep
     are processed, so a short chain reorganisation can't produce an alert.
  2. Read every token transfer in or out of the monitored vaults since the
     cursor (two eth_getLogs calls cover all bridges and tokens).
  3. Store them and advance the cursor in one database transaction.
  4. Feed them to the detector; store new or updated alerts; send webhooks.

Start-up and recovery:
  - First run: backfill BRIDGEWATCH_HISTORY_DAYS of transfers so the baseline
    is learned before the first live block.
  - Restart: catch up from the stored cursor, then rebuild the detector from
    stored transfers. Alerts are keyed so the rebuild never duplicates them,
    and alerts older than an hour at the time they are raised are marked
    historical and never notified.
  - Escrow at the start of the window = balance now minus flows since then,
    so no archive-node calls are needed.

Coverage: the ERC-20 tokens in bridges.json. Native ETH (held in separate
portal/bridge contracts) is not covered yet.
"""

from __future__ import annotations
import json
import logging
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

from .detector import Detector, DetectorConfig
from .models import Bridge, FlowEvent
from .notify import Notifier
from .onchain import LIVE_RPCS, TRANSFER_TOPIC, Rpc, _topic
from .store import Store

log = logging.getLogger("bridgewatch.live")
CONFIG = Path(__file__).resolve().parent / "bridges.json"
BLOCKS_PER_DAY = 7_200   # 12-second slots


@dataclass
class LiveSettings:
    db_path: str = "bridgewatch.db"
    poll_seconds: float = 15
    confirmations: int = 6
    history_days: float = 7
    max_blocks_per_poll: int = 2_000
    rpc_urls: tuple[str, ...] = LIVE_RPCS
    config_path: Path = CONFIG
    price_refresh_seconds: float = 600


@dataclass
class TokenCfg:
    symbol: str
    address: str
    decimals: int
    price: dict


@dataclass
class Status:
    phase: str = "starting"          # starting | backfilling | live | error
    started_at: float = field(default_factory=time.time)
    head: int | None = None
    safe_head: int | None = None
    cursor: int | None = None
    last_ok_at: float | None = None
    last_error: str | None = None
    consecutive_failures: int = 0
    transfers_ingested: int = 0


class LiveMonitor:
    def __init__(self, settings: LiveSettings, rpc: Rpc | None = None, store: Store | None = None,
                 notifier: Notifier | None = None, detector_cfg: DetectorConfig | None = None, clock=time.time):
        self.s = settings
        cfg = json.loads(Path(settings.config_path).read_text(encoding="utf-8"))
        self.explorer_tx = cfg.get("explorer_tx", "")
        self.tokens = {t["address"].lower(): TokenCfg(t["symbol"], t["address"].lower(), t["decimals"], t["price"])
                       for t in cfg["tokens"]}
        self.bridge_cfg = {b["id"]: b for b in cfg["bridges"]}
        self.vault_to_bridge = {_topic(b["vault"]): b["id"] for b in cfg["bridges"]}
        self.rpc = rpc or Rpc(settings.rpc_urls)
        self.store = store or Store(settings.db_path)
        self.notifier = notifier or Notifier(None)
        self.detector_cfg = detector_cfg or DetectorConfig()
        self.clock = clock
        self.lock = threading.RLock()
        self.status = Status(started_at=clock())
        self.prices: dict[str, float] = {}
        self._prices_at = 0.0
        self.detector: Detector | None = None
        self.bridges: tuple[Bridge, ...] = ()
        self.now: float | None = None      # timestamp of the last processed block

    # --- prices -------------------------------------------------------------
    def refresh_prices(self, force: bool = False) -> None:
        if not force and self.prices and self.clock() - self._prices_at < self.s.price_refresh_seconds:
            return
        prices = {}
        for t in self.tokens.values():
            if "fixed" in t.price:
                prices[t.symbol] = float(t.price["fixed"])
            else:
                desc, value = self.rpc.chainlink_price(t.price["chainlink"])
                if desc != t.price["expect"]:
                    raise RuntimeError(f"Price feed for {t.symbol} says '{desc}', expected '{t.price['expect']}'.")
                prices[t.symbol] = value
        self.prices, self._prices_at = prices, self.clock()

    # --- ingest -------------------------------------------------------------
    def fetch(self, start: int, end: int) -> list[dict]:
        """All transfers of monitored tokens in or out of monitored vaults, blocks start..end."""
        vaults = list(self.vault_to_bridge)
        tokens = list(self.tokens)
        rows = []
        for direction, topics in (("out", [TRANSFER_TOPIC, vaults]), ("in", [TRANSFER_TOPIC, None, vaults])):
            for lg in self.rpc.logs(tokens, topics, start, end):
                tok = self.tokens.get(lg["address"].lower())
                vault_topic = lg["topics"][1 if direction == "out" else 2].lower()
                bridge = self.vault_to_bridge.get(vault_topic)
                if tok is None or bridge is None or len(lg["topics"]) < 3:
                    continue
                other = lg["topics"][2 if direction == "out" else 1]
                rows.append({"tx": lg["transactionHash"], "log_index": int(lg["logIndex"], 16),
                             "block": int(lg["blockNumber"], 16), "ts": int(lg["ts"]), "bridge": bridge,
                             "token": tok.symbol, "direction": direction,
                             "amount": int(lg["data"], 16) / 10 ** tok.decimals,
                             "counterparty": "0x" + other[-40:]})
        rows.sort(key=lambda r: (r["block"], r["log_index"]))
        return rows

    def _event(self, r: dict) -> FlowEvent:
        return FlowEvent(r["ts"], r["bridge"], r["direction"], r["amount"] * self.prices.get(r["token"], 0.0), r["tx"])

    # --- detector -----------------------------------------------------------
    def rebuild(self) -> None:
        """Recreate the detector from stored transfers (start-up / after catching up)."""
        cursor = int(self.store.get("cursor"))
        window_start = self.rpc.block_time(cursor) - self.s.history_days * 86_400
        rows = self.store.transfers_since(window_start)
        bridges = []
        for bid, b in self.bridge_cfg.items():
            usd = 0.0
            for t in self.tokens.values():
                units = self.rpc.balance_of(t.address, b["vault"], cursor) / 10 ** t.decimals
                flows = sum((r["amount"] if r["direction"] == "out" else -r["amount"])
                            for r in rows if r["bridge"] == bid and r["token"] == t.symbol)
                usd += (units + flows) * self.prices.get(t.symbol, 0.0)   # balance before the window
            bridges.append(Bridge(bid, b["name"], tuple(b["chains"]), max(usd, 0.0)))
        det = Detector(tuple(bridges), self.detector_cfg)
        for m in det.monitors.values():
            m.first_ts = window_start
        for r in rows:
            det.observe(self._event(r))
        det.advance(self.rpc.block_time(cursor))
        with self.lock:
            self.bridges, self.detector, self.now = tuple(bridges), det, self.rpc.block_time(cursor)
            self._persist_alerts(det.alerts)
        log.info("Detector rebuilt from %d stored transfers (%.1f days); %d alerts in window",
                 len(rows), self.s.history_days, len(det.alerts))

    def _persist_alerts(self, alerts) -> None:
        cutoff = self.clock() - 3_600
        for a in alerts:
            a.id = self.store.upsert_alert(a, historical=a.started < cutoff)

    def notify_pending(self) -> None:
        if not self.notifier.enabled:
            return
        for a in self.store.pending_notifications():
            name = self.bridge_cfg.get(a["bridge"], {}).get("name", a["bridge"])
            if self.notifier.send(a, name):
                self.store.mark_notified(a["id"], a["severity"])

    # --- lifecycle ----------------------------------------------------------
    def start(self) -> None:
        """Blocking start-up: prices, backfill or catch-up, rebuild. Run in a thread."""
        self.refresh_prices(force=True)
        head = self.rpc.head()
        safe = head - self.s.confirmations
        history = int(self.s.history_days * BLOCKS_PER_DAY)
        stored = self.store.get("cursor")
        begin = safe - history if stored is None else max(int(stored) + 1, safe - history)
        self.status.phase = "backfilling"
        if begin <= safe:
            log.info("Backfilling blocks %d-%d (%d blocks)", begin, safe, safe - begin + 1)
            rows = self.fetch(begin, safe)
            self.status.transfers_ingested += self.store.add_transfers(rows, cursor=safe)
        self.status.head, self.status.safe_head, self.status.cursor = head, safe, safe
        self.rebuild()
        self.notify_pending()
        self.status.phase = "live"
        self.status.last_ok_at = self.clock()

    def poll(self) -> int:
        """Process newly confirmed blocks. Returns how many transfers were new."""
        self.refresh_prices()
        head = self.rpc.head()
        safe = head - self.s.confirmations
        cursor = int(self.store.get("cursor"))
        self.status.head, self.status.safe_head = head, safe
        if safe <= cursor:
            return 0
        end = min(safe, cursor + self.s.max_blocks_per_poll)
        rows = self.fetch(cursor + 1, end)
        new = self.store.add_transfers(rows, cursor=end)
        end_ts = self.rpc.block_time(end)
        with self.lock:
            det = self.detector
            before = len(det.alerts)
            for r in rows:
                det.observe(self._event(r))
            det.advance(end_ts)
            self.now = end_ts
            touched = det.alerts[before:] + [a for a in det.alerts[:before] if a.last_seen >= end_ts - 3_600]
            self._persist_alerts(touched)
        self.status.cursor = end
        self.status.transfers_ingested += new
        self.notify_pending()
        return new

    def run_forever(self, stop: threading.Event) -> None:
        while not stop.is_set():
            try:
                if self.detector is None:
                    self.start()
                else:
                    self.poll()
                self.status.last_ok_at = self.clock()
                self.status.consecutive_failures = 0
                self.status.last_error = None
                if self.status.phase == "error":
                    self.status.phase = "live"
            except Exception as e:   # keep running: the next poll retries from the stored cursor
                self.status.consecutive_failures += 1
                self.status.last_error = f"{type(e).__name__}: {e}"[:300]
                if self.status.consecutive_failures >= 3:
                    self.status.phase = "error"
                log.exception("Live poll failed (%d in a row)", self.status.consecutive_failures)
            behind = (self.status.safe_head or 0) - (self.status.cursor or 0)
            stop.wait(0 if behind > 0 and self.status.consecutive_failures == 0 else self.s.poll_seconds)

    def health(self) -> dict:
        s = self.status
        lag = (s.head - s.cursor) if s.head is not None and s.cursor is not None else None
        stale = s.last_ok_at is None or self.clock() - s.last_ok_at > max(3 * self.s.poll_seconds, 90)
        ok = s.phase == "live" and not stale and lag is not None and lag <= self.s.confirmations + 50
        return {"status": "ok" if ok else ("starting" if s.phase in ("starting", "backfilling") else "degraded"),
                "phase": s.phase, "head": s.head, "cursor": s.cursor, "lag_blocks": lag,
                "confirmations": self.s.confirmations, "last_ok_at": s.last_ok_at, "last_error": s.last_error,
                "consecutive_failures": s.consecutive_failures, "rpc_calls": self.rpc.calls, "rpc_errors": self.rpc.errors,
                "notifications": {"enabled": self.notifier.enabled, "sent": self.notifier.sent, "failed": self.notifier.failed},
                "prices_usd": self.prices}
