"""
Objective 1.2 (#15): how well the baseline of normal describes normal days.

  "Compute the normal outflow range for each bridge and each hour of the day from
  the past seven days, and show that at least 95% of normal 10-minute periods fall
  inside this range."

The range is the detector's own baseline (detector.robust_baseline), so this
measures exactly what the alert rules compare against:

  normal outflow range = [max(0, median - K x spread), median + K x spread]

for the same hour of day over the past 7 days (the last 42 ten-minute periods of
that hour, as in BridgeMonitor), with K = 3, chosen before any result was looked
at. K = 1 and 2 are reported for context only; they are not the target.

For each believed-normal dataset, every 10-minute period that has a full 7 days of
history behind it is checked against the range built from the periods before it
(walk-forward: a period never helps build its own range). Two shares are reported:

  all periods             every checked period
  withdrawal periods      only periods with at least one withdrawal

On quiet vaults almost every period is empty, and an empty period is inside any
range that starts at $0, so the share over all periods is close to 100% almost by
construction there. The withdrawal-only share is the honest one for those vaults.

"Stress" windows (a believed-normal vault during a turbulent market, e.g. the FTX
collapse) are reported separately and never count toward the 95% target.

Run (from prototype/):
  python -m bridgewatch.baseline_check                 -> results/baseline-check.json
  python -m bridgewatch.baseline_check --data DIR ...  other dataset folders
"""

from __future__ import annotations
import argparse
import json
import math
import time
from collections import deque
from pathlib import Path

from .config import DATA_DIR, PROTOTYPE_DIR, detector_config, settings_from_env
from .detector import BUCKET, DetectorConfig, robust_baseline
from .source import FileSource, find_datasets, to_flow_event

K = 3.0                      # range half-width in spreads (team decision, Oct 23)
CONTEXT_K = (1.0, 2.0, 3.0)
TARGET = 0.95
DAY = 86_400
RESEARCH_NORMAL_DIR = PROTOTYPE_DIR.parent / "research" / "bridge-hacks" / "03-onchain-data" / "normal"
DEFAULT_DIRS = (DATA_DIR / "normal", RESEARCH_NORMAL_DIR)


