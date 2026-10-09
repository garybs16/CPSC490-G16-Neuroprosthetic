"""
Normal-traffic statistics per window -> 04-analysis/normal-stats.csv, plus
out/largest-legit-outflows.csv (top legitimate releases per window, with context)
and out/seasonality.json.

Windows: the 15 normal / stress-normal files, and (role "pre-hack") the pre-hack
baseline of every hack file (warm-up to 1 h before the first theft).
False alarms use the CURRENT prototype detector (default DetectorConfig), counted
after the 3-day warm-up, exactly as bridgewatch.evaluate --real does.

  PYTHONDONTWRITEBYTECODE=1 python normal_stats.py --prototype <copy of prototype/>
"""
from __future__ import annotations

import csv
import datetime as dt
import json
import statistics
from collections import Counter, defaultdict

import common
import engine
from common import WEEK, fmt_ts


def pct(vals, q):
    if not vals:
        return 0.0
    vals = sorted(vals)
    i = min(len(vals) - 1, max(0, int(round(q / 100 * (len(vals) - 1)))))
    return vals[i]


def current_alerts(ds):
    from bridgewatch.detector import DetectorConfig
    from bridgewatch.replay import detect
    return detect(ds.src, DetectorConfig()).alerts


def main():
    args = common.parser(__doc__).parse_args()
    common.setup(args)
    rows, big, season = [], [], {}
    for ds in common.load_all(args):
        p = ds.fa_period()
        if not p:
            continue
        lo, hi = p
        weeks = (hi - lo) / WEEK
        days = weeks * 7
        feats = [r for r in engine.cached_stream(ds) if lo <= r["ts"] < hi]
        trs = [t for t in ds.transfers if lo <= t.block_time < hi and t.amount_usd is not None]
        outs = [t for t in trs if t.direction == "out"]
        ins = [t for t in trs if t.direction == "in"]
        sizes = [t.amount_usd for t in outs]
        # seasonality: outflow USD and count by hour of day and weekday
        by_h, by_hc, by_wd = defaultdict(float), Counter(), defaultdict(float)
        for t in outs:
            d = dt.datetime.fromtimestamp(t.block_time, dt.timezone.utc)
            by_h[d.hour] += t.amount_usd
            by_hc[d.hour] += 1
            by_wd[d.weekday()] += t.amount_usd
        tot = sum(by_h.values()) or 1.0
        hshare = [by_h[h] / tot for h in range(24)]
        cnt_tot = sum(by_hc.values()) or 1
        hc_share = [by_hc[h] / cnt_tot for h in range(24)]
        wkend = (by_wd[5] + by_wd[6]) / 2
        wkday = sum(by_wd[i] for i in range(5)) / 5
        season[ds.key] = {"hour_usd_share": [round(x, 4) for x in hshare], "hour_count_share": [round(x, 4) for x in hc_share],
                          "weekday_usd": {d: round(by_wd[i]) for i, d in enumerate("Mon Tue Wed Thu Fri Sat Sun".split())}}
        # burstiness: 10-minute release counts
        nb = int((hi - lo) // 600) or 1
        cnts = Counter(int((t.block_time - lo) // 600) for t in outs)
        series = [cnts.get(i, 0) for i in range(nb)]
        mean_c = statistics.mean(series)
        fano = (statistics.pvariance(series) / mean_c) if mean_c > 0 else 0.0
        # current detector false alarms
        al = [a for a in current_alerts(ds) if lo <= a.started < hi]
        by_rule = Counter(a.rule for a in al)
        newcp = [r for r in feats if r["new_cp"] is True]
        known = [r for r in feats if r["new_cp"] is not None]
        row = {
            "key": ds.key, "role": "pre-hack" if ds.kind == "hack" else ds.role, "design": ds.design,
            "window_utc": f"{fmt_ts(lo)[:10]} to {fmt_ts(hi)[:10]}", "weeks_counted": round(weeks, 2),
            "tracked_tvl_start_usd": round(ds.escrow0),
            "releases_per_day": round(len(outs) / days, 1), "deposits_per_day": round(len(ins) / days, 1),
            "release_usd_per_day": round(sum(sizes) / days),
            "release_p50_usd": round(pct(sizes, 50)), "release_p90_usd": round(pct(sizes, 90)),
            "release_p99_usd": round(pct(sizes, 99)), "release_max_usd": round(max(sizes) if sizes else 0),
            "max_single_release_pct_tvl": round(100 * max((r["share_tvl"] for r in feats), default=0), 2),
            "n_release_ge_1pct_tvl": sum(r["share_tvl"] >= 0.01 for r in feats),
            "n_release_ge_2pct_tvl": sum(r["share_tvl"] >= 0.02 for r in feats),
            "n_release_ge_5pct_tvl": sum(r["share_tvl"] >= 0.05 for r in feats),
            "n_release_ge_10pct_tvl": sum(r["share_tvl"] >= 0.10 for r in feats),
            "n_release_ge_5pct_tvl_and_1M": sum(r["share_tvl"] >= 0.05 and r["usd"] >= 1e6 for r in feats),
            "max_net_1h_outflow_pct_tvl": round(100 * max((r["net1h_share"] for r in feats), default=0), 2),
            "max_gross_10m_outflow_pct_tvl": round(100 * max((r["gross10_share"] for r in feats), default=0), 2),
            "max_drawdown_24h_pct": round(100 * max((r["dd24"] for r in feats), default=0), 2),
            "peak_hour_usd_share": round(max(hshare), 3), "peak_hour_utc": hshare.index(max(hshare)),
            "hour_count_cv": round(statistics.pstdev(hc_share) / statistics.mean(hc_share), 2) if cnt_tot > 1 else "",
            "weekend_to_weekday_usd": round(wkend / wkday, 2) if wkday else "",
            "fano_10min_counts": round(fano, 1), "max_releases_in_10min": max(series) if series else 0,
            "share_releases_to_new_recipient": round(len(newcp) / len(known), 3) if known else "",
            "new_recipient_ge_1pct_tvl_and_250k_per_week": round(sum(r["share_tvl"] >= 0.01 and r["usd"] >= 250_000 for r in newcp) / weeks, 2),
            "dust_lt_1k_to_new_recipient_per_week": round(sum(r["usd"] < 1_000 for r in newcp) / weeks, 1),
            "current_false_alarms": len(al), "current_fa_per_week": round(len(al) / weeks, 2),
            "fa_outflow_spike": by_rule.get("outflow_spike", 0), "fa_withdrawal_burst": by_rule.get("withdrawal_burst", 0),
            "fa_escrow_drain": by_rule.get("escrow_drain", 0), "fa_large_withdrawal": by_rule.get("large_withdrawal", 0),
        }
        rows.append(row)
        # largest legitimate releases, with context
        top = sorted(feats, key=lambda r: -r["share_tvl"])[:5]
        intimes = [(t.block_time, t.amount_usd, t.counterparty.lower()) for t in ins]
        for r in top:
            back = sum(u for (ts, u, c) in intimes if abs(ts - r["ts"]) <= 3_600)
            same_cp_in = sum(u for (ts, u, c) in intimes if c == r["cp"] and abs(ts - r["ts"]) <= 86_400)
            big.append({"key": ds.key, "role": row["role"], "design": ds.design, "utc": fmt_ts(r["ts"]),
                        "tx": r["tx"], "token": r["token"], "usd": round(r["usd"]),
                        "pct_tvl": round(100 * r["share_tvl"], 2), "pct_token_balance": round(100 * min(r["tok_share"], 9.99), 1),
                        "recipient": r["cp"] or "(weth unwrap)", "recipient_new": r["new_cp"], "recipient_ever_deposited": (r["never_dep"] is False),
                        "deposits_within_1h_usd": round(back), "same_recipient_deposits_24h_usd": round(same_cp_in),
                        "net_1h_pct_tvl": round(100 * r["net1h_share"], 2), "drawdown_24h_pct": round(100 * r["dd24"], 2)})
    cols = list(dict.fromkeys(k for r in rows for k in r))
    out = common.HERE.parent / "normal-stats.csv"
    with open(out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)
    with open(common.OUT / "largest-legit-outflows.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(big[0]))
        w.writeheader()
        w.writerows(big)
    (common.OUT / "seasonality.json").write_text(json.dumps(season, indent=1) + "\n")
    for r in rows:
        print({k: r[k] for k in ("key", "role", "design", "releases_per_day", "max_single_release_pct_tvl",
                                  "max_net_1h_outflow_pct_tvl", "n_release_ge_5pct_tvl_and_1M", "fano_10min_counts",
                                  "share_releases_to_new_recipient", "new_recipient_ge_1pct_tvl_and_250k_per_week",
                                  "current_fa_per_week")})
    print("wrote", out)


if __name__ == "__main__":
    main()
