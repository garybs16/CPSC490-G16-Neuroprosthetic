"""Live-mode tests for BridgeWatch, all offline: a fake Ethereum node, a
temporary SQLite database, and a mocked webhook."""
import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx  # noqa: E402
import pytest  # noqa: E402

from bridgewatch.detector import DetectorConfig  # noqa: E402
from bridgewatch.live import LiveMonitor, LiveSettings  # noqa: E402
from bridgewatch.notify import Notifier  # noqa: E402
from bridgewatch.onchain import TRANSFER_TOPIC, _topic  # noqa: E402
from bridgewatch.store import Store  # noqa: E402

CFG = Path(__file__).resolve().parents[1] / "bridgewatch" / "bridges.json"
USDT = "0xdac17f958d2ee523a2206206994597c13d831ec7"
WBTC = "0x2260fac5e5542a773aa44fbcfedf7c193bc2c599"
OP_VAULT = "0x99C9fc46f92E8a1c0deC1b1747d010903E884bE1"
GENESIS_TS = 1_790_000_000
BPD = 7_200   # blocks per day


class FakeChain:
    """Just enough of an Ethereum node for LiveMonitor: a block every 12 s, token logs, balances."""

    def __init__(self, head: int):
        self.head_block = head
        self.entries: list[dict] = []
        self.balances = {(USDT, OP_VAULT.lower()): 300_000_000 * 10**6}
        self.calls = self.errors = 0
        self.fail_next = 0
        self.fail_block_time = 0
        self.fail_price = False
        self._n = 0

    def ts(self, block: int) -> int:
        return GENESIS_TS + block * 12

    def transfer(self, block: int, token: str, frm: str, to: str, amount_units: int):
        self._n += 1
        self.entries.append({"address": token, "blockNumber": hex(block), "logIndex": hex(self._n % 500),
                          "transactionHash": f"0x{self._n:064x}", "data": hex(amount_units),
                          "topics": [TRANSFER_TOPIC, _topic(frm), _topic(to)], "ts": self.ts(block)})

    # --- the Rpc methods LiveMonitor uses ---
    def head(self):
        self.calls += 1
        if self.fail_next:
            self.fail_next -= 1
            self.errors += 1
            raise RuntimeError("node unreachable")
        return self.head_block

    def block_time(self, block):
        if self.fail_block_time:
            self.fail_block_time -= 1
            raise RuntimeError("timeout reading block")
        return self.ts(block)

    def balance_of(self, token, holder, block):
        return self.balances.get((token.lower(), holder.lower()), 0)

    def chainlink_round(self, feed, block="latest"):
        if self.fail_price:
            raise RuntimeError("feed unreachable")
        return "BTC / USD", 60_000.0, self.ts(self.head_block)

    def logs(self, addresses, topics, start, end, chunk=5_000):
        def match(i, t, lg):
            if t is None:
                return True
            want = [x.lower() for x in t] if isinstance(t, list) else [t.lower()]
            return lg["topics"][i].lower() in want
        return [dict(lg) for lg in self.entries
                if start <= int(lg["blockNumber"], 16) <= end and lg["address"] in addresses
                and all(match(i, t, lg) for i, t in enumerate(topics))]


def user(i):
    return "0x" + f"{i:040x}"


def seed_history(chain, start_block, days, per_day=40, amount=50_000):
    """Regular deposits, and a smaller number of releases, on the OP vault."""
    step = BPD // per_day
    for k in range(int(days * per_day)):
        b = start_block + k * step
        chain.transfer(b, USDT, user(k + 1), OP_VAULT, amount * 10**6)
        if k % 4 == 0:
            chain.transfer(b + 1, USDT, OP_VAULT, user(k + 1), amount * 10**6)


@pytest.fixture
def setup(tmp_path):
    chain = FakeChain(10 * BPD)
    seed_history(chain, chain.head_block - 8 * BPD, 8)
    sent = []
    hook = Notifier("https://hooks.example/test", "slack",
                    client=httpx.Client(transport=httpx.MockTransport(lambda r: sent.append(r) or httpx.Response(200))))

    def make():
        settings = LiveSettings(db_path=str(tmp_path / "bw.db"), confirmations=6, registry_path=CFG)
        return LiveMonitor(settings, rpc=chain, store=Store(settings.db_path), notifier=hook,
                           detector_cfg=DetectorConfig(history_days=7), clock=lambda: chain.ts(chain.head_block))
    return chain, make, sent


def drain(chain, block, amount_usd=40_000_000, to=999):
    chain.transfer(block, USDT, OP_VAULT, user(to), amount_usd * 10**6)


