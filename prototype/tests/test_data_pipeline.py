"""Tests for the data pipeline pieces: dataset files (FileSource), the SQLite
schema and its migration, load_data, the real-data evaluation, configuration,
and webhook delivery (backoff, Retry-After, grouping, LATE). All offline."""
import gzip
import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx  # noqa: E402
import pytest  # noqa: E402

from bridgewatch.models import Alert  # noqa: E402
from bridgewatch.notify import Notifier  # noqa: E402
from bridgewatch.source import FileSource, find_datasets, to_flow_event  # noqa: E402
from bridgewatch.store import SCHEMA_VERSION, Store  # noqa: E402

ORBIT = Path(__file__).resolve().parents[1] / "bridgewatch" / "data" / "orbit-2023.json"


# --- FileSource ------------------------------------------------------------------

def test_file_source_reads_the_orbit_dataset():
    src = FileSource(ORBIT)
    rows = src.transfers()
    assert src.key == "orbit-2023" and src.kind == "hack" and len(rows) == 254
    assert all(t.bridge == "orbit-2023" and t.chain == "ethereum" for t in rows)
    assert [t.block_time for t in rows] == sorted(t.block_time for t in rows)
    raw = json.loads(ORBIT.read_text())["transfers"][0]
    first = next(t for t in rows if t.tx_hash == raw["tx"] and t.log_index == raw["log_index"])
    assert first.decimals == 8 and first.amount == pytest.approx(raw["amount"]) and isinstance(first.amount_raw, int)
    assert 60e6 < src.escrow_usd_at_start < 80e6
    e = to_flow_event(first, 72)
    assert e.confirmed_at == first.block_time + 72 and e.amount_usd == raw["usd"]
    batches = list(FileSource(ORBIT, chunk_blocks=10_000).batches())
    assert len(batches) > 1 and sum(len(b.transfers) for b in batches) == 254
    assert all(b.cursor == b.transfers[-1].block_number for b in batches)


def write_normal(folder: Path, gz: bool = False) -> Path:
    """A believed-normal dataset made from Orbit's pre-hack days (no hack window)."""
    data = json.loads(ORBIT.read_text())
    data["case"] = {k: v for k, v in data["case"].items() if k not in ("hack_window", "theft_min_usd")}
    data["case"]["key"] = "orbit-pre-hack"
    first_theft_block = 18_907_104
    data["transfers"] = [r for r in data["transfers"] if r["block"] < first_theft_block]
    data["end_ts"] = max(r["ts"] for r in data["transfers"])
    folder.mkdir(parents=True, exist_ok=True)
    if gz:
        path = folder / "orbit-pre-hack.json.gz"
        with gzip.open(path, "wt", encoding="utf-8") as f:
            json.dump(data, f)
    else:
        path = folder / "orbit-pre-hack.json"
        path.write_text(json.dumps(data))
    return path


def test_file_source_finds_gzip_files_in_subfolders(tmp_path):
    path = write_normal(tmp_path / "normal", gz=True)
    assert find_datasets(tmp_path) == [path]
    src = FileSource(path)
    assert src.kind == "normal" and len(src.transfers()) == len(src.data["transfers"]) == 240


# --- store schema -------------------------------------------------------------------

V1_SCHEMA = """
CREATE TABLE transfers (
  tx TEXT NOT NULL, log_index INTEGER NOT NULL, block INTEGER NOT NULL, ts INTEGER NOT NULL,
  bridge TEXT NOT NULL, token TEXT NOT NULL, direction TEXT NOT NULL CHECK (direction IN ('in','out')),
  amount REAL NOT NULL, counterparty TEXT NOT NULL, PRIMARY KEY (tx, log_index));
CREATE INDEX transfers_ts ON transfers (ts);
CREATE TABLE alerts (
  id INTEGER PRIMARY KEY AUTOINCREMENT, bridge TEXT NOT NULL, rule TEXT NOT NULL, severity TEXT NOT NULL,
  started REAL NOT NULL, last_seen REAL NOT NULL, observed REAL NOT NULL, expected REAL NOT NULL,
  message TEXT NOT NULL, worst TEXT NOT NULL DEFAULT '', acknowledged INTEGER NOT NULL DEFAULT 0,
  acknowledged_at REAL, notified_severity TEXT NOT NULL DEFAULT '', UNIQUE (bridge, rule, started));
CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
"""