def _hour(ts: float) -> int:
    return int((ts % DAY) // 3_600)


def outflow_range(history, min_spread_usd: float, k: float = K) -> tuple[float, float, float, float]:
    """(low, high, median, spread) of the normal outflow range for one hour's history."""
    med, spread = robust_baseline(history, min_spread_usd)
    return max(0.0, med - k * spread), med + k * spread, med, spread


def period_outflows(src: FileSource) -> list[tuple[float, float, int]]:
    """(start, outflow USD, withdrawals) for every 10-minute period from the dataset's start to
    its end, empty periods included. Transfers with no USD price are skipped, as in the replay."""
    first = src.start_ts - src.start_ts % BUCKET
    n = math.ceil((src.end_ts - first) / BUCKET)        # periods that start before the data ends
    usd, cnt = [0.0] * n, [0] * n
    for t in src.transfers():
        e = to_flow_event(t)
        if e is None or e.direction != "out":
            continue
        i = int((e.ts - first) // BUCKET)
        if 0 <= i < n:
            usd[i] += e.amount_usd
            cnt[i] += 1
    return [(first + i * BUCKET, usd[i], cnt[i]) for i in range(n)]


def check(src: FileSource, cfg: DetectorConfig) -> dict:
    """Walk-forward check of one dataset: every period with a full history is compared with the
    range built from the 7 days before it."""
    per_hour = int(cfg.history_days * 3_600 // BUCKET)        # 42 periods of each hour in 7 days
    hist = {h: deque(maxlen=per_hour) for h in range(24)}
    counted_from = src.start_ts + cfg.history_days * DAY
    tally = {k: {"all": [0, 0], "withdrawal": [0, 0]} for k in CONTEXT_K}   # [inside, checked]
    outside = []
    for start, out_usd, n_out in period_outflows(src):
        h = _hour(start)
        if start >= counted_from and len(hist[h]) == per_hour:
            for k in CONTEXT_K:
                lo, hi, med, spread = outflow_range(hist[h], cfg.min_spread_usd, k)
                inside = lo <= out_usd <= hi
                groups = ("all", "withdrawal") if n_out else ("all",)
                for g in groups:
                    tally[k][g][0] += inside
                    tally[k][g][1] += 1
                if k == K and not inside:
                    outside.append({"start": start, "hour_utc": h, "outflow_usd": round(out_usd, 2),
                                    "withdrawals": n_out, "range_usd": [round(lo, 2), round(hi, 2)]})
        hist[h].append(out_usd)

    def share(k, g):
        inside, checked = tally[k][g]
        return {"inside": inside, "checked": checked, "share": round(inside / checked, 4) if checked else None}

    # The range for each hour of the day as it stands at the end of the window (the past 7 days).
    ranges = []
    for h in range(24):
        if len(hist[h]) == per_hour:
            lo, hi, med, spread = outflow_range(hist[h], cfg.min_spread_usd)
            ranges.append({"hour_utc": h, "median_usd": round(med, 2), "spread_usd": round(spread, 2),
                           "low_usd": round(lo, 2), "high_usd": round(hi, 2)})
    period = src.case.get("period", "")
    return {
        "key": src.key, "title": src.title, "vault": src.vault, "dataset": str(src.path.name),
        "group": "stress" if period.startswith("stress") else "normal",
        "days": round((src.end_ts - src.start_ts) / DAY, 1),
        "all_periods": share(K, "all"), "withdrawal_periods": share(K, "withdrawal"),
        "context_k": {f"{k:g}": {"all_periods": share(k, "all"), "withdrawal_periods": share(k, "withdrawal")}
                      for k in CONTEXT_K},
        "outside_count": len(outside), "outside_examples": sorted(outside, key=lambda o: -o["outflow_usd"])[:5],
        "ranges_by_hour": ranges,
    }


def _pooled(rows: list[dict], field: str) -> dict:
    inside = sum(r[field]["inside"] for r in rows)
    checked = sum(r[field]["checked"] for r in rows)
    return {"inside": inside, "checked": checked, "share": round(inside / checked, 4) if checked else None,
            "meets_target": (inside / checked >= TARGET) if checked else None}


def run(dirs=DEFAULT_DIRS, cfg: DetectorConfig | None = None) -> dict:
    """Check every believed-normal dataset under the given folders (hack cases are skipped;
    datasets shorter than 7 days + 1 day are skipped and listed, since nothing could be checked)."""
    cfg = cfg or detector_config()
    rows, skipped = [], []
    for d in dirs:
        for path in find_datasets(d):
            src = FileSource(path)
            if src.kind != "normal":
                continue
            if src.end_ts - src.start_ts < (cfg.history_days + 1) * DAY:
                skipped.append({"dataset": path.name, "days": round((src.end_ts - src.start_ts) / DAY, 1),
                                "reason": "shorter than 7 days of history plus 1 day to check"})
                continue
            rows.append(check(src, cfg))
    normal = [r for r in rows if r["group"] == "normal"]
    for r in rows:
        for field in ("all_periods", "withdrawal_periods"):
            s = r[field]["share"]
            r[field]["meets_target"] = None if s is None else s >= TARGET
    return {
        "generated_at": time.time(),
        "objective": "1.2 (#15): at least 95% of normal 10-minute periods fall inside the normal outflow range",
        "range": f"[max(0, median - {K:g} x spread), median + {K:g} x spread] of the same hour over the past "
                 f"{cfg.history_days:g} days; median and spread from detector.robust_baseline "
                 f"(min_spread_usd = {cfg.min_spread_usd:g})",
        "k": K, "target": TARGET,
        "normal": {"datasets": len(normal), "all_periods": _pooled(normal, "all_periods"),
                   "withdrawal_periods": _pooled(normal, "withdrawal_periods"),
                   "below_target_withdrawal_periods": [r["key"] for r in normal
                                                       if r["withdrawal_periods"]["meets_target"] is False]},
        "datasets": rows, "skipped": skipped,
        "note": "Public Ethereum data (key-less JSON-RPC, fetched 2026-10-07), not SonarX. 'Believed normal' "
                "means no known incident on the vault in the window. Stress windows are reported but not pooled.",
    }


def _print(r: dict) -> None:
    print(f"Objective 1.2: share of 10-minute periods inside the normal outflow range (K = {r['k']:g}, target {r['target']:.0%})")
    print(f"  {'dataset':36} {'group':6} {'all periods':>20} {'withdrawal periods':>22}")
    for d in r["datasets"]:
        a, w = d["all_periods"], d["withdrawal_periods"]
        ws = "n/a" if w["share"] is None else f"{w['share']:.1%} of {w['checked']}"
        print(f"  {d['key']:36} {d['group']:6} {a['share']:>8.1%} of {a['checked']:<8} {ws:>22}")
    n = r["normal"]
    print(f"Pooled over {n['datasets']} normal datasets: all periods {n['all_periods']['share']:.1%} "
          f"(target met: {n['all_periods']['meets_target']}), withdrawal periods {n['withdrawal_periods']['share']:.1%} "
          f"(target met: {n['withdrawal_periods']['meets_target']})")
    for s in r["skipped"]:
        print(f"  skipped {s['dataset']}: {s['reason']}")


def main(argv: list[str] | None = None) -> dict:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", nargs="+", help="dataset folders (default: data/normal and the research normal folder)")
    ap.add_argument("--out", help="where to save the JSON result (default: results/baseline-check.json)")
    ap.add_argument("--no-save", action="store_true")
    args = ap.parse_args(argv)
    dirs = [Path(d) for d in args.data] if args.data else [d for d in DEFAULT_DIRS if d.is_dir()]
    result = run(dirs)
    if not result["datasets"]:
        raise SystemExit("No believed-normal datasets found.")
    _print(result)
    if not args.no_save:
        out = Path(args.out) if args.out else settings_from_env().results_dir / "baseline-check.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(result, indent=1) + "\n", encoding="utf-8")
        print(f"Saved {out}")
    return result


if __name__ == "__main__":
    main()