def test_first_start_backfills_and_learns_a_baseline(setup):
    chain, make, sent = setup
    m = make()
    m.start()
    assert m.status.phase == "live" and m.status.cursor == chain.head_block - 6
    assert m.store.transfer_counts()["optimism"] > 100
    mon = m.detector.monitors["optimism"]
    assert 290e6 < mon.escrow < 310e6                 # escrow reconstructed from balance and flows
    assert mon.baseline(m.now) is not None             # 7 days learned before the first live block
    assert sent == [] and m.store.alerts() == []        # ordinary history: nothing to report


def test_unconfirmed_blocks_wait_and_a_drain_alerts_once(setup):
    chain, make, sent = setup
    m = make()
    m.start()
    theft = chain.head_block + 3
    drain(chain, theft)                                  # 13% of escrow
    chain.head_block = theft + 2                         # 2 confirmations: not processed yet
    assert m.poll() == 0 and m.store.alerts() == []
    chain.head_block = theft + 6
    assert m.poll() == 1
    alerts = m.store.alerts()
    assert {"escrow_drain", "large_withdrawal"} <= {a["rule"] for a in alerts}
    assert all(a["severity"] == "critical" for a in alerts)
    assert len({a["incident"] for a in alerts}) == 1
    assert len(sent) == 1                                # one incident, one message
    assert b"CRITICAL" in sent[0].content and b"OP Mainnet bridge" in sent[0].content
    assert b"LATE" not in sent[0].content
    a = alerts[0]
    assert a["confirmed_at"] == chain.ts(theft) + 6 * 12 and a["detected_at"] is not None
    chain.head_block += 5
    m.poll()
    assert len(sent) == 1                                # nothing sent twice


def test_restart_resumes_from_cursor_without_duplicates_or_renotifying(setup):
    chain, make, sent = setup
    m = make()
    m.start()
    b = chain.head_block + 1
    drain(chain, b, to=777)
    chain.head_block = b + 6
    m.poll()
    n_transfers, n_alerts, n_sent = sum(m.store.transfer_counts().values()), len(m.store.alerts()), len(sent)
    chain.head_block += 20
    m2 = make()                                          # a new process on the same database
    m2.start()
    assert sum(m2.store.transfer_counts().values()) == n_transfers
    assert len(m2.store.alerts()) == n_alerts and len(sent) == n_sent
    assert m2.status.cursor == chain.head_block - 6


def test_a_failed_block_time_read_does_not_lose_a_drain(setup):
    """P0-1 regression: the poll used to store transfers and advance the cursor, then
    fail reading the block time, so the drain was stored but never checked."""
    chain, make, sent = setup
    m = make()
    m.start()
    cursor = m.status.cursor
    theft = chain.head_block + 1
    drain(chain, theft)
    chain.head_block = theft + 6
    chain.fail_block_time = 1
    with pytest.raises(RuntimeError):
        m.poll()
    assert int(m.store.get("cursor")) == cursor          # nothing committed
    assert m.store.alerts() == []
    m.poll()                                             # the next poll re-reads the same blocks
    assert "escrow_drain" in {a["rule"] for a in m.store.alerts()}
    assert len(sent) == 1


def test_a_failed_commit_rebuilds_the_detector_from_the_store(setup, monkeypatch):
    chain, make, sent = setup
    m = make()
    m.start()
    theft = chain.head_block + 1
    drain(chain, theft)
    chain.head_block = theft + 6
    real_add = m.store.add_transfers
    fail = {"n": 1}

    def flaky_add(*a, **k):
        if fail["n"]:
            fail["n"] -= 1
            raise RuntimeError("disk full")
        return real_add(*a, **k)
    monkeypatch.setattr(m.store, "add_transfers", flaky_add)
    stop = threading.Event()
    m.s.poll_seconds = 0
    real_poll, polls = m.poll, {"n": 0}

    def poll_twice():
        polls["n"] += 1
        if polls["n"] >= 2:
            stop.set()
        return real_poll()
    m.poll = poll_twice
    m.run_forever(stop)            # poll 1 fails after the detector saw the drain -> rebuild -> poll 2
    assert "escrow_drain" in {a["rule"] for a in m.store.alerts()}
    mon = m.detector.monitors["optimism"]
    assert m.detector is not None and polls["n"] == 2
    assert 39e6 < mon.net_hour < 41e6                   # the $40M drain counted once, not twice


