"""
Every CURRENT-detector false alarm, mapped to the release that triggered it, with
context, and what the recommended policy (REC in sweep.py) does with the same release.

  PYTHONDONTWRITEBYTECODE=1 python fa_examples.py --prototype <copy of prototype/>
-> out/fa-examples.csv   (one row per current alert in a false-alarm period)
   out/rec-pages.csv     (every REC page in a false-alarm period, with full context)
"""
from __future__ import annotations

import csv

import common
import engine
from policy import levels
from sweep import REC, write_csv


def main():
    args = common.parser(__doc__).parse_args()
    common.setup(args)
    from bridgewatch.detector import DetectorConfig
    from bridgewatch.replay import detect
    rows, recp = [], []
    for ds in common.load_all(args):
        per = ds.fa_period()
        if not per:
            continue
        lo, hi = per
        stream = engine.cached_stream(ds)
        lv = {(r["ts"], r["tx"], r["token"], round(r["usd"], 6)): (l, f) for r, l, f in levels(stream, REC, ds.design)}
        by_ts = {}
        for r in stream:
            by_ts.setdefault(r["ts"], []).append(r)
        role = "pre-hack" if ds.kind == "hack" else ds.role
        for a in detect(ds.src, DetectorConfig()).alerts:
            if not (lo <= a.started < hi):
                continue
            cands = by_ts.get(a.started, [])
            r = max(cands, key=lambda x: x["usd"]) if cands else None
            l, f = lv.get((r["ts"], r["tx"], r["token"], round(r["usd"], 6)), (0, frozenset())) if r else (0, frozenset())
            rows.append({"key": ds.key, "design": ds.design, "role": role, "utc": common.fmt_ts(a.started),
                         "rule": a.rule, "severity": a.severity, "message": a.message,
                         "tx": r["tx"] if r else "", "token": r["token"] if r else "",
                         "release_usd": round(r["usd"]) if r else "", "pct_tvl": round(100 * r["share_tvl"], 2) if r else "",
                         "net1h_pct_tvl": round(100 * r["net1h_share"], 2) if r else "",
                         "recipient": r["cp"] if r else "", "recipient_fresh": r["fresh"] if r else "",
                         "recipient_ever_deposited": (r["never_dep"] is False) if r else "",
                         "releases_in_10min": r["n_out10"] if r else "",
                         "rec_level": {0: "none", 1: "warning", 2: "PAGE"}[l], "rec_families": "+".join(sorted(f))})
        last = -1e18
        for r, l, f in levels(stream, REC, ds.design):
            if l == 2 and lo <= r["ts"] < hi:
                recp.append({"key": ds.key, "design": ds.design, "role": role, "utc": common.fmt_ts(r["ts"]),
                             "new_incident": r["ts"] - last >= 3_600, "tx": r["tx"], "token": r["token"],
                             "release_usd": round(r["usd"]), "pct_tvl": round(100 * r["share_tvl"], 2),
                             "net1h_pct_tvl": round(100 * r["net1h_share"], 2), "recipient": r["cp"],
                             "recipient_fresh": r["fresh"], "families": "+".join(sorted(f))})
                last = r["ts"]
    write_csv(common.OUT / "fa-examples.csv", rows)
    write_csv(common.OUT / "rec-pages.csv", recp)
    print(len(rows), "current false alarms;", sum(x["rec_level"] == "PAGE" for x in rows), "of them page under REC;",
          sum(x["rec_level"] == "warning" for x in rows), "become warnings")


if __name__ == "__main__":
    main()
