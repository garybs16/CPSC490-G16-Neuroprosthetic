"""
Speed floors: the smallest share of tracked theft that ANY vault-outflow detector
could have prevented, given the pipeline, and the effect of native-ETH visibility.

For each hack case and confirmation depth k (0 = alert at inclusion, provisional):
  floor_k = share of tracked theft whose block time <= the poll that first sees the
            first theft after k confirmations (12 s blocks, 15 s polls)
Native-ETH sensitivity: where native ETH left first (poly-2021, heco-2023, ronin-2024)
or in the same tx, an alert on the native transfer moves the earliest alert. Shares
are computed over tracked + native theft.

  PYTHONDONTWRITEBYTECODE=1 python floors.py --prototype <copy of prototype/>
-> out/floors.csv, out/floors.json
"""
from __future__ import annotations

import csv
import json
import math

import common
from common import NATIVE_ETH, utc

DEPTHS = (0, 1, 2, 6, 12, 64)   # 64 ~ Ethereum finality (2 epochs, ~12.8 min)


def seen_at(ts: float, k: int) -> float:
    return math.ceil((ts + k * 12.0) / 15.0) * 15.0


def main():
    args = common.parser(__doc__).parse_args()
    common.setup(args)
    rows = []
    for ds in common.load_all(args):
        if ds.kind != "hack" or not ds.thefts:
            continue
        stolen = ds.stolen_usd()
        r = {"key": ds.key, "tracked_stolen_usd": round(stolen)}
        for k in DEPTHS:
            t0 = seen_at(ds.first_theft_ts, k)
            r[f"floor_{k}conf"] = round(sum(t.amount_usd for t in ds.thefts if t.block_time <= t0) / stolen, 3)
        nat = NATIVE_ETH.get(ds.key)
        if nat:
            nts, eth, px = utc(nat[0]), nat[1], nat[2]
            nusd = eth * px
            total = stolen + nusd
            first_any = min(nts, ds.first_theft_ts)
            # without native visibility: alert at the tracked floor (6 conf); native counted as gone if earlier
            t_tracked = seen_at(ds.first_theft_ts, 6)
            gone_tracked = sum(t.amount_usd for t in ds.thefts if t.block_time <= t_tracked) + (nusd if nts <= t_tracked else 0)
            t_native = seen_at(first_any, 6)
            gone_native = sum(t.amount_usd for t in ds.thefts if t.block_time <= t_native) + (nusd if nts <= t_native else 0)
            r.update({"native_usd": round(nusd), "native_lead_min": round((ds.first_theft_ts - nts) / 60, 1),
                      "share_gone_at_alert_tokens_only_view": round(gone_tracked / total, 3),
                      "share_gone_at_alert_with_native_view": round(gone_native / total, 3),
                      "minutes_earlier_with_native": round((t_tracked - t_native) / 60, 1)})
        rows.append(r)
    cols = list(dict.fromkeys(k for r in rows for k in r))
    with open(common.OUT / "floors.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)
    (common.OUT / "floors.json").write_text(json.dumps(rows, indent=1) + "\n")
    for r in rows:
        print(r)


if __name__ == "__main__":
    main()
