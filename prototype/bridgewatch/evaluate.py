"""
Scores the detector against simulated exploits and clean traffic.

For each exploit kind, bridge and seed: generate 7 days of normal traffic
(the baseline), inject the exploit at a random time on day 8 or 9, run the
detector, and record
  detected         any alert on that bridge between the exploit's start and 1h after its end
  minutes_to_alert time from the first stolen dollar to the first alert
  lost_before      share of the eventually stolen funds already gone at the first alert

Separately, run clean traffic (no exploits) and count alerts per bridge-day
after warm-up: every one of those is a false alarm. The sweep repeats this
for several z-thresholds, so the team can pick the trade-off between
catching exploits early and how many false alarms a person would tolerate.

Real data (Objective 2.3, at most 1 false alarm per bridge per week): --real
feeds every believed-normal dataset under bridgewatch/data/ (30-day windows
with no known incident, e.g. data/normal/*.json[.gz]) through the detector on
the same simulated pipeline as the replay, and counts every alert after the
warm-up as a false alarm, per bridge per WEEK.

Run (from prototype/):
  python -m bridgewatch.evaluate            synthetic scorecard -> results/evaluation.json (about 15 s)
  python -m bridgewatch.evaluate --real     real normal periods  -> results/evaluation-real.json
"""

from __future__ import annotations
import argparse
import json
import random
import statistics
import time
from dataclasses import asdict, dataclass, replace
from pathlib import Path

from .config import DATA_DIR, detector_config, settings_from_env
from .detector import Detector, DetectorConfig
from .source import FileSource, find_datasets
from .synthetic import BRIDGES, INCIDENT_KINDS, SyntheticSource

DAY = 86_400
WEEK = 7 * DAY
TARGET_PER_WEEK = 1.0
T0 = 1_767_225_600.0   # 2026-01-01 00:00 UTC; any fixed start works, it just keeps runs reproducible


@dataclass
class Case:
    kind: str
    bridge: str
    seed: int
    detected: bool
    minutes_to_alert: float | None
    lost_before: float | None
    stolen_usd: float


def run_case(kind: str, bridge_id: str, seed: int, cfg: DetectorConfig, baseline_days: int = 7) -> Case:
    src = SyntheticSource(seed=seed)
    det = Detector(src.bridges, cfg)
    rng = random.Random(seed * 1_000 + INCIDENT_KINDS.index(kind))
    start = T0 + (baseline_days + rng.uniform(0, 2)) * DAY
    end = start + DAY
    for e in src.events_between(T0, start):
        det.observe(e)
    inc = src.inject(bridge_id, kind, start, escrow_usd=det.monitors[bridge_id].escrow)
    for e in src.events_between(start, end):
        det.observe(e)
    hits = [a for a in det.alerts if a.bridge == bridge_id and inc.start <= a.started <= inc.end + 3_600]
    if not hits:
        return Case(kind, bridge_id, seed, False, None, None, inc.stolen_usd)
    first = min(a.started for a in hits)
    lost = sum(e.amount_usd for e in inc.events if e.ts <= first)
    return Case(kind, bridge_id, seed, True, (first - inc.start) / 60, lost / inc.stolen_usd, inc.stolen_usd)


def false_alarms(cfg: DetectorConfig, days: int = 14, seed: int = 99) -> tuple[float, dict[str, int]]:
    """Alerts per bridge-day on clean traffic (all false alarms), and their count by rule."""
    src = SyntheticSource(seed=seed)
    det = Detector(src.bridges, cfg)
    for e in src.events_between(T0, T0 + days * DAY):
        det.observe(e)
    counted_days = (days - cfg.warmup / DAY) * len(src.bridges)
    by_rule: dict[str, int] = {}
    for a in det.alerts:
        by_rule[a.rule] = by_rule.get(a.rule, 0) + 1
    return (len(det.alerts) / counted_days if counted_days > 0 else 0.0), by_rule


def summarize(cases: list[Case]) -> dict:
    out = {}
    for kind in sorted({c.kind for c in cases}, key=INCIDENT_KINDS.index):
        cs = [c for c in cases if c.kind == kind]
        hit = [c for c in cs if c.detected]
        out[kind] = {
            "runs": len(cs),
            "detected": len(hit),
            "median_minutes_to_alert": round(statistics.median(c.minutes_to_alert for c in hit), 1) if hit else None,
            "median_lost_before_alert": round(statistics.median(c.lost_before for c in hit), 4) if hit else None,
        }
    return out


