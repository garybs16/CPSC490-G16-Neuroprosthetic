"""
BridgeWatch API and dashboard. Endpoints and their JSON shapes: prototype/API.md.

Run from prototype/:  python run_bridgewatch.py            (live, real Ethereum data)
                      python run_bridgewatch.py --demo     (synthetic traffic)
Then open http://localhost:8001 (dashboard), /docs (API explorer), /metrics (Prometheus).

Two modes, same detector, same API:
  live  real bridge vaults (bridges.json), polled from public JSON-RPC nodes,
        stored in SQLite, alerts sent to a webhook
  demo  synthetic bridges on a fast simulated clock, with injectable exploits

Settings are environment variables, all read in bridgewatch/config.py.

The API does no heavy work per request: in live mode /api/state is a snapshot
rebuilt after each poll, and the evaluation and replay results are JSON files
written by the command-line tools (python -m bridgewatch.evaluate / .replay).
"""

from __future__ import annotations
import hmac
import json
import logging
import os
import threading
import time
from contextlib import asynccontextmanager
from dataclasses import asdict

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse
from pydantic import BaseModel

from .config import PROTOTYPE_DIR, detector_config, settings_from_env
from .detector import BUCKET, Detector, DetectorConfig
from .synthetic import BRIDGE_BY_ID, INCIDENT_KINDS, SyntheticSource

logging.basicConfig(level=os.getenv("BRIDGEWATCH_LOG_LEVEL", "INFO").upper(),
                    format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)
log = logging.getLogger("bridgewatch")
WEB = PROTOTYPE_DIR / "web" / "bridgewatch.html"
TICK = 1.0   # real seconds between demo simulation steps


# --- demo mode ----------------------------------------------------------------
class Sim:
    """Synthetic source feeding the detector on a fast clock."""

    def __init__(self, seed: int = 7, speed: float = 60.0, cfg: DetectorConfig | None = None):
        self.speed = speed
        self.source = SyntheticSource(seed=seed)
        cfg = cfg or detector_config()
        self.detector = Detector(self.source.bridges, cfg, clock=lambda: self.clock)
        self.history_days = cfg.history_days
        wall = time.time()
        self.clock = wall - wall % BUCKET - self.history_days * 86_400
        self.events = 0

    def step(self, seconds: float) -> None:
        end = self.clock + seconds
        for e in self.source.events_between(self.clock, end):
            self.clock = max(self.clock, e.ts)   # an alert can't be detected before the transfer that trips it
            self.detector.observe(e)
            self.events += 1
        self.detector.advance(end)
        self.clock = end

    def warm_up(self) -> None:
        self.step(self.history_days * 86_400)


def build_state(svc) -> dict:
    """Every bridge's status: escrow, last-hour outflow vs normal, live alerts."""
    with svc.lock:
        now, mons, out = svc.now(), svc.monitors(), []
        for b in svc.bridges():
            m = mons.get(b.id)
            if m is None or now is None:
                continue
            recent = [k for k in [*m.buckets, *([m.bucket] if m.bucket else [])] if k.start >= now - 3_600]
            base = m.baseline(now)
            live = [a for a in svc.alerts(50, b.id) if not a["acknowledged"] and now - a["last_seen"] < svc.cooldown()]
            out.append({
                "id": b.id, "name": b.name, "chains": list(b.chains),
                "escrow_usd": round(m.escrow, 2),
                "outflow_last_hour_usd": round(sum(k.out_usd for k in recent), 2),
                "normal_hour_usd": round(base[0] * 6, 2) if base else None,
                "status": "alert" if live else "learning" if base is None else "ok",
                "worst_severity": ("critical" if any(a["severity"] == "critical" for a in live)
                                   else "warning" if live else None),
                **svc.bridge_extra(b.id),
            })
    return {"mode": svc.mode, "data": "synthetic" if svc.mode == "demo" else "ethereum-mainnet",
            "clock": now, "bridges": out}


