"""
BridgeWatch API and dashboard.

Run from prototype/:  python run_bridgewatch.py            (live, real Ethereum data)
                      python run_bridgewatch.py --demo     (synthetic traffic)
Then open http://localhost:8001 (dashboard), /docs (API explorer), /metrics (Prometheus).

Two modes, same detector, same API:
  live  real bridge vaults on Ethereum mainnet (bridges.json), polled from public
        JSON-RPC nodes, stored in SQLite, alerts sent to a webhook
  demo  synthetic bridges on a fast simulated clock, with injectable exploits

Settings (environment variables, all optional):
  BRIDGEWATCH_MODE             live (default) | demo
  BRIDGEWATCH_DB               SQLite file for live mode (default bridgewatch.db)
  BRIDGEWATCH_RPC_URLS         comma-separated Ethereum JSON-RPC endpoints, tried in order
  BRIDGEWATCH_POLL_SECONDS     default 15
  BRIDGEWATCH_CONFIRMATIONS    blocks a transfer must be buried under before it counts (default 6)
  BRIDGEWATCH_HISTORY_DAYS     baseline window and first-run backfill (default 7)
  BRIDGEWATCH_WEBHOOK_URL      where alerts are POSTed (secret; unset = off)
  BRIDGEWATCH_WEBHOOK_FORMAT   slack (default) | json
  BRIDGEWATCH_API_TOKEN        if set, acknowledging an alert needs "Authorization: Bearer <token>"
  BRIDGEWATCH_SPEED, BRIDGEWATCH_SEED   demo clock speed and random seed
"""

from __future__ import annotations
import asyncio
import hmac
import logging
import os
import threading
import time
from contextlib import asynccontextmanager
from dataclasses import asdict
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse
from pydantic import BaseModel

from .detector import BUCKET, Detector, DetectorConfig
from .evaluate import evaluate
from .replay import ORBIT, run as run_replay
from .synthetic import BRIDGE_BY_ID, INCIDENT_KINDS, SyntheticSource

logging.basicConfig(level=os.getenv("BRIDGEWATCH_LOG_LEVEL", "INFO").upper(),
                    format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)
log = logging.getLogger("bridgewatch")
WEB = Path(__file__).resolve().parent.parent / "web" / "bridgewatch.html"
HISTORY_DAYS = 7
TICK = 1.0   # real seconds between demo simulation steps


# --- demo mode ----------------------------------------------------------------
class Sim:
    """Synthetic source feeding the detector on a fast clock."""

    def __init__(self, seed: int = 7, speed: float = 60.0, cfg: DetectorConfig | None = None):
        self.speed = speed
        self.source = SyntheticSource(seed=seed)
        self.detector = Detector(self.source.bridges, cfg or DetectorConfig())
        wall = time.time()
        self.clock = wall - wall % BUCKET - HISTORY_DAYS * 86_400
        self.events = 0

    def step(self, seconds: float) -> None:
        end = self.clock + seconds
        for e in self.source.events_between(self.clock, end):
            self.detector.observe(e)
            self.events += 1
        self.detector.advance(end)
        self.clock = end

    def warm_up(self) -> None:
        self.step(HISTORY_DAYS * 86_400)


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

    def alerts(self, limit=50, bridge=None, since=None) -> list[dict]:
        rows = [asdict(a) for a in self.sim.detector.alerts
                if (bridge is None or a.bridge == bridge) and (since is None or a.started >= since)]
        return sorted(rows, key=lambda a: -a["started"])[:limit]

    def ack(self, alert_id: int) -> dict | None:
        for a in self.sim.detector.alerts:
            if a.id == alert_id:
                a.acknowledged = True
                return asdict(a)
        return None

    def bridge_extra(self, bridge_id: str) -> dict:
        return {}

    def health(self) -> dict:
        return {"status": "ok", "mode": "demo", "sim_time": self.sim.clock}

    def info(self) -> dict:
        return {"speed": self.sim.speed, "events_processed": self.sim.events}


# --- live mode ----------------------------------------------------------------
class LiveService:
    mode = "live"

    def __init__(self, monitor):
        self.m = monitor
        self.lock = monitor.lock

    def bridges(self):
        return self.m.bridges

    def monitors(self):
        return self.m.detector.monitors if self.m.detector else {}

    def now(self) -> float | None:
        return self.m.now

    def cooldown(self) -> float:
        return self.m.detector_cfg.cooldown

    def alerts(self, limit=50, bridge=None, since=None) -> list[dict]:
        return self.m.store.alerts(limit, bridge, since)

    def ack(self, alert_id: int) -> dict | None:
        return self.m.store.acknowledge(alert_id, time.time())

    def bridge_extra(self, bridge_id: str) -> dict:
        b = self.m.bridge_cfg.get(bridge_id, {})
        return {"vault": b.get("vault"), "contract": b.get("contract"), "source": b.get("source")}

    def health(self) -> dict:
        return {"mode": "live", **self.m.health()}

    def info(self) -> dict:
        h = self.m.health()
        return {"explorer_tx": self.m.explorer_tx, "head": h["head"], "cursor": h["cursor"], "lag_blocks": h["lag_blocks"],
                "phase": h["phase"], "health": h["status"], "transfers_stored": sum(self.m.store.transfer_counts().values())}


