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

Run:  python -m bridgewatch.evaluate      (from prototype/)
"""

from __future__ import annotations
import random
import statistics
from dataclasses import dataclass, replace

from .detector import Detector, DetectorConfig
from .synthetic import BRIDGES, INCIDENT_KINDS, SyntheticSource

DAY = 86_400
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
    """Full scorecard at the chosen config, plus a threshold sweep. Takes a minute at the defaults."""
    cfg = cfg or DetectorConfig()
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
        "config": {k: v for k, v in cfg.__dict__.items()},
        "by_kind": summarize(cases),
        "false_alarms_per_bridge_day": round(rate, 3),
        "false_alarms_by_rule": by_rule,
        "clean_bridge_days": (clean_days - cfg.warmup / DAY) * len(BRIDGES),
        "sweep": sweep,
        "note": "Synthetic data only. These numbers describe the detector on generated traffic, "
                "not its performance on real bridges.",
    }


if __name__ == "__main__":
    import json
    print(json.dumps(evaluate(), indent=2))
