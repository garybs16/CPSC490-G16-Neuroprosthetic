"""
Replay real bridge hacks through the detector, using saved on-chain data.

Each hack case is a dataset file under bridgewatch/data/ (orbit-2023.json and
whatever scripts/fetch_datasets.py has added): about 14 days of the vault's
ordinary traffic (the baseline), then the hack, transfer by transfer, exactly
as live mode would have seen it.

Simulated clock. Live mode reads a block once it has 6 confirmations and polls
every 15 s, so here a transfer at block time t is seen at the first 15-second
poll after t + 6 x 12 s. That poll time is the alert's detected_at.

Reported per case
  first theft time       block time of the first theft (releases >= the case's
                         theft_min_usd inside its hack_window)
  first alert time       when the first alert would have been raised (detected_at)
  detection latency      first alert detected_at - first theft confirmed_at
                         (proposal: "evaluated within 1 minute after 6 confirmations")
  stolen before / after  USD of thefts whose block time is before / after the first
                         alert was raised (only "after" could have been acted on)
  false alarms           alerts more than an hour before the first theft

  python -m bridgewatch.replay                          # every hack case found, saved to results/replay.json
  python -m bridgewatch.replay bridgewatch/data/orbit-2023.json
  python -m bridgewatch.replay --no-save

Re-downloading a dataset: scripts/fetch_datasets.py.
"""

from __future__ import annotations
import argparse
import datetime as dt
import json
import math
import time
from dataclasses import asdict
from pathlib import Path

from .config import DATA_DIR, detector_config, settings_from_env
from .detector import Detector, DetectorConfig
from .models import Bridge
from .source import FileSource, find_datasets, to_flow_event

CONFIRMATIONS = 6
BLOCK_TIME_S = 12.0
POLL_SECONDS = 15.0
ORBIT_PATH = DATA_DIR / "orbit-2023.json"


def hack_cases(root: Path = DATA_DIR) -> list[FileSource]:
    """Every dataset under root that marks a hack window."""
    out = []
    for path in find_datasets(root):
        src = FileSource(path)
        if src.kind == "hack":
            out.append(src)
    return out


def detect(src: FileSource, cfg: DetectorConfig, confirmations: int = CONFIRMATIONS,
           block_time_s: float = BLOCK_TIME_S, poll_seconds: float = POLL_SECONDS) -> Detector:
    """Feed a dataset through a fresh detector on the simulated poll clock."""
    clock = {"now": src.start_ts}
    bridge = Bridge(src.key, src.title, (src.chain,), src.escrow_usd_at_start)
    det = Detector((bridge,), cfg, clock=lambda: clock["now"])
    det.monitors[src.key].first_ts = src.start_ts
    confirm_s = confirmations * block_time_s
    for t in src.transfers():
        e = to_flow_event(t, confirm_s)
        if e is None:
            continue
        clock["now"] = math.ceil(e.confirmed_at / poll_seconds) * poll_seconds
        det.observe(e)
    det.advance(src.end_ts)
    return det