class DemoService:
    mode = "demo"

    def __init__(self, sim: Sim):
        self.sim = sim
        self.lock = threading.RLock()

    def bridges(self):
        return self.sim.source.bridges

    def monitors(self):
        return self.sim.detector.monitors

    def now(self) -> float:
        return self.sim.clock

    def cooldown(self) -> float:
        return self.sim.detector.cfg.cooldown

    def history_days(self) -> float:
        return self.sim.history_days

    def alerts(self, limit=50, bridge=None, since=None, before_id=None) -> list[dict]:
        rows = [asdict(a) for a in self.sim.detector.alerts
                if (bridge is None or a.bridge == bridge) and (since is None or a.started >= since)
                and (before_id is None or a.id < before_id)]
        return sorted(rows, key=lambda a: -a["id"])[:limit]

    def ack(self, alert_id: int) -> dict | None:
        for a in self.sim.detector.alerts:
            if a.id == alert_id:
                a.acknowledged = True
                return asdict(a)
        return None

    def bridge_extra(self, bridge_id: str) -> dict:
        return {}

    def state(self) -> dict:
        # In-memory and cheap: computed per request.
        return {**build_state(self), "speed": self.sim.speed, "events_processed": self.sim.events}

    def health(self) -> dict:
        return {"status": "ok", "mode": "demo", "clock": self.sim.clock}


# --- live mode ----------------------------------------------------------------
class LiveService:
    mode = "live"

    def __init__(self, monitor):
        self.m = monitor
        self.lock = monitor.lock
        self.snapshot: dict = {"mode": "live", "data": "ethereum-mainnet", "clock": None, "bridges": []}
        monitor.listeners.append(self.refresh_snapshot)

    def bridges(self):
        return self.m.bridges

    def monitors(self):
        return self.m.detector.monitors if self.m.detector else {}

    def now(self) -> float | None:
        return self.m.now

    def cooldown(self) -> float:
        return self.m.detector_cfg.cooldown

    def history_days(self) -> float:
        return self.m.detector_cfg.history_days

    def alerts(self, limit=50, bridge=None, since=None, before_id=None) -> list[dict]:
        return self.m.store.alerts(limit, bridge, since, before_id)

    def ack(self, alert_id: int) -> dict | None:
        a = self.m.store.acknowledge(alert_id, time.time())
        if a is not None:
            self.refresh_snapshot()
        return a

    def bridge_extra(self, bridge_id: str) -> dict:
        b = self.m.bridge_cfg.get(bridge_id)
        return {"vault": b.vault, "contract": b.contract, "source": b.source, "chain": b.chain} if b else {}

    def refresh_snapshot(self) -> None:
        """Called by the monitor after each poll: the expensive part of /api/state."""
        snap = build_state(self)
        snap["snapshot_at"] = time.time()
        self.snapshot = snap

    def state(self) -> dict:
        s = self.m.status
        lag = (s.head - s.cursor) if s.head is not None and s.cursor is not None else None
        return {**self.snapshot, "explorer_tx": self.m.explorer_tx, "chain": self.m.chain.id,
                "head": s.head, "cursor": s.cursor, "lag_blocks": lag, "phase": s.phase,
                "health": self.m.status_word(), "transfers_stored": sum(self.m.transfer_counts.values())}

    def health(self) -> dict:
        return {"mode": "live", **self.m.health()}


def build_live_service() -> LiveService:
    from .live import LiveMonitor, LiveSettings
    from .notify import Notifier
    from .onchain import LIVE_RPCS
    s = settings_from_env()
    settings = LiveSettings(db_path=s.db_path, chain=s.chain, poll_seconds=s.poll_seconds,
                            confirmations=s.confirmations, rpc_urls=s.rpc_urls or LIVE_RPCS, rpc_pause=s.rpc_pause,
                            registry_path=s.registry_path)
    notifier = Notifier(s.webhook_url, s.webhook_format)
    return LiveService(LiveMonitor(settings, notifier=notifier, detector_cfg=detector_config(s)))


service: DemoService | LiveService | None = None


def get_service():
    global service
    if service is None:
        s = settings_from_env()
        sim = Sim(seed=s.seed, speed=s.speed, cfg=detector_config(s))
        sim.warm_up()
        service = DemoService(sim)
    return service


