"""Tests for the Objective 1.2 check (#15): the normal outflow range per bridge and hour,
and the share of normal 10-minute periods inside it. All offline, on small handmade datasets
whose expected numbers can be worked out by hand."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bridgewatch.baseline_check import K, check, outflow_range, run  # noqa: E402
from bridgewatch.detector import BUCKET, DetectorConfig, robust_baseline  # noqa: E402
from bridgewatch.source import FileSource  # noqa: E402

DAY = 86_400
T0 = 1_767_225_600            # 2026-01-01 00:00 UTC, a period boundary
CFG = DetectorConfig()        # 7 days of history, min_spread_usd = 100,000
SPIKE_TS = T0 + 8 * DAY + 12 * 3_600


def write_dataset(folder: Path, key: str, days: float = 9, per_period_usd: float = 50_000.0,
                  spike_usd: float = 0.0, quiet_hour: int | None = None, period: str = "believed-normal",
                  hack: bool = False) -> Path:
    """One USDC withdrawal of per_period_usd every 10 minutes (none during quiet_hour), plus one
    spike_usd withdrawal at day 8, 12:00 UTC."""
    rows, i, t = [], 0, T0
    while t < T0 + days * DAY:
        if quiet_hour is None or int((t % DAY) // 3_600) != quiet_hour:
            rows.append({"ts": t + 60, "block": 1_000 + i, "token": "USDC", "direction": "out",
                         "amount": per_period_usd, "usd": per_period_usd, "tx": f"0x{i:064x}", "log_index": 0})
        i += 1
        t += BUCKET
    if spike_usd:
        rows.append({"ts": SPIKE_TS + 120, "block": 999_999, "token": "USDC", "direction": "out",
                     "amount": spike_usd, "usd": spike_usd, "tx": "0x" + "f" * 64, "log_index": 1})
    case = {"key": key, "title": key, "vault": "0x" + "1" * 40, "period": period,
            "tokens": [["0x" + "2" * 40, "USDC", 6]]}
    if hack:
        case["hack_window"] = [999_999, 999_999]
    data = {"case": case, "prices_usd": {"USDC": 1.0}, "balances_at_start": {"USDC": 1e8},
            "start_ts": T0, "end_ts": T0 + days * DAY, "transfers": rows}
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{key}.json"
    path.write_text(json.dumps(data))
    return path


def test_robust_baseline_keeps_the_detectors_spread_floors():
    assert robust_baseline([0.0] * 42, 100_000) == (0.0, 100_000)           # quiet hour: the floor
    assert robust_baseline([10.0] * 42, 1.0) == (10.0, 5.0)                  # MAD 0: half the median
    med, spread = robust_baseline([0.0, 50.0, 100.0, 150.0, 10_000.0], 0.0)  # one outlier barely moves it
    assert med == 100.0 and abs(spread - 1.4826 * 50) < 1e-9                 # MAD 50 beats half the median


def test_outflow_range_is_median_plus_minus_k_spreads_and_never_below_zero():
    lo, hi, med, spread = outflow_range([50_000.0] * 42, 100_000)
    assert (med, spread) == (50_000.0, 100_000)
    assert lo == 0.0 and hi == 50_000.0 + K * 100_000


def test_steady_traffic_is_inside_and_a_spike_is_outside(tmp_path):
    r = check(FileSource(write_dataset(tmp_path, "steady", spike_usd=5_000_000)), CFG)
    checked = 2 * 144                       # days 7 and 8 have a full 7-day history behind them
    assert r["all_periods"] == {"inside": checked - 1, "checked": checked, "share": round((checked - 1) / checked, 4)}
    assert r["withdrawal_periods"]["checked"] == checked
    assert r["outside_count"] == 1
    out = r["outside_examples"][0]
    assert out["start"] == SPIKE_TS and out["outflow_usd"] == 5_050_000 and out["hour_utc"] == 12
    assert out["range_usd"] == [0.0, 350_000.0]
    assert len(r["ranges_by_hour"]) == 24 and r["group"] == "normal"


def test_a_period_never_helps_build_its_own_range(tmp_path):
    # The spike is outside at day 8 even though it is in the history afterwards: walk-forward.
    r = check(FileSource(write_dataset(tmp_path, "spike", spike_usd=5_000_000)), CFG)
    assert [o["start"] for o in r["outside_examples"]] == [SPIKE_TS]


def test_empty_periods_count_in_all_periods_but_not_in_withdrawal_periods(tmp_path):
    r = check(FileSource(write_dataset(tmp_path, "quiet", quiet_hour=3)), CFG)
    assert r["all_periods"]["checked"] == 2 * 144
    assert r["withdrawal_periods"]["checked"] == 2 * 144 - 2 * 6     # hour 3 is empty both days
    assert r["all_periods"]["share"] == r["withdrawal_periods"]["share"] == 1.0


def test_run_pools_normal_windows_only_and_lists_what_it_skipped(tmp_path):
    write_dataset(tmp_path, "a-normal", spike_usd=5_000_000)
    write_dataset(tmp_path, "b-stress", spike_usd=5_000_000, period="stress-normal: turbulent market")
    write_dataset(tmp_path, "c-short", days=7.5)
    write_dataset(tmp_path, "d-hack", hack=True)
    r = run([tmp_path], CFG)
    assert [d["key"] for d in r["datasets"]] == ["a-normal", "b-stress"]
    assert [d["group"] for d in r["datasets"]] == ["normal", "stress"]
    assert [s["dataset"] for s in r["skipped"]] == ["c-short.json"]
    pooled = r["normal"]["all_periods"]
    assert pooled["checked"] == 288 and pooled["inside"] == 287 and pooled["meets_target"] is True
    assert r["k"] == K == 3.0 and r["target"] == 0.95
