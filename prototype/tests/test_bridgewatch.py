"""Tests for the BridgeWatch prototype (SNX-3 draft): the synthetic source, the
detector's baseline and rules, the evaluation, and the API. All offline."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest  # noqa: E402

from bridgewatch.detector import BUCKET, Detector, DetectorConfig  # noqa: E402
from bridgewatch.evaluate import T0, false_alarms, run_case  # noqa: E402
from bridgewatch.models import Bridge, FlowEvent  # noqa: E402
from bridgewatch.synthetic import BRIDGES, SyntheticSource, activity  # noqa: E402

DAY = 86_400
FAST = DetectorConfig(warmup=2 * DAY)
BRIDGE = Bridge("t", "Test Bridge", ("A", "B"), 100e6)


def steady(det, days, per_bucket=5, amount=10_000.0, start=T0):
    """Perfectly regular traffic: `per_bucket` releases (and deposits) every 10 minutes."""
    t = start
    while t < start + days * DAY:
        for i in range(per_bucket):
            ts = t + i * BUCKET / per_bucket
            det.observe(FlowEvent(ts, "t", "in", amount, "d"))
            det.observe(FlowEvent(ts + 1, "t", "out", amount, "r"))
        t += BUCKET
    return t


def test_synthetic_source_is_deterministic_and_ordered():
    a = list(SyntheticSource(seed=5).events_between(T0, T0 + 3_600))
    b = list(SyntheticSource(seed=5).events_between(T0, T0 + 3_600))
    assert [e.tx for e in a] == [e.tx for e in b] and len(a) > 50
    assert all(x.ts <= y.ts for x, y in zip(a, a[1:]))
    assert all(T0 <= e.ts < T0 + 3_600 for e in a)


def test_traffic_has_a_daily_cycle():
    assert activity(T0 + 15 * 3_600) > activity(T0 + 3 * 3_600)


def test_injected_exploit_matches_its_ground_truth():
    src = SyntheticSource(seed=1)
    inc = src.inject("gamma", "mass_drain", T0 + 100, escrow_usd=60e6)
    assert 0.7 * 60e6 < inc.stolen_usd < 0.95 * 60e6
    released = [e for e in src.events_between(T0, T0 + DAY) if e.backed is False]
    assert abs(sum(e.amount_usd for e in released) - inc.stolen_usd) < 1


def test_no_baseline_alerts_while_learning():
    det = Detector((BRIDGE,), FAST)
    t = steady(det, 1)
    det.observe(FlowEvent(t, "t", "out", 1.5e6, "big"))   # 1.5% of escrow, but no baseline yet
    assert [a.rule for a in det.alerts] == []
    det.observe(FlowEvent(t + 60, "t", "out", 3e6, "bigger"))   # one 3% release: needs no baseline
    assert [a.rule for a in det.alerts] == ["large_withdrawal"]


def test_normal_traffic_raises_nothing_and_a_spike_is_caught():
    det = Detector((BRIDGE,), FAST)
    t = steady(det, 3)
    assert det.alerts == []
    det.observe(FlowEvent(t + 5, "t", "out", 2e6, "x"))   # 2% of escrow in one go
    rules = {a.rule for a in det.alerts}
    assert "outflow_spike" in rules
    assert "2.0M left Test Bridge" in det.alerts[0].message


def test_drain_rule_needs_no_baseline_and_is_critical():
    det = Detector((BRIDGE,), FAST)
    det.observe(FlowEvent(T0, "t", "out", 6e6, "x"))       # 6% of escrow on the first event
    assert [(a.rule, a.severity) for a in det.alerts] == [("escrow_drain", "critical"), ("large_withdrawal", "critical")]
    assert len({a.incident for a in det.alerts}) == 1        # one incident -> one notification


def test_cooldown_merges_repeat_triggers_into_one_alert():
    det = Detector((BRIDGE,), FAST)
    for i in range(10):
        det.observe(FlowEvent(T0 + i * 60, "t", "out", 6e6, f"x{i}"))
    drains = [a for a in det.alerts if a.rule == "escrow_drain"]
    assert len(drains) == 1 and drains[0].last_seen == T0 + 540
    assert "6% of its" in drains[0].message                 # message: the moment it fired
    assert drains[0].observed > 0.4 and "net in the last hour" in drains[0].worst   # worst point kept separately


def quiet(det, days, start=T0):
    """Deposits only: the usual outflow is $0 every hour (MAD = 0)."""
    t = start
    while t < start + days * DAY:
        det.observe(FlowEvent(t, "t", "in", 10_000.0, "d"))
        t += BUCKET
    return t


def test_min_spread_stops_small_releases_from_alerting_in_quiet_hours():
    det = Detector((BRIDGE,), FAST)                       # min_spread_usd defaults to $100K
    t = quiet(det, 3)
    det.observe(FlowEvent(t + 5, "t", "out", 550_000.0, "a"))   # > 0.5% of escrow but only 5.5 spreads
    assert det.alerts == []
    old_floor = Detector((BRIDGE,), DetectorConfig(warmup=2 * DAY, min_spread_usd=1.0))
    quiet(old_floor, 3)
    old_floor.observe(FlowEvent(t + 5, "t", "out", 550_000.0, "a"))
    assert [a.rule for a in old_floor.alerts] == ["outflow_spike"]   # what the $1 floor used to do
    det.observe(FlowEvent(t + 65, "t", "out", 200_000.0, "b"))  # $750K in 10 min = 7.5 spreads
    assert [a.rule for a in det.alerts] == ["outflow_spike"]


def test_large_single_withdrawal_rule_and_per_bridge_override():
    det = Detector((BRIDGE,), FAST)
    det.observe(FlowEvent(T0, "t", "out", 2.5e6, "x"))       # 2.5% of a $100M escrow in one release
    assert [(a.rule, a.severity) for a in det.alerts] == [("large_withdrawal", "warning")]
    assert "One release of $2.5M" in det.alerts[0].message
    relaxed = Detector((BRIDGE,), FAST, overrides={"t": {"large_withdrawal_share": 0.03}})
    relaxed.observe(FlowEvent(T0, "t", "out", 2.5e6, "x"))
    assert relaxed.alerts == [] and relaxed.monitors["t"].cfg.large_withdrawal_share == 0.03
    small = Detector((Bridge("s", "Small", ("A",), 10e6),), FAST)
    small.observe(FlowEvent(T0, "s", "out", 900_000.0, "y"))  # 9% of escrow but under the $1M floor
    assert [a.rule for a in small.alerts] == ["escrow_drain"]


def test_alerts_carry_confirmation_and_detection_times():
    clock = {"now": T0 + 100}
    det = Detector((BRIDGE,), FAST, clock=lambda: clock["now"])
    det.observe(FlowEvent(T0, "t", "out", 6e6, "x", confirmed_at=T0 + 72))
    a = det.alerts[0]
    assert a.started == T0 and a.confirmed_at == T0 + 72 and a.detected_at == T0 + 100


def test_unbacked_rule_only_with_message_matching():
    for matching, expected in ((False, set()), (True, {"unbacked_release"})):
        det = Detector((BRIDGE,), DetectorConfig(use_message_matching=matching))
        det.observe(FlowEvent(T0, "t", "out", 1_000, "x", backed=False))
        assert {a.rule for a in det.alerts} == expected


def test_one_whale_does_not_move_the_baseline():
    det = Detector((BRIDGE,), FAST)
    steady(det, 1)
    det.observe(FlowEvent(T0 + DAY + 10, "t", "out", 5e6, "whale"))
    t = steady(det, 2, start=T0 + DAY + BUCKET)
    med = det.monitors["t"].baseline(t)[0]
    assert med == pytest.approx(50_000, rel=0.01)   # 5 x $10K per bucket, whale ignored by the median


def test_evaluation_catches_a_mass_drain_early():
    case = run_case("mass_drain", "alpha", seed=1, cfg=DetectorConfig(), baseline_days=4)
    assert case.detected and case.minutes_to_alert < 60 and case.lost_before < 0.25


def test_false_alarm_rate_is_measured_on_clean_traffic():
    rate, by_rule = false_alarms(DetectorConfig(warmup=2 * DAY), days=4, seed=3)
    assert rate >= 0 and sum(by_rule.values()) == round(rate * 2 * len(BRIDGES))


# --- API ------------------------------------------------------------------

@pytest.fixture(scope="module")
def api():
    from fastapi.testclient import TestClient
    import bridgewatch.app as bw
    sim = bw.Sim(seed=3, speed=60)
    sim.warm_up()
    bw.service = bw.DemoService(sim)
    return TestClient(bw.app), bw


def test_api_state_lists_bridges_with_learned_baselines(api):
    client, _ = api
    body = client.get("/api/state").json()
    assert body["data"] == "synthetic" and len(body["bridges"]) == 4
    assert all(b["status"] in ("ok", "alert") and b["normal_hour_usd"] for b in body["bridges"])


def test_api_simulated_exploit_is_detected_live(api):
    client, bw = api
    r = client.post("/api/simulate", json={"bridge": "beta", "kind": "key_compromise"})
    assert r.status_code == 200 and r.json()["stolen_usd"] > 0
    assert client.post("/api/simulate", json={"bridge": "beta", "kind": "mass_drain"}).status_code == 409
    bw.service.sim.step(900)
    alerts = client.get("/api/alerts").json()
    hit = [a for a in alerts if a["bridge"] == "beta" and a["severity"] == "critical"]
    assert hit
    assert client.post(f"/api/alerts/{hit[0]['id']}/ack").json()["acknowledged"] is True
    series = client.get("/api/series/beta?hours=2").json()
    assert series["buckets"] and any(a["bridge"] == "beta" for a in series["alerts"])
    assert series["buckets"][-1]["partial"] is True   # the bucket still filling is included


def test_api_rejects_bad_input(api):
    client, _ = api
    assert client.post("/api/simulate", json={"bridge": "nope", "kind": "mass_drain"}).status_code == 404
    assert client.post("/api/simulate", json={"bridge": "alpha", "kind": "nope"}).status_code == 400
    assert client.get("/api/series/nope").status_code == 404
    assert client.post("/api/alerts/999999/ack").status_code == 404


def test_dashboard_is_served(api):
    client, _ = api
    r = client.get("/")
    assert r.status_code == 200 and "BridgeWatch" in r.text and "Synthetic data" in r.text


# --- Real on-chain replay (saved data, offline) ------------------------------

def test_orbit_replay_alerts_on_first_theft_with_no_false_alarms():
    from bridgewatch.replay import ORBIT_PATH, run
    from bridgewatch.source import FileSource
    src = FileSource(ORBIT_PATH)
    assert src.kind == "hack" and src.prices["USDT"] == 1.0
    r = run(src, DetectorConfig())
    assert r["false_alarms_during_baseline"] == 0 and r["baseline_days"] >= 13
    assert len(r["thefts"]) == 4 and 59e6 < r["stolen_usd_tracked"] < 61e6
    assert r["seconds_from_first_theft_to_alert"] == 0                     # the first theft trips it
    assert 0 <= r["detection_latency_s"] <= 60                              # proposal: within 1 min of 6 confirmations
    assert r["first_alert_detected_at"] >= r["first_theft_ts"] + 72        # never before the 6th confirmation
    assert r["stolen_after_alert_usd"] > 0.8 * r["stolen_usd_tracked"]
    assert any(a["severity"] == "critical" for a in r["alerts"])


def test_saved_results_are_served_and_missing_ones_are_404(api, tmp_path, monkeypatch):
    client, _ = api
    monkeypatch.setenv("BRIDGEWATCH_RESULTS_DIR", str(tmp_path))
    assert client.get("/api/evaluation").status_code == 404
    assert "python -m bridgewatch.replay" in client.get("/api/replay").json()["detail"]
    (tmp_path / "evaluation.json").write_text('{"note": "done"}')
    (tmp_path / "replay.json").write_text('{"cases": [{"key": "orbit-2023", "thefts": []}]}')
    assert client.get("/api/evaluation").json() == {"note": "done"}
    assert client.get("/api/replay/orbit-2023").json()["key"] == "orbit-2023"
    assert client.get("/api/replay/nope").status_code == 404