@asynccontextmanager
async def lifespan(_: FastAPI):
    global service
    stop = threading.Event()
    if settings_from_env().mode == "demo":
        svc = get_service()

        def tick():   # on its own thread, so a slow step never blocks API requests
            while not stop.wait(TICK):
                with svc.lock:
                    svc.sim.step(svc.sim.speed * TICK)
        threading.Thread(target=tick, daemon=True, name="bridgewatch-demo").start()
    else:
        service = build_live_service()
        service.m.notifier.start()
        threading.Thread(target=service.m.run_forever, args=(stop,), daemon=True, name="bridgewatch-live").start()
    log.info("BridgeWatch started in %s mode", service.mode)
    yield
    stop.set()
    if isinstance(service, LiveService):
        service.m.notifier.stop()


app = FastAPI(title="BridgeWatch", version="0.3.0", lifespan=lifespan,
              description="Cross-chain bridge exploit detection (SNX-3 prototype)")


def require_token(request: Request, mode: str) -> None:
    """Acknowledging needs the API token. In live mode it is refused when no token is
    configured (anyone who can reach the port could otherwise silence alerts)."""
    token = settings_from_env().api_token
    if not token:
        if mode == "live":
            raise HTTPException(403, "Acknowledging is disabled: set BRIDGEWATCH_API_TOKEN on the server.")
        return
    given = request.headers.get("authorization", "")
    if not hmac.compare_digest(given.encode(), f"Bearer {token}".encode()):
        raise HTTPException(401, "This action needs the BridgeWatch API token.", headers={"WWW-Authenticate": "Bearer"})


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(WEB)


@app.get("/api/state")
def state():
    """Every bridge's status right now. Live mode: a snapshot rebuilt after each poll."""
    return get_service().state()


@app.get("/api/series/{bridge_id}")
def series(bridge_id: str, hours: int = Query(24, ge=1, le=24 * 30)):
    """10-minute outflow buckets with the learned normal and the alert line, plus alerts in range."""
    svc = get_service()
    hours = min(hours, int(24 * svc.history_days()))
    with svc.lock:
        m = svc.monitors().get(bridge_id)
        if m is None:
            raise HTTPException(404, f"No bridge '{bridge_id}'.")
        since = (svc.now() or 0) - hours * 3_600
        current = [m.bucket] if m.bucket is not None else []
        buckets = [{"t": k.start, "out_usd": round(k.out_usd, 2), "in_usd": round(k.in_usd, 2),
                    "releases": k.out_count, "normal_usd": k.expected_usd and round(k.expected_usd, 2),
                    "alert_line_usd": k.upper_usd and round(k.upper_usd, 2), "partial": k is m.bucket}
                   for k in [*m.buckets, *current] if k.start >= since]
    return {"bridge": bridge_id, "bucket_seconds": BUCKET, "buckets": buckets,
            "alerts": svc.alerts(500, bridge_id, since)}


@app.get("/api/alerts")
def alerts(limit: int = Query(50, ge=1, le=500), before_id: int | None = Query(None, ge=1),
           bridge: str | None = None):
    """Newest first (by id). Next page: before_id = the last id you got."""
    return get_service().alerts(limit, bridge, None, before_id)


@app.post("/api/alerts/{alert_id}/ack")
def acknowledge(alert_id: int, request: Request):
    """A person has looked at this alert. It stays in the log but stops counting as live."""
    svc = get_service()
    require_token(request, svc.mode)
    a = svc.ack(alert_id)
    if a is None:
        raise HTTPException(404, f"No alert {alert_id}.")
    return a


class SimulateRequest(BaseModel):
    bridge: str
    kind: str


@app.post("/api/simulate")
def simulate(req: SimulateRequest):
    """Demo mode only: inject a synthetic exploit starting now on the simulated clock."""
    svc = get_service()
    if svc.mode != "demo":
        raise HTTPException(409, "Simulated exploits exist only in demo mode; live mode watches real bridges.")
    if req.bridge not in BRIDGE_BY_ID:
        raise HTTPException(404, f"No bridge '{req.bridge}'.")
    if req.kind not in INCIDENT_KINDS:
        raise HTTPException(400, f"Unknown exploit kind. Use one of: {', '.join(INCIDENT_KINDS)}.")
    s = svc.sim
    with svc.lock:
        if any(i.bridge == req.bridge and i.end > s.clock for i in s.source.incidents):
            raise HTTPException(409, "An exploit is already running on that bridge.")
        inc = s.source.inject(req.bridge, req.kind, s.clock + 1, escrow_usd=s.detector.monitors[req.bridge].escrow)
    return {"bridge": inc.bridge, "kind": inc.kind, "start": inc.start, "end": inc.end,
            "stolen_usd": round(inc.stolen_usd, 2), "releases": len(inc.events)}


