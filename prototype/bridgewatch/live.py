"""
Live monitoring of real bridge vaults (Ethereum mainnet today).

    RpcSource  ->  Detector  ->  Store  ->  alerts  ->  Notifier (own thread) / API snapshot

Each poll (every BRIDGEWATCH_POLL_SECONDS):
  1. The source asks a node for the chain head; only blocks with the chain's
     confirmations (bridges.json, default 6) are read, so a short reorg can't
     produce an alert.
  2. For each batch of blocks: the detector sees the transfers first, THEN the
     store saves them and advances the cursor in one transaction. If anything
     fails in between, the detector is thrown away and rebuilt from the store,
     so a transfer is never stored without having been checked (and never
     checked twice).
  3. New or updated alerts are stored; the notifier thread is woken; the API
     snapshot is rebuilt.

Start-up and recovery:
  - First run: backfill history_days of transfers (committed chunk by chunk, so
    an interrupted backfill resumes) so the baseline is learned before the first
    live block. Alerts in that history are stored as 'historical' and never sent.
  - Restart: catch up from the stored cursor, then rebuild the detector from
    stored transfers. Alerts are keyed so the rebuild never duplicates them;
    ones found while catching up are sent, labelled LATE.
  - Escrow at the start of the window = balance now minus flows since then,
    so no archive-node calls are needed.
  - Prices: USD is fixed per transfer when it is ingested. If a price feed
    fails, the last good price is kept and /api/health flags it stale; a token
    that has never had a price is stored without a USD value and not fed to the
    detector (never priced at $0).

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

from .config import REGISTRY_PATH, detector_config, load_registry
from .detector import Detector, DetectorConfig
from .models import Alert, Bridge
from .notify import Notifier
from .onchain import LIVE_RPCS, Rpc
from .source import Batch, RpcSource, to_flow_event, transfer_from_row
from .store import Store

log = logging.getLogger("bridgewatch.live")


@dataclass
class LiveSettings:
    db_path: str = "bridgewatch.db"
    chain: str = "ethereum"
    poll_seconds: float = 15
    confirmations: int | None = None          # None = the chain's value in bridges.json
    max_blocks_per_poll: int = 2_000
    chunk_blocks: int = 2_000                 # blocks per batch (and per commit while backfilling)
    rpc_urls: tuple[str, ...] = LIVE_RPCS
    rpc_pause: float = 0.3
    registry_path: Path = REGISTRY_PATH
    price_refresh_seconds: float = 600
    price_stale_seconds: float = 2 * 3_600     # Chainlink BTC/USD updates at least hourly
    prune_every_seconds: float = 3_600


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
    unpriced_transfers: int = 0
    last_detection_latency_s: float | None = None


class LiveMonitor:
    def __init__(self, settings: LiveSettings, rpc: Rpc | None = None, store: Store | None = None,
                 notifier: Notifier | None = None, detector_cfg: DetectorConfig | None = None, clock=time.time):
        self.s = settings
        self.registry = load_registry(settings.registry_path)
        self.chain = self.registry.chains[settings.chain]
        self.confirmations = settings.confirmations if settings.confirmations is not None else self.chain.confirmations
        self.explorer_tx = self.chain.explorer_tx
        self.tokens = self.registry.tokens_on(self.chain.id)
        self.bridge_cfg = {b.id: b for b in self.registry.bridges_on(self.chain.id)}
        self.rpc = rpc or Rpc(settings.rpc_urls, pause=settings.rpc_pause)
        self.store = store or Store(settings.db_path)
        self.detector_cfg = detector_cfg or detector_config()
        self.notifier = notifier or Notifier(None)
        self.notifier.attach(self.store, {b.id: b.name for b in self.bridge_cfg.values()})
        self.clock = clock
        self.lock = threading.RLock()
        self.status = Status(started_at=clock())
        self.source = RpcSource(
            self.rpc, self.chain.id, vaults={b.vault: b.id for b in self.bridge_cfg.values()},
            tokens={t.address: (t.symbol, t.decimals) for t in self.tokens}, price=self.price_of,
            confirmations=self.confirmations, block_time_s=self.chain.block_time_s,
            history_days=self.detector_cfg.history_days, chunk_blocks=settings.chunk_blocks)
        self.prices: dict[str, float] = {}
        self.price_info: dict[str, dict] = {}
        self._prices_at = float("-inf")
        self._pruned_at = float("-inf")
        self._dirty = False                  # detector has seen transfers the store hasn't committed
        self.detector: Detector | None = None
        self.bridges: tuple[Bridge, ...] = ()
        self.now: float | None = None        # block time of the last processed block
        self.transfer_counts: dict[str, int] = {}
        self.listeners: list = []            # called after every successful start/poll (the API snapshot)
        self._load_saved_prices()

    @property
    def confirm_seconds(self) -> float:
        return self.confirmations * self.chain.block_time_s

    # --- prices -------------------------------------------------------------
    def _load_saved_prices(self) -> None:
        for t in self.tokens:
            saved = self.store.get(f"price:{t.symbol}")
            if saved:
                info = json.loads(saved)
                self.prices[t.symbol] = info["usd"]
                self.price_info[t.symbol] = {**info, "stale": True, "error": "not refreshed since restart"}

    def price_of(self, symbol: str) -> float | None:
        return self.prices.get(symbol)

    def refresh_prices(self, force: bool = False) -> None:
        """Never raises: a failed feed keeps its last good price and is flagged stale."""
        now = self.clock()
        if not force and now - self._prices_at < self.s.price_refresh_seconds:
            return
        self._prices_at = now
        for t in self.tokens:
            if "fixed" in t.price:
                self.prices[t.symbol] = float(t.price["fixed"])
                self.price_info[t.symbol] = {"usd": self.prices[t.symbol], "updated_at": None, "stale": False, "error": None}
                continue
            try:
                desc, value, updated_at = self.rpc.chainlink_round(t.price["chainlink"])
                if desc != t.price["expect"]:
                    raise RuntimeError(f"feed says '{desc}', expected '{t.price['expect']}'")
                if value <= 0:
                    raise RuntimeError(f"feed answered {value}")
            except Exception as e:   # keep the last good price
                old = self.price_info.get(t.symbol, {})
                self.price_info[t.symbol] = {"usd": self.prices.get(t.symbol), "updated_at": old.get("updated_at"),
                                             "stale": True, "error": f"{type(e).__name__}: {e}"[:200]}
                log.warning("Price for %s not refreshed (%s); %s", t.symbol, e,
                            "keeping the last good price" if t.symbol in self.prices else "no price yet")
                continue
            self.prices[t.symbol] = value
            self.price_info[t.symbol] = {"usd": value, "updated_at": updated_at,
                                         "stale": now - updated_at > self.s.price_stale_seconds, "error": None}
            self.store.put(f"price:{t.symbol}", json.dumps({"usd": value, "updated_at": updated_at}))

    # --- detector -----------------------------------------------------------
    def rebuild(self) -> None:
        """Recreate the detector from stored transfers (start-up, or after a failed poll)."""
        cursor = int(self.store.get("cursor"))
        now_ts = self.rpc.block_time(cursor)
        window_start = now_ts - self.detector_cfg.history_days * 86_400
        for sym, price in self.prices.items():
            filled = self.store.fill_missing_usd(sym, price)   # transfers migrated from schema v1
            if filled:
                log.info("Priced %d stored %s transfers that had no USD value", filled, sym)
        rows = self.store.transfers_since(window_start, list(self.bridge_cfg))
        bridges = []
        for bid, b in self.bridge_cfg.items():
            usd = 0.0
            for t in self.tokens:
                price = self.prices.get(t.symbol)
                if price is None:
                    log.warning("No price for %s: left out of %s escrow", t.symbol, bid)
                    continue
                units = self.rpc.balance_of(t.address, b.vault, cursor) / 10 ** t.decimals
                flows = sum((1 if r["direction"] == "out" else -1) * int(r["amount_raw"]) / 10 ** r["decimals"]
                            for r in rows if r["bridge"] == bid and r["token"] == t.symbol)
                usd += (units + flows) * price   # balance before the window
            bridges.append(Bridge(bid, b.name, b.chains, max(usd, 0.0)))
        det = Detector(tuple(bridges), self.detector_cfg, overrides=self.registry.overrides(), clock=self.clock)
        for m in det.monitors.values():
            m.first_ts = window_start
        for r in rows:
            if r["amount_usd"] is None:
                continue
            det.observe(to_flow_event(transfer_from_row(r), self.confirm_seconds))
        det.advance(now_ts)
        with self.lock:
            self.bridges, self.detector, self.now = tuple(bridges), det, now_ts
            self._persist_alerts(det.alerts, record_latency=False)
            self._dirty = False
        log.info("Detector rebuilt from %d stored transfers (%.1f days); %d alerts in window",
                 len(rows), self.detector_cfg.history_days, len(det.alerts))

    def _persist_alerts(self, alerts, record_latency: bool = True) -> None:
        """Store alerts. rebuild() passes record_latency=False: re-raising old alerts on restart
        stamps them with detected_at = now, which is not a real detection latency."""
        live_since = float(self.store.get("live_since_ts", "0"))
        for a in alerts:
            a.id = self.store.upsert_alert(a, historical=a.started < live_since)
            if (record_latency and a.detected_at is not None and a.confirmed_at is not None
                    and a.started >= live_since):
                self.status.last_detection_latency_s = a.detected_at - a.confirmed_at

    # --- ingest -------------------------------------------------------------
    def _process(self, batch: Batch) -> int:
        """Detector first, then commit (P0-1). Returns how many transfers were new."""
        events = [to_flow_event(t, self.confirm_seconds) for t in batch.transfers]
        unpriced = sum(e is None for e in events)
        with self.lock:
            det = self.detector
            self._dirty = True
            raised: list[Alert] = []
            for e in events:
                if e is not None:
                    raised += det.observe(e)
            det.advance(batch.safe_time)
            new = self.store.add_transfers(batch.transfers, cursor=batch.cursor)
            self.now = batch.safe_time
            # Alerts raised now, plus live ones this batch may have updated (worse peak, critical)
            touched = {id(a): a for a in raised}
            for m in det.monitors.values():
                for a in m.live.values():
                    if a.last_seen >= batch.safe_time - 3_600:
                        touched.setdefault(id(a), a)
            self._persist_alerts(touched.values())
            self._dirty = False
        for bridge, n in new.items():
            self.transfer_counts[bridge] = self.transfer_counts.get(bridge, 0) + n
        self.status.cursor = batch.cursor
        self.status.unpriced_transfers += unpriced
        added = sum(new.values())
        self.status.transfers_ingested += added
        return added

    # --- lifecycle ----------------------------------------------------------
    def start(self) -> None:
        """Blocking start-up: prices, backfill or catch-up, rebuild. Run in a thread."""
        self.refresh_prices(force=True)
        stored = self.store.get("cursor")
        head, safe = self.source.tip()
        if self.store.get("live_since_ts") is None:
            # Anything before this moment is history: stored and shown, never notified.
            since = self.rpc.block_time(safe if stored is None else int(stored))
            self.store.put("live_since_ts", since)
        self.transfer_counts = self.store.transfer_counts()     # the only full count, once per start
        self.status.phase = "backfilling"
        for batch in self.source.batches(None if stored is None else int(stored)):
            new = self.store.add_transfers(batch.transfers, cursor=batch.cursor)   # commit per chunk
            for bridge, n in new.items():
                self.transfer_counts[bridge] = self.transfer_counts.get(bridge, 0) + n
            self.status.transfers_ingested += sum(new.values())
            self.status.cursor = batch.cursor
            log.info("Backfilled to block %d (%d new transfers)", batch.cursor, sum(new.values()))
        if self.store.get("cursor") is None:
            self.store.put("cursor", safe)
        self.status.head, self.status.safe_head = self.source.head, self.source.safe_head
        self.status.cursor = int(self.store.get("cursor"))
        self.rebuild()
        self.notifier.wake()
        self.status.phase = "live"
        self.status.last_ok_at = self.clock()
        self._updated()

    def poll(self) -> int:
        """Process newly confirmed blocks. Returns how many transfers were new."""
        self.refresh_prices()
        cursor = int(self.store.get("cursor"))
        new = 0
        for batch in self.source.batches(cursor, max_blocks=self.s.max_blocks_per_poll):
            new += self._process(batch)
        self.status.head, self.status.safe_head = self.source.head, self.source.safe_head
        if self.clock() - self._pruned_at > self.s.prune_every_seconds and self.now is not None:
            self._pruned_at = self.clock()
            gone = self.store.prune(self.now - (self.detector_cfg.history_days + 1) * 86_400)
            if gone:
                log.info("Retention: pruned %d transfers older than the baseline window", gone)
        self.notifier.wake()
        self._updated()
        return new

    def _updated(self) -> None:
        for fn in self.listeners:
            try:
                fn()
            except Exception:
                log.exception("Snapshot listener failed")

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
                if self._dirty:
                    # The detector saw transfers the store never committed: rebuild it from the store
                    self.detector = None
                    self._dirty = False
                self.status.consecutive_failures += 1
                self.status.last_error = f"{type(e).__name__}: {e}"[:300]
                if self.status.consecutive_failures >= 3:
                    self.status.phase = "error"
                log.exception("Live poll failed (%d in a row)", self.status.consecutive_failures)
            behind = (self.status.safe_head or 0) - (self.status.cursor or 0)
            stop.wait(0 if behind > 0 and self.status.consecutive_failures == 0 else self.s.poll_seconds)

    def status_word(self) -> str:
        """ok | starting | degraded (no database access: cheap enough for every request)."""
        s = self.status
        lag = (s.head - s.cursor) if s.head is not None and s.cursor is not None else None
        stale = s.last_ok_at is None or self.clock() - s.last_ok_at > max(3 * self.s.poll_seconds, 90)
        ok = s.phase == "live" and not stale and lag is not None and lag <= self.confirmations + 50
        return "ok" if ok else ("starting" if s.phase in ("starting", "backfilling") else "degraded")

    def health(self) -> dict:
        s = self.status
        lag = (s.head - s.cursor) if s.head is not None and s.cursor is not None else None
        n = self.store.notification_counts()
        return {"status": self.status_word(),
                "phase": s.phase, "chain": self.chain.id, "head": s.head, "cursor": s.cursor, "lag_blocks": lag,
                "confirmations": self.confirmations, "last_ok_at": s.last_ok_at, "last_error": s.last_error,
                "consecutive_failures": s.consecutive_failures, "rpc_calls": self.rpc.calls, "rpc_errors": self.rpc.errors,
                "notifications": {"enabled": self.notifier.enabled, "sent": self.notifier.sent,
                                  "failed": self.notifier.failed, "gave_up": self.notifier.gave_up,
                                  "pending": n.get("", 0) if self.notifier.enabled else 0},
                "prices_usd": dict(self.prices),
                "prices": self.price_info,
                "prices_stale": any(p.get("stale") for p in self.price_info.values()),
                "unpriced_transfers": s.unpriced_transfers,
                "last_detection_latency_s": s.last_detection_latency_s}