def test_a_v1_database_is_migrated_to_v2(tmp_path):
    path = tmp_path / "old.db"
    db = sqlite3.connect(path)
    db.executescript(V1_SCHEMA)
    db.execute("INSERT INTO transfers VALUES ('0xabc', 7, 100, 1700000000, 'base', 'USDC', 'out', 1234.567891, '0xdef')")
    db.execute("INSERT INTO transfers VALUES ('0xabd', 1, 101, 1700000012, 'base', 'WBTC', 'in', 0.5, '0xdef')")
    db.execute("INSERT INTO alerts (bridge, rule, severity, started, last_seen, observed, expected, message, notified_severity) "
               "VALUES ('base', 'escrow_drain', 'critical', 1, 1, 0.1, 0.05, 'old alert', 'critical')")
    db.execute("INSERT INTO meta VALUES ('cursor', '101')")
    db.commit()
    db.close()

    store = Store(path)
    assert store.schema_version == SCHEMA_VERSION == 2
    rows = {r["tx_hash"]: r for r in store.transfers_since(0)}
    usdc = rows["0xabc"]
    assert usdc["chain"] == "ethereum" and usdc["amount_raw"] == "1234567891" and usdc["decimals"] == 6
    assert usdc["block_number"] == 100 and usdc["amount_usd"] is None
    assert rows["0xabd"]["amount_raw"] == "50000000" and rows["0xabd"]["decimals"] == 8
    assert store.get("cursor") == "101"
    old = store.alerts()[0]
    assert old["message"] == "old alert" and old["incident"] == "" and old["notify_attempts"] == 0
    assert store.fill_missing_usd("WBTC", 60_000.0) == 1
    assert store.transfers_since(1700000012)[0]["amount_usd"] == pytest.approx(30_000.0)
    store.db.close()
    assert Store(path).schema_version == 2               # opening again changes nothing


def test_store_keys_on_chain_tx_and_log_index_and_prunes_only_live_rows(tmp_path):
    store = Store(tmp_path / "x.db")
    src = FileSource(ORBIT)
    rows = src.transfers()[:10]
    assert sum(store.add_transfers(rows, source="file:orbit-2023").values()) == 10
    assert store.add_transfers(rows, cursor=5) == {} and store.get("cursor") == "5"
    assert store.prune(2e9) == 0                          # imported datasets are kept
    names = {r[1] for r in store.db.execute("PRAGMA index_list(transfers)")}
    assert "transfers_bridge_time" in names


# --- load_data -------------------------------------------------------------------

def test_load_data_is_idempotent(tmp_path, capsys):
    from bridgewatch.load_data import main
    normal = write_normal(tmp_path / "data" / "normal")
    db = str(tmp_path / "datasets.db")
    first = main(["--db", db, str(ORBIT), str(normal)])
    assert {r["key"]: r["new"] for r in first} == {"orbit-2023": 254, "orbit-pre-hack": 0}   # same transfers, same keys
    again = main(["--db", db, str(ORBIT), str(normal)])
    assert all(r["new"] == 0 for r in again)
    assert "orbit-2023" in capsys.readouterr().out
    store = Store(db)
    assert store.transfer_counts() == {"orbit-2023": 254}
    assert json.loads(store.get("dataset:orbit-pre-hack"))["kind"] == "normal"


def test_load_data_refuses_a_live_database(tmp_path):
    """Datasets share (chain, tx, log_index) keys with live mode; importing into the live DB
    would make live ingest silently skip those transfers."""
    from bridgewatch.load_data import main
    db = str(tmp_path / "live.db")
    Store(db).put("cursor", "26000000")
    with pytest.raises(SystemExit, match="live-mode database"):
        main(["--db", db, str(ORBIT)])
    assert Store(db).transfer_counts() == {}


# --- evaluate --real ----------------------------------------------------------------

def test_real_evaluation_counts_false_alarms_per_bridge_week(tmp_path):
    from bridgewatch.evaluate import main
    write_normal(tmp_path / "data" / "normal")
    out = tmp_path / "evaluation-real.json"
    result = main(["--real", "--data", str(tmp_path / "data"), "--out", str(out)])
    saved = json.loads(out.read_text())
    assert saved["datasets"][0]["key"] == "orbit-pre-hack" == result["datasets"][0]["key"]
    d = saved["datasets"][0]
    assert 1.4 < d["weeks_counted"] < 1.7 and d["false_alarms"] == 0 and d["per_week"] == 0
    assert saved["overall"]["all_meet_target"] is True and saved["target_per_bridge_week"] == 1


# --- configuration -------------------------------------------------------------------

def test_old_single_chain_bridges_json_still_loads(tmp_path):
    from bridgewatch.config import load_registry
    old = {"chain": "ethereum", "explorer_tx": "https://etherscan.io/tx/",
           "tokens": [{"symbol": "USDT", "address": "0xDAC17F958D2ee523a2206206994597C13D831ec7", "decimals": 6,
                       "price": {"fixed": 1.0}}],
           "bridges": [{"id": "base", "name": "Base bridge", "chains": ["Ethereum", "Base"], "vault": "0x31"}]}
    (tmp_path / "old.json").write_text(json.dumps(old))
    reg = load_registry(tmp_path / "old.json")
    assert reg.chains["ethereum"].confirmations == 6 and reg.chains["ethereum"].explorer_tx.startswith("https://ether")
    assert reg.bridges[0].chain == "ethereum" and reg.tokens[0].address.startswith("0xdac")
    old["bridges"][0]["overrides"] = {"z_treshold": 5}     # a typo is an error, not silently ignored
    (tmp_path / "bad.json").write_text(json.dumps(old))
    with pytest.raises(ValueError, match="z_treshold"):
        load_registry(tmp_path / "bad.json")