def test_price_feed_failure_keeps_last_price_and_never_prices_at_zero(setup):
    chain, make, _ = setup
    m = make()
    m.start()
    chain.fail_price = True
    m.refresh_prices(force=True)                         # must not raise
    assert m.prices["WBTC"] == 60_000.0
    h = m.health()
    assert h["prices_stale"] and h["prices"]["WBTC"]["error"]
    b = chain.head_block + 1
    chain.transfer(b, WBTC, user(1), OP_VAULT, 2 * 10**8)
    chain.head_block = b + 6
    assert m.poll() == 1                                 # ingest goes on with the last good price
    row = m.store.transfers_since(chain.ts(b))[0]
    assert row["amount_usd"] == pytest.approx(120_000.0)


def test_a_token_without_any_price_is_stored_unpriced_not_at_zero(setup, tmp_path):
    chain, _, _ = setup
    chain.fail_price = True
    settings = LiveSettings(db_path=str(tmp_path / "fresh.db"), confirmations=6, registry_path=CFG)
    m = LiveMonitor(settings, rpc=chain, store=Store(settings.db_path), detector_cfg=DetectorConfig(history_days=7),
                    clock=lambda: chain.ts(chain.head_block))
    m.start()
    assert "WBTC" not in m.prices and m.status.phase == "live"
    b = chain.head_block + 1
    chain.transfer(b, WBTC, user(1), OP_VAULT, 2 * 10**8)
    chain.head_block = b + 6
    m.poll()
    row = m.store.transfers_since(chain.ts(b))[0]
    assert row["amount_usd"] is None and m.health()["unpriced_transfers"] == 1


def test_rpc_failures_are_survived_and_counted(setup):
    chain, make, _ = setup
    m = make()
    m.start()
    chain.fail_next = 3
    stop = threading.Event()
    m.s.poll_seconds = 0
    polls = {"n": 0}
    real_poll = m.poll

    def poll_then_stop():
        polls["n"] += 1
        if polls["n"] >= 4:
            stop.set()
        return real_poll()
    m.poll = poll_then_stop
    m.run_forever(stop)
    assert chain.errors == 3
    assert m.status.consecutive_failures == 0 and m.status.phase == "live"   # recovered on its own


def test_health_reports_lag_and_goes_degraded_when_stale(setup):
    chain, make, _ = setup
    m = make()
    m.start()
    h = m.health()
    assert h["status"] == "ok" and h["lag_blocks"] == 6
    chain.head_block += 600                              # two hours with no successful poll
    assert m.health()["status"] == "degraded"


def test_historical_alerts_are_stored_but_never_sent(setup):
    chain, make, sent = setup
    drain(chain, chain.head_block - 3 * BPD, to=555)     # three days ago, found while backfilling
    m = make()
    m.start()
    assert [a for a in m.store.alerts() if a["notified_severity"] == "historical"]
    assert sent == []


def test_alerts_found_while_catching_up_after_downtime_are_sent_late(setup):
    chain, make, sent = setup
    m = make()
    m.start()
    theft = chain.head_block + 10
    drain(chain, theft, to=321)
    chain.head_block = theft + 600                       # down for two hours, then restarted
    m2 = make()
    m2.start()
    assert len(sent) == 1 and b"LATE" in sent[0].content


def test_backfill_commits_chunk_by_chunk(setup, tmp_path):
    chain, _, _ = setup
    settings = LiveSettings(db_path=str(tmp_path / "chunks.db"), confirmations=6, registry_path=CFG, chunk_blocks=5_000)
    m = LiveMonitor(settings, rpc=chain, store=Store(settings.db_path), detector_cfg=DetectorConfig(history_days=7),
                    clock=lambda: chain.ts(chain.head_block))
    cursors = []
    real_add = m.store.add_transfers
    m.store.add_transfers = lambda rows, cursor=None, **k: cursors.append(cursor) or real_add(rows, cursor=cursor, **k)
    m.start()
    assert len(cursors) == 11 and cursors == sorted(cursors) and cursors[-1] == chain.head_block - 6


