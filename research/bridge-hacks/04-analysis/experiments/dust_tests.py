"""
"Test then drain": how often does a never-seen recipient get a dust release (< $1,000)
and then, within 24 h, a large release (>= 1% of TVL and >= $250K)?

Seen before the theft in Orbit 2023 (5 dust releases to the 4 later theft recipients,
27 min to 2 h 38 min earlier) and Multichain 2023 ($2 test, 1 h 49 min earlier).

  PYTHONDONTWRITEBYTECODE=1 python dust_tests.py --prototype <copy of prototype/>
-> out/dust-tests.json
"""
from __future__ import annotations

import json

import common
from common import WEEK

WETH = "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2"


def main():
    args = common.parser(__doc__).parse_args()
    common.setup(args)
    res = {"normal_and_prehack": {}, "hacks": {}}
    tot_w = tot_dust = tot_hits = 0
    for ds in common.load_all(args):
        esc = ds.escrow0
        first_seen, dust_at = {}, {}
        hits = []
        n_dust = 0
        per = ds.fa_period()
        for t in ds.transfers:
            if t.amount_usd is None:
                continue
            cp = t.counterparty.lower()
            if t.direction == "in":
                esc += t.amount_usd
                first_seen.setdefault(cp, t.block_time)
                continue
            before = esc
            esc -= t.amount_usd
            if cp == WETH:
                continue
            if cp not in first_seen:
                first_seen[cp] = t.block_time
                if t.amount_usd < 1_000:
                    dust_at[cp] = t.block_time
                    if per and per[0] <= t.block_time < per[1]:
                        n_dust += 1
                continue
            if cp in dust_at and t.block_time - dust_at[cp] <= 86_400 and t.amount_usd >= max(0.01 * before, 250_000):
                hits.append({"utc": common.fmt_ts(t.block_time), "usd": round(t.amount_usd), "tx": t.tx_hash,
                             "lead_min": round((t.block_time - dust_at[cp]) / 60, 1), "theft": ds.is_theft(t)})
        if ds.kind == "hack":
            res["hacks"][ds.key] = [h for h in hits if h["theft"]]
        if per:
            fa_hits = [h for h in hits if not h["theft"] and per[0] <= common.utc(h["utc"]) < per[1]]
            w = (per[1] - per[0]) / WEEK
            res["normal_and_prehack"][ds.key] = {"weeks": round(w, 2), "dust_to_new_recipient": n_dust,
                                                 "dust_then_large_within_24h": fa_hits}
            tot_w += w
            tot_dust += n_dust
            tot_hits += len(fa_hits)
    res["summary"] = {"bridge_weeks": round(tot_w, 1), "dust_releases_to_new_recipients": tot_dust,
                      "per_bridge_week": round(tot_dust / tot_w, 2),
                      "dust_then_large_in_normal_traffic": tot_hits,
                      "dust_then_large_per_bridge_week": round(tot_hits / tot_w, 3),
                      "hack_cases_with_the_pattern": [k for k, v in res["hacks"].items() if v]}
    (common.OUT / "dust-tests.json").write_text(json.dumps(res, indent=1) + "\n")
    print(json.dumps(res["summary"], indent=1))
    for k, v in res["hacks"].items():
        if v:
            print(k, v)


if __name__ == "__main__":
    main()