def evaluate(seeds: tuple[int, ...] = (1, 2, 3), thresholds: tuple[float, ...] = (4.0, 6.0, 8.0),
             cfg: DetectorConfig | None = None, clean_days: int = 14) -> dict:
    """Full scorecard at the chosen config, plus a threshold sweep. Takes about 15 s at the defaults."""
    cfg = cfg or detector_config()
    cases = [run_case(k, b.id, s, cfg) for k in INCIDENT_KINDS for b in BRIDGES for s in seeds]
    sweep = []
    for z in thresholds:
        c = replace(cfg, z_threshold=z)
        sc = [run_case(k, b.id, seeds[0], c) for k in INCIDENT_KINDS for b in BRIDGES]
        sweep.append({"z_threshold": z,
                      "detected": sum(x.detected for x in sc), "runs": len(sc),
                      "false_alarms_per_bridge_day": round(false_alarms(c, clean_days)[0], 3)})
    rate, by_rule = false_alarms(cfg, clean_days)
    return {
        "generated_at": time.time(),
        "config": asdict(cfg),
        "by_kind": summarize(cases),
        "false_alarms_per_bridge_day": round(rate, 3),
        "false_alarms_per_bridge_week": round(rate * 7, 3),
        "false_alarms_by_rule": by_rule,
        "clean_bridge_days": (clean_days - cfg.warmup / DAY) * len(BRIDGES),
        "sweep": sweep,
        "note": "Synthetic data only. These numbers describe the detector on generated traffic, "
                "not its performance on real bridges.",
    }


def normal_datasets(root: Path = DATA_DIR) -> list[FileSource]:
    """Every believed-normal dataset under root (no hack window)."""
    return [src for src in (FileSource(p) for p in find_datasets(root)) if src.kind == "normal"]


def evaluate_real(sources: list[FileSource], cfg: DetectorConfig | None = None) -> dict:
    """False alarms per bridge per week on real believed-normal data. Every alert after the
    warm-up is counted as a false alarm (alerts during warm-up are reported separately)."""
    from .replay import detect   # same simulated pipeline as the hack replay
    cfg = cfg or detector_config()
    rows = []
    for src in sources:
        det = detect(src, cfg)
        counted_from = src.start_ts + cfg.warmup
        counted = [a for a in det.alerts if a.started >= counted_from]
        weeks = max(src.end_ts - counted_from, 0) / WEEK
        by_rule: dict[str, int] = {}
        for a in counted:
            by_rule[a.rule] = by_rule.get(a.rule, 0) + 1
        rows.append({
            "key": src.key, "title": src.title, "vault": src.vault, "dataset": src.path.name,
            "days": round((src.end_ts - src.start_ts) / DAY, 1), "weeks_counted": round(weeks, 2),
            "transfers": len(src.data["transfers"]), "escrow_usd_at_start": round(src.escrow_usd_at_start, 2),
            "false_alarms": len(counted), "per_week": round(len(counted) / weeks, 3) if weeks else None,
            "meets_target": (len(counted) / weeks <= TARGET_PER_WEEK) if weeks else None,
            "by_rule": by_rule, "alerts_during_warmup": sum(a.started < counted_from for a in det.alerts),
            "alerts": [{"started": a.started, "rule": a.rule, "severity": a.severity, "message": a.message}
                       for a in counted],
        })
    total_weeks = sum(r["weeks_counted"] for r in rows)
    total = sum(r["false_alarms"] for r in rows)
    return {
        "generated_at": time.time(),
        "config": asdict(cfg),
        "target_per_bridge_week": TARGET_PER_WEEK,
        "datasets": rows,
        "overall": {"datasets": len(rows), "bridge_weeks": round(total_weeks, 2), "false_alarms": total,
                    "per_bridge_week": round(total / total_weeks, 3) if total_weeks else None,
                    "worst_per_week": max((r["per_week"] for r in rows if r["per_week"] is not None), default=None),
                    "all_meet_target": all(r["meets_target"] for r in rows) if rows else None},
        "note": "Real Ethereum data from believed-normal windows (no known incident). Every alert after the "
                "warm-up counts as a false alarm; an alert on a real but unreported incident would be counted too.",
    }


def _print_real(r: dict) -> None:
    print(f"False alarms per bridge per week on real normal data (target <= {r['target_per_bridge_week']:g})")
    for d in r["datasets"]:
        rate = "n/a" if d["per_week"] is None else f"{d['per_week']:.2f}"
        print(f"  {d['key']:32} {d['weeks_counted']:5.2f} weeks  {d['false_alarms']:3} alarms  {rate:>6}/week  {d['by_rule']}")
    o = r["overall"]
    print(f"Overall: {o['false_alarms']} false alarms in {o['bridge_weeks']} bridge-weeks = {o['per_bridge_week']} per bridge per week; "
          f"every dataset within target: {o['all_meet_target']}")


def main(argv: list[str] | None = None) -> dict:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--real", action="store_true", help="real believed-normal datasets instead of synthetic traffic")
    ap.add_argument("--data", default=str(DATA_DIR), help="folder searched for datasets (with --real)")
    ap.add_argument("--out", help="where to save the JSON result (default: results/evaluation[-real].json)")
    ap.add_argument("--no-save", action="store_true")
    args = ap.parse_args(argv)
    if args.real:
        sources = normal_datasets(Path(args.data))
        if not sources:
            raise SystemExit(f"No believed-normal datasets under {args.data} (run scripts/fetch_datasets.py).")
        result = evaluate_real(sources)
        _print_real(result)
        name = "evaluation-real.json"
    else:
        result = evaluate()
        print(json.dumps(result, indent=2))
        name = "evaluation.json"
    if not args.no_save:
        out = Path(args.out) if args.out else settings_from_env().results_dir / name
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(result, indent=1) + "\n", encoding="utf-8")
        print(f"Saved {out}")
    return result


if __name__ == "__main__":
    main()