def build_live_service() -> LiveService:
    from .live import LiveMonitor, LiveSettings
    from .notify import Notifier
    from .onchain import LIVE_RPCS
    urls = tuple(u.strip() for u in os.getenv("BRIDGEWATCH_RPC_URLS", "").split(",") if u.strip()) or LIVE_RPCS
    settings = LiveSettings(db_path=os.getenv("BRIDGEWATCH_DB", "bridgewatch.db"),
                            poll_seconds=float(os.getenv("BRIDGEWATCH_POLL_SECONDS", "15")),
                            confirmations=int(os.getenv("BRIDGEWATCH_CONFIRMATIONS", "6")),
                            history_days=float(os.getenv("BRIDGEWATCH_HISTORY_DAYS", "7")),
                            rpc_urls=urls)
    notifier = Notifier(os.getenv("BRIDGEWATCH_WEBHOOK_URL") or None, os.getenv("BRIDGEWATCH_WEBHOOK_FORMAT", "slack"))
    return LiveService(LiveMonitor(settings, notifier=notifier))


service: DemoService | LiveService | None = None
scorecard: dict | None = None
_scoring = False
replay_result: dict | None = None


def get_service():
    global service
    if service is None:
        sim = Sim(seed=int(os.getenv("BRIDGEWATCH_SEED", "7")), speed=float(os.getenv("BRIDGEWATCH_SPEED", "60")))
        sim.warm_up()
        service = DemoService(sim)
    return service


@asynccontextmanager
async def lifespan(_: FastAPI):
    global service
    stop = threading.Event()
    tasks = []
    if os.getenv("BRIDGEWATCH_MODE", "live").lower() == "demo":
        svc = get_service()

        async def tick():
            while True:
                await asyncio.sleep(TICK)
                with svc.lock:
                    svc.sim.step(svc.sim.speed * TICK)
        tasks.append(asyncio.create_task(tick()))
    else:
        service = build_live_service()
        threading.Thread(target=service.m.run_forever, args=(stop,), daemon=True, name="bridgewatch-live").start()
    log.info("BridgeWatch started in %s mode", service.mode)
    yield
    stop.set()
    for t in tasks:
        t.cancel()


app = FastAPI(title="BridgeWatch", version="0.2.0", lifespan=lifespan,
              description="Cross-chain bridge exploit detection (SNX-3 prototype)")


def require_token(request: Request) -> None:
    token = os.getenv("BRIDGEWATCH_API_TOKEN")
    if not token:
        return
    given = request.headers.get("authorization", "")
    if not hmac.compare_digest(given.encode(), f"Bearer {token}".encode()):
        raise HTTPException(401, "This action needs the BridgeWatch API token.", headers={"WWW-Authenticate": "Bearer"})


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(WEB)


@app.get("/api/state")
def state():
    """Every bridge's status right now: escrow, last-hour outflow vs normal, live alerts."""
    svc = get_service()
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
            "clock": now, "sim_time": now, "bridges": out, **svc.info()}


@app.get("/api/series/{bridge_id}")
def series(bridge_id: str, hours: int = Query(24, ge=1, le=24 * HISTORY_DAYS)):
    """10-minute outflow buckets with the learned normal and the alert line, plus alerts in range."""
    svc = get_service()
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
def alerts(limit: int = Query(50, ge=1, le=500)):
    return get_service().alerts(limit)


@app.post("/api/alerts/{alert_id}/ack")
def acknowledge(alert_id: int, request: Request):
    """A person has looked at this alert. It stays in the log but stops counting as live."""
    require_token(request)
    a = get_service().ack(alert_id)
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


def _score():
    global scorecard, _scoring
    try:
        scorecard = evaluate()
    finally:
        _scoring = False


@app.get("/api/evaluation")
def evaluation():
    """Synthetic scorecard. Computed on first request (~90 s); until then answers 202 {"status": "running"}."""
    global _scoring
    if scorecard is None:
        if not _scoring:
            _scoring = True
            threading.Thread(target=_score, daemon=True, name="bridgewatch-eval").start()
        return JSONResponse({"status": "running", "detail": "The evaluation is running (about a minute and a half)."},
                            status_code=202)
    return scorecard


@app.get("/api/replay")
def replay():
    """The detector replayed on real on-chain data from the Orbit Chain bridge hack (saved, offline)."""
    global replay_result
    if replay_result is None:
        replay_result = run_replay(ORBIT)
    return replay_result


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
        lines += [f"bridgewatch_ingest_lag_blocks {h['lag_blocks'] if h['lag_blocks'] is not None else -1}",
                  f"bridgewatch_rpc_calls_total {h['rpc_calls']}",
                  f"bridgewatch_rpc_errors_total {h['rpc_errors']}",
                  f"bridgewatch_consecutive_failures {h['consecutive_failures']}",
                  f"bridgewatch_last_ok_timestamp_seconds {h['last_ok_at'] or 0}",
                  f"bridgewatch_notifications_sent_total {h['notifications']['sent']}",
                  f"bridgewatch_notifications_failed_total {h['notifications']['failed']}"]
        lines += [f'bridgewatch_transfers_stored{{bridge="{b}"}} {n}' for b, n in m.store.transfer_counts().items()]
        lines += [f'bridgewatch_alerts_total{{bridge="{b}",rule="{r}"}} {n}' for (b, r), n in m.store.alert_counts().items()]
    with svc.lock:
        lines += [f'bridgewatch_escrow_usd{{bridge="{bid}"}} {mon.escrow:.2f}' for bid, mon in svc.monitors().items()]
    return PlainTextResponse("\n".join(lines) + "\n")