def test_live_api_state_ack_token_simulate_and_metrics(setup, monkeypatch):
    from fastapi.testclient import TestClient
    import bridgewatch.app as bw
    chain, make, _ = setup
    m = make()
    m.start()
    b = chain.head_block + 1
    drain(chain, b, to=4242)
    chain.head_block = b + 6
    m.poll()
    monkeypatch.setattr(bw, "service", bw.LiveService(m))
    m._updated()
    client = TestClient(bw.app)
    aid = client.get("/api/alerts").json()[0]["id"]
    monkeypatch.delenv("BRIDGEWATCH_API_TOKEN", raising=False)
    assert client.post(f"/api/alerts/{aid}/ack").status_code == 403    # live mode: no token configured = no acks
    monkeypatch.setenv("BRIDGEWATCH_API_TOKEN", "s3cret-token")
    assert client.post(f"/api/alerts/{aid}/ack").status_code == 401
    assert client.post(f"/api/alerts/{aid}/ack", headers={"Authorization": "Bearer wrong"}).status_code == 401
    r = client.post(f"/api/alerts/{aid}/ack", headers={"Authorization": "Bearer s3cret-token"})
    assert r.status_code == 200 and r.json()["acknowledged"] is True
    state = client.get("/api/state").json()
    assert state["mode"] == "live" and {x["id"] for x in state["bridges"]} == {"optimism", "base", "arbitrum"}
    assert state["transfers_stored"] > 100 and state["health"] == "ok"
    assert client.post("/api/simulate", json={"bridge": "alpha", "kind": "mass_drain"}).status_code == 409
    text = client.get("/metrics").text
    assert "bridgewatch_ingest_lag_blocks 6" in text and 'bridgewatch_alerts_total{bridge="optimism"' in text
    assert client.get("/api/health").status_code == 200


def test_api_state_is_a_snapshot_rebuilt_after_each_poll(setup, monkeypatch):
    from fastapi.testclient import TestClient
    import bridgewatch.app as bw
    chain, make, _ = setup
    m = make()
    m.start()
    monkeypatch.setattr(bw, "service", bw.LiveService(m))
    m._updated()
    client = TestClient(bw.app)

    def no_scans(*a, **k):
        raise AssertionError("/api/state must not query the database")
    monkeypatch.setattr(m.store, "transfer_counts", no_scans)
    monkeypatch.setattr(m.store, "alerts", no_scans)
    before = client.get("/api/state").json()
    op = next(b for b in before["bridges"] if b["id"] == "optimism")
    assert op["status"] == "ok"
    monkeypatch.undo()
    monkeypatch.setattr(bw, "service", bw.LiveService(m))
    b = chain.head_block + 1
    drain(chain, b, to=31337)
    chain.head_block = b + 6
    m.poll()                                             # the poll rebuilds the snapshot
    monkeypatch.setattr(m.store, "transfer_counts", no_scans)
    monkeypatch.setattr(m.store, "alerts", no_scans)
    after = client.get("/api/state").json()
    op = next(x for x in after["bridges"] if x["id"] == "optimism")
    assert op["status"] == "alert" and op["worst_severity"] == "critical"
    assert after["transfers_stored"] == before["transfers_stored"] + 1


def test_alerts_pagination_with_before_id(setup, monkeypatch):
    from fastapi.testclient import TestClient
    import bridgewatch.app as bw
    chain, make, _ = setup
    m = make()
    m.start()
    for i in range(3):                                    # three separate incidents, two hours apart
        b = chain.head_block + 1
        drain(chain, b, amount_usd=20_000_000, to=900 + i)
        chain.head_block = b + 600
        m.poll()
    monkeypatch.setattr(bw, "service", bw.LiveService(m))
    client = TestClient(bw.app)
    everything = client.get("/api/alerts?limit=500").json()
    first = client.get("/api/alerts?limit=2").json()
    rest = client.get(f"/api/alerts?limit=500&before_id={first[-1]['id']}").json()
    assert [a["id"] for a in first + rest] == [a["id"] for a in everything] and len(everything) > 2
    assert all(x["id"] > y["id"] for x, y in zip(everything, everything[1:]))


def test_rpc_skips_refusing_endpoints_and_retries_transient_errors(monkeypatch):
    import bridgewatch.onchain as oc
    monkeypatch.setattr(oc.time, "sleep", lambda s: None)
    hits, flaky_failures = [], [1]

    def handler(req):
        hits.append(req.url.host)
        if req.url.host == "archive-refuser.example":
            return httpx.Response(403, json={"jsonrpc": "2.0", "id": 1, "error": {
                "code": -32602, "message": "Archive requests require a personal token."}})
        if req.url.host == "flaky.example" and flaky_failures[0]:
            flaky_failures[0] -= 1
            return httpx.Response(503)
        return httpx.Response(200, json={"jsonrpc": "2.0", "id": 1, "result": "0x10"})

    rpc = oc.Rpc(("https://archive-refuser.example", "https://flaky.example"), pause=0)
    rpc.http = httpx.Client(transport=httpx.MockTransport(handler))
    assert rpc.head() == 16
    assert hits == ["archive-refuser.example", "flaky.example", "flaky.example"]   # refusal not retried; 503 retried
    hits.clear()
    assert rpc.head() == 16 and hits == ["flaky.example"]                            # the working endpoint goes first now