def test_history_days_comes_from_one_setting():
    from bridgewatch.config import detector_config, settings_from_env
    s = settings_from_env({"BRIDGEWATCH_HISTORY_DAYS": "5", "BRIDGEWATCH_MIN_SPREAD_USD": "250000"})
    cfg = detector_config(s)
    assert cfg.history_days == 5 and cfg.min_spread_usd == 250_000


# --- notifier ----------------------------------------------------------------------

def stored_alert(store, rule="escrow_drain", severity="critical", started=1_000.0, incident="base-1000",
                 detected_at=1_080.0, historical=False) -> int:
    a = Alert(0, "base", rule, severity, started, started, 0.1, 0.05, f"{rule} happened",
              confirmed_at=started + 72, detected_at=detected_at, incident=incident)
    return store.upsert_alert(a, historical=historical)


class Receiver:
    """A fake webhook that answers with the queued responses, then 200."""

    def __init__(self, *responses):
        self.responses, self.requests = list(responses), []
        self.client = httpx.Client(transport=httpx.MockTransport(self.handle))

    def handle(self, request):
        self.requests.append(json.loads(request.content))
        return self.responses.pop(0) if self.responses else httpx.Response(200)


def test_notifier_backs_off_and_honors_retry_after():
    store, clock = Store(":memory:"), {"t": 10_000.0}
    rx = Receiver(httpx.Response(503), httpx.Response(429, headers={"Retry-After": "120"}))
    n = Notifier("https://hooks.example/x", client=rx.client, clock=lambda: clock["t"])
    n.attach(store, {"base": "Base bridge"})
    stored_alert(store)
    assert n.deliver_pending() == 0 and len(rx.requests) == 1          # 503: retry in 5 s
    clock["t"] += 1
    assert n.deliver_pending() == 0 and len(rx.requests) == 1          # still backing off
    clock["t"] += 5
    assert n.deliver_pending() == 0 and len(rx.requests) == 2          # 429, Retry-After: 120
    clock["t"] += 60
    assert n.deliver_pending() == 0 and len(rx.requests) == 2          # the receiver asked for 120 s
    clock["t"] += 61
    assert n.deliver_pending() == 1 and len(rx.requests) == 3
    assert store.pending_notifications() == [] and n.sent == 1 and n.failed == 2
    assert "CRITICAL" in rx.requests[-1]["text"] and "Base bridge" in rx.requests[-1]["text"]


def test_notifier_gives_up_after_max_attempts():
    store, clock = Store(":memory:"), {"t": 0.0}
    rx = Receiver(*[httpx.Response(500)] * 10)
    n = Notifier("https://hooks.example/x", client=rx.client, clock=lambda: clock["t"], max_attempts=3)
    n.attach(store, {})
    stored_alert(store)
    for _ in range(5):
        n.deliver_pending()
        clock["t"] += 1_000
    assert len(rx.requests) == 3 and n.gave_up == 1
    assert store.alerts()[0]["notified_severity"] == "failed"


def test_one_incident_one_message_then_an_upgrade_and_late_label():
    store = Store(":memory:")
    rx = Receiver()
    n = Notifier("https://hooks.example/x", client=rx.client)
    n.attach(store, {"base": "Base bridge"})
    stored_alert(store, "outflow_spike", "warning", started=1_000.0)
    stored_alert(store, "withdrawal_burst", "warning", started=1_060.0)
    n.deliver_pending()
    assert len(rx.requests) == 1 and "outflow spike, withdrawal burst" in rx.requests[0]["text"]
    stored_alert(store, "large_withdrawal", "warning", started=1_200.0)     # same incident, same level: folded in
    n.deliver_pending()
    assert len(rx.requests) == 1
    stored_alert(store, "escrow_drain", "critical", started=1_300.0)        # raises it to critical: one update
    n.deliver_pending()
    assert len(rx.requests) == 2 and "(now critical)" in rx.requests[1]["text"]
    stored_alert(store, "escrow_drain", "critical", started=50_000.0, incident="base-50000", detected_at=60_000.0)
    stored_alert(store, "outflow_spike", "warning", started=90_000.0, incident="base-90000", historical=True)
    n.deliver_pending()
    assert len(rx.requests) == 3 and rx.requests[2]["text"].startswith("[BridgeWatch] LATE CRITICAL")
    assert store.pending_notifications() == []                              # historical ones are never sent


def test_notifier_worker_thread_delivers_without_blocking_the_caller():
    store = Store(":memory:")
    rx = Receiver()
    n = Notifier("https://hooks.example/x", client=rx.client)
    n.attach(store, {})
    n.start()
    try:
        stored_alert(store)
        n.wake()                                  # returns at once; the thread sends
        for _ in range(100):
            if rx.requests:
                break
            import time
            time.sleep(0.02)
        assert len(rx.requests) == 1
    finally:
        n.stop()