# --- saved results (written by the command-line tools) ----------------------------
RESULT_FILES = {"evaluation": "evaluation.json", "evaluation-real": "evaluation-real.json", "replay": "replay.json"}
RESULT_COMMANDS = {"evaluation": "python -m bridgewatch.evaluate", "evaluation-real": "python -m bridgewatch.evaluate --real",
                   "replay": "python -m bridgewatch.replay"}


def saved_result(name: str) -> dict:
    path = settings_from_env().results_dir / RESULT_FILES[name]
    if not path.exists():
        raise HTTPException(404, f"No saved {name} result. Run `{RESULT_COMMANDS[name]}` from prototype/ to create {path.name}.")
    return json.loads(path.read_text(encoding="utf-8"))


@app.get("/api/evaluation")
def evaluation():
    """Synthetic scorecard, as saved by `python -m bridgewatch.evaluate`. 404 if never run."""
    return saved_result("evaluation")


@app.get("/api/evaluation/real")
def evaluation_real():
    """False alarms per bridge per week on real believed-normal data (`python -m bridgewatch.evaluate --real`)."""
    return saved_result("evaluation-real")


@app.get("/api/replay")
def replay():
    """Every replayed hack case, as saved by `python -m bridgewatch.replay`: {"generated_at", "config", "cases": [...]}."""
    return saved_result("replay")


@app.get("/api/replay/{case_key}")
def replay_case(case_key: str):
    """One replayed hack case (the shape /api/replay had before v0.3)."""
    for case in saved_result("replay")["cases"]:
        if case["key"] == case_key:
            return case
    raise HTTPException(404, f"No replayed case '{case_key}'.")


@app.get("/api/health")
def health():
    """200 when ingesting normally; 503 when degraded (stale, far behind, or failing), for load balancers."""
    h = get_service().health()
    return JSONResponse(h, status_code=200 if h["status"] in ("ok", "starting") else 503)


@app.get("/metrics", include_in_schema=False)
def metrics():
    """Prometheus text format."""
    svc = get_service()
    h = svc.health()
    lines = [f'bridgewatch_up{{mode="{svc.mode}"}} {1 if h["status"] == "ok" else 0}']
    if svc.mode == "live":
        m = svc.m
        lat = h["last_detection_latency_s"]
        lines += [f"bridgewatch_ingest_lag_blocks {h['lag_blocks'] if h['lag_blocks'] is not None else -1}",
                  f"bridgewatch_rpc_calls_total {h['rpc_calls']}",
                  f"bridgewatch_rpc_errors_total {h['rpc_errors']}",
                  f"bridgewatch_consecutive_failures {h['consecutive_failures']}",
                  f"bridgewatch_last_ok_timestamp_seconds {h['last_ok_at'] or 0}",
                  f"bridgewatch_notifications_sent_total {h['notifications']['sent']}",
                  f"bridgewatch_notifications_failed_total {h['notifications']['failed']}",
                  f"bridgewatch_notifications_gave_up_total {h['notifications']['gave_up']}",
                  f"bridgewatch_prices_stale {1 if h['prices_stale'] else 0}",
                  f"bridgewatch_unpriced_transfers_total {h['unpriced_transfers']}",
                  f"bridgewatch_last_detection_latency_seconds {lat if lat is not None else -1}"]
        lines += [f'bridgewatch_transfers_stored{{bridge="{b}"}} {n}' for b, n in m.transfer_counts.items()]
        lines += [f'bridgewatch_alerts_total{{bridge="{b}",rule="{r}"}} {n}' for (b, r), n in m.store.alert_counts().items()]
    with svc.lock:
        lines += [f'bridgewatch_escrow_usd{{bridge="{bid}"}} {mon.escrow:.2f}' for bid, mon in svc.monitors().items()]
    return PlainTextResponse("\n".join(lines) + "\n")