def run(src: FileSource, cfg: DetectorConfig | None = None, confirmations: int = CONFIRMATIONS,
        block_time_s: float = BLOCK_TIME_S, poll_seconds: float = POLL_SECONDS) -> dict:
    """Replay one hack case and score the detector against its thefts."""
    cfg = cfg or detector_config()
    case = src.case
    lo, hi = case["hack_window"]
    theft_min = case.get("theft_min_usd", 1_000_000)
    transfers = src.transfers()
    thefts = [t for t in transfers if t.direction == "out" and lo <= t.block_number <= hi
              and t.amount_usd is not None and t.amount_usd >= theft_min]
    det = detect(src, cfg, confirmations, block_time_s, poll_seconds)
    confirm_s = confirmations * block_time_s

    first_theft = min((t.block_time for t in thefts), default=None)
    last_theft = max((t.block_time for t in thefts), default=None)
    if first_theft is None:
        hack_alerts, false_alarms = [], list(det.alerts)
    else:
        hack_alerts = [a for a in det.alerts if first_theft - 3_600 <= a.started <= last_theft + 3_600]
        false_alarms = [a for a in det.alerts if a.started < first_theft - 3_600]
    first_alert = min(hack_alerts, key=lambda a: (a.detected_at, a.id)) if hack_alerts else None
    stolen = sum(t.amount_usd for t in thefts)
    # A theft is "after" the alert only if it happened after the alert was raised
    after = [t for t in thefts if first_alert and t.block_time > first_alert.detected_at]
    latency = (first_alert.detected_at - (first_theft + confirm_s)) if first_alert else None
    return {
        "key": src.key,
        "case": src.title,
        "dataset": src.path.name,
        "vault": src.vault,
        "escrow_usd_at_start": round(src.escrow_usd_at_start, 2),
        "baseline_days": round((first_theft - src.start_ts) / 86_400, 1) if first_theft else None,
        "ordinary_transfers": len(transfers) - len(thefts),
        "stolen_usd_tracked": round(stolen, 2),
        "thefts": [{"ts": t.block_time, "token": t.token, "amount": t.amount, "usd": round(t.amount_usd, 2),
                    "to": t.counterparty, "tx": t.tx_hash} for t in thefts],
        "alerts": [asdict(a) for a in hack_alerts],
        "first_theft_ts": first_theft,
        "first_alert_ts": first_alert.started if first_alert else None,          # block time of the triggering transfer
        "first_alert_detected_at": first_alert.detected_at if first_alert else None,
        "first_alert_rule": first_alert.rule if first_alert else None,
        "seconds_from_first_theft_to_alert": (first_alert.started - first_theft) if first_alert else None,
        "detection_latency_s": round(latency, 1) if latency is not None else None,
        "latency_target_s": 60,
        "stolen_before_alert_usd": round(stolen - sum(t.amount_usd for t in after), 2) if first_alert else None,
        "stolen_after_alert_usd": round(sum(t.amount_usd for t in after), 2) if first_alert else None,
        "minutes_of_warning_for_later_thefts": [round((t.block_time - first_alert.detected_at) / 60, 1) for t in after],
        "false_alarms_during_baseline": len(false_alarms),
        "false_alarms": [{"started": a.started, "rule": a.rule, "severity": a.severity, "message": a.message}
                         for a in false_alarms],
        "source": src.data.get("source", ""),
        "fetched": src.data.get("fetched", ""),
        "price_note": src.data.get("price_note", ""),
    }


def run_all(sources: list[FileSource], cfg: DetectorConfig | None = None) -> dict:
    cfg = cfg or detector_config()
    return {"generated_at": time.time(),
            "config": asdict(cfg),
            "simulated_pipeline": {"confirmations": CONFIRMATIONS, "block_time_s": BLOCK_TIME_S,
                                   "poll_seconds": POLL_SECONDS},
            "cases": [run(s, cfg) for s in sources]}


def _t(ts: float | None) -> str:
    return dt.datetime.fromtimestamp(ts, dt.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC") if ts else "-"


def _print(r: dict) -> None:
    print(f"\n== {r['case']} ({r['key']})")
    print(f"   vault {r['vault']}, tracked escrow at start ${r['escrow_usd_at_start']:,.0f}; "
          f"{r['baseline_days']} days of baseline, {r['ordinary_transfers']} ordinary transfers")
    print(f"   thefts: {len(r['thefts'])}, ${r['stolen_usd_tracked']:,.0f} tracked")
    print(f"   first theft      {_t(r['first_theft_ts'])}")
    if r["first_alert_detected_at"]:
        print(f"   first alert      {_t(r['first_alert_detected_at'])}  ({r['first_alert_rule']}, "
              f"on the transfer at {_t(r['first_alert_ts'])})")
        print(f"   detection latency {r['detection_latency_s']:.0f} s after the first theft was confirmed "
              f"(target <= {r['latency_target_s']} s)")
        print(f"   stolen before the alert ${r['stolen_before_alert_usd']:,.0f}; after it ${r['stolen_after_alert_usd']:,.0f}")
    else:
        print("   first alert      NONE: the detector missed this hack")
    print(f"   false alarms before the hack: {r['false_alarms_during_baseline']}")
    for a in r["false_alarms"][:5]:
        print(f"     {_t(a['started'])} {a['severity']:8} {a['rule']}: {a['message']}")


def main(argv: list[str] | None = None) -> dict:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("files", nargs="*", help="dataset files to replay (default: every hack case under bridgewatch/data)")
    ap.add_argument("--out", help="where to save the JSON result (default: results/replay.json)")
    ap.add_argument("--no-save", action="store_true")
    args = ap.parse_args(argv)
    sources = [FileSource(f) for f in args.files] if args.files else hack_cases()
    sources = [s for s in sources if s.kind == "hack"]
    if not sources:
        raise SystemExit("No hack cases found (a case needs a hack_window).")
    result = run_all(sources)
    for r in result["cases"]:
        _print(r)
    if not args.no_save:
        out = Path(args.out) if args.out else settings_from_env().results_dir / "replay.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(result, indent=1) + "\n", encoding="utf-8")
        print(f"\nSaved {out}")
    return result


if __name__ == "__main__":
    main()
