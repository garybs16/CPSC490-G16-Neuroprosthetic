"""
Threshold sweeps, rule combinations, Pareto front, leave-one-out and a time split.

  PYTHONDONTWRITEBYTECODE=1 python sweep.py --prototype <copy of prototype/>

Outputs (experiments/out/):
  baseline-check.json      the "current" policy re-implemented here vs bridgewatch.replay / evaluate
  single-signal.csv        each signal family ALONE paging, over a threshold grid (separability)
  combos.csv               combination policies (named) with all metrics
  grid.csv                 the combination grid used for the Pareto front
  pareto.csv               non-dominated (pages/bridge-week, excess loss, misses) points of grid.csv
  per-case.csv             per hack case: floor and stolen-before share for the main policies
  per-window.csv           per window: pages / week for the main policies
  loo.json                 leave-one-hack-out choice of the grid config, scored on the held-out case
  time-split.json          choose on 2021-2023 data, score on 2024-2026 data
"""
from __future__ import annotations

import csv
import itertools
import json
from dataclasses import replace

import common
import engine
from policy import P, score, summary


def write_csv(path, rows):
    if not rows:
        return
    cols = list(dict.fromkeys(k for r in rows for k in r))
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)


CURRENT = P(label="current (any rule pages)")
OFF = dict(huge=None, size=None, fresh=None, net1h=None, net10=None, dd24=None, conc=None, multi=None, crowd=None,
           spike=None, burst=None)


def single_family_grid():
    g = []
    for s in (0.01, 0.02, 0.05, 0.10, 0.20):
        for fl in (250_000, 1_000_000):
            g.append(P(**{**OFF, "size": (s, fl)}, label=f"size >= {s:.0%} TVL & ${fl/1e6:g}M"))
    for s in (0.005, 0.01, 0.02, 0.05, 0.10):
        for fl in (250_000, 1_000_000):
            g.append(P(**{**OFF, "fresh": (s, fl)}, label=f"fresh recipient & >= {s:.1%} TVL & ${fl/1e6:g}M"))
            g.append(P(**{**OFF, "fresh": (s, fl)}, unknown_recipient_is_fresh=True,
                       label=f"fresh(+unknown) & >= {s:.1%} TVL & ${fl/1e6:g}M"))
    for s in (0.02, 0.05, 0.10, 0.20):
        for fl in (0, 1_000_000):
            g.append(P(**{**OFF, "net1h": (s, fl)}, label=f"net 1h >= {s:.0%} TVL & ${fl/1e6:g}M"))
            g.append(P(**{**OFF, "net10": (s, fl)}, label=f"net 10m >= {s:.0%} TVL & ${fl/1e6:g}M"))
    for s in (0.05, 0.10, 0.20, 0.30):
        g.append(P(**{**OFF, "dd24": (s, 1_000_000)}, label=f"drawdown 24h >= {s:.0%} & $1M"))
    for s in (0.02, 0.05, 0.10):
        g.append(P(**{**OFF, "conc": (s, 1_000_000)}, label=f"one recipient 1h >= {s:.0%} TVL & $1M"))
    for k in (2, 3):
        g.append(P(**{**OFF, "multi": k}, label=f">= {k} tokens drained >= 20% in 10m"))
    for k in (3, 5, 10, 20):
        g.append(P(**{**OFF, "crowd": k}, label=f">= {k} new recipients in 10m"))
    for z in (4, 6, 8, 10, 15):
        for fl in (100_000, 1_000_000):
            g.append(P(**{**OFF, "spike": (z, fl, 0.005)}, label=f"outflow_spike z>={z} floor ${fl/1e6:g}M"))
    for z in (6, 10):
        for n in (12, 30):
            g.append(P(**{**OFF, "burst": (z, n)}, label=f"withdrawal_burst z>={z} n>={n}"))
    # the prototype's own rules one at a time at their defaults
    g.append(P(**{**OFF, "size": (0.02, 1_000_000)}, label="proto large_withdrawal alone (2% & $1M)"))
    g.append(P(**{**OFF, "net1h": (0.05, 0)}, label="proto escrow_drain alone (net 1h 5%)"))
    return g


REC = P(**{**OFF, "huge": (0.50, 250_000), "size": (0.10, 1_000_000), "fresh": (0.01, 250_000),
           "net1h": (0.10, 250_000), "conc": (0.05, 250_000), "crowd": 10, "spike": (10.0, 1_000_000, 0.005)},
        mode="combo", strong=("huge", "size"), window_s=1_800, unknown_recipient_is_fresh=True,
        pool_ignore_known_lp=True, pool_profile=True,
        label="REC: recommended (huge|size page alone; else >=2 of fresh/net1h/conc/crowd/spike in 30 min; pool profile)")


def named_combos():
    """The policies compared in experiments.md (all use the same signals; only paging differs)."""
    base = dict(OFF)
    rec = P(**{**base, "size": (0.10, 1_000_000), "fresh": (0.01, 250_000), "net1h": (0.10, 1_000_000),
               "multi": 2, "crowd": 5, "spike": (10.0, 1_000_000, 0.005), "conc": (0.05, 1_000_000)},
            mode="combo", strong=("size",), window_s=1_800, unknown_recipient_is_fresh=True,
            pool_ignore_known_lp=True, label="R: first draft (size strong; >=2 of fresh/net1h/multi/crowd5/spike/conc, $1M floors)")
    return [
        CURRENT,
        P(spike=(6.0, 1_000_000, 0.005), label="current + $1M spread floor"),
        P(spike=(10.0, 1_000_000, 0.005), burst=(10.0, 30), label="current, z 10, $1M floor, burst n30"),
        P(size=(0.05, 1_000_000), net1h=(0.10, 1_000_000), spike=(10.0, 1_000_000, 0.005), burst=(10.0, 30),
          label="current rules, all thresholds raised"),
        P(**{**base, "size": (0.02, 1_000_000), "net1h": (0.05, 0), "spike": (6.0, 100_000, 0.005),
             "burst": (6.0, 12)}, mode="combo", strong=(), label="current rules, page only if >=2 agree"),
        P(**{**base, "fresh": (0.01, 250_000)}, unknown_recipient_is_fresh=True,
          label="fresh recipient >=1% & $250K alone"),
        rec,
        replace(rec, multi=None, conc=None, label="R without multi-token / concentration"),
        replace(rec, huge=(0.5, 250_000), strong=("size", "huge"), label="R + huge (>=50% TVL & $250K) pages alone"),
        REC,
        replace(REC, pool_profile=False, label="REC without pool profile"),
        replace(REC, pool_profile=False, pool_ignore_known_lp=False, label="REC without pool profile or LP suppression"),
        replace(REC, window_s=600, label="REC, 10-minute combination window"),
        replace(REC, window_s=3_600, label="REC, 60-minute combination window"),
        replace(REC, fresh=None, label="REC without fresh-recipient signal"),
        replace(REC, unknown_recipient_is_fresh=False, label="REC, unknown (weth-unwrap) recipient not fresh"),
        replace(REC, spike=None, label="REC without seasonal spike"),
        replace(REC, spike=(6.0, 100_000, 0.005), label="REC with the prototype spike (z 6, $100K floor)"),
        replace(REC, crowd=None, label="REC without crowd"),
        replace(REC, crowd=None, spike=None, label="REC without crowd and spike"),
        replace(REC, conc=None, label="REC without one-recipient concentration"),
        replace(REC, multi=2, label="REC + multi-token family"),
        replace(REC, huge=None, strong=("size",), label="REC without huge (small vaults)"),
        replace(REC, size=(0.05, 1_000_000), label="REC, size strong at 5%"),
        replace(REC, size=(0.20, 1_000_000), label="REC, size strong at 20%"),
        replace(REC, strong=(), label="REC, nothing pages alone (>=2 only)"),
        replace(REC, strong=("huge", "size", "fresh"), label="REC, fresh also pages alone"),
        replace(REC, fresh=(0.005, 250_000), label="REC, fresh at 0.5%"),
        replace(REC, fresh=(0.02, 1_000_000), label="REC, fresh at 2% & $1M"),
        replace(REC, net1h=(0.05, 250_000), label="REC, net1h at 5%"),
        replace(REC, net1h=(0.20, 1_000_000), label="REC, net1h at 20% & $1M"),
    ]


def combo_grid():
    out = []
    for size_s, fresh_s, net_s, crowd, spike_z, win, fl in itertools.product(
            (0.05, 0.10, 0.20, None), (0.005, 0.01, 0.02, None), (0.05, 0.10, 0.20), (5, 10, None),
            (6.0, 10.0, None), (600, 1_800), (250_000, 1_000_000)):
        p = P(**{**OFF, "huge": (0.5, 250_000), "size": (size_s, 1_000_000) if size_s else None,
                 "fresh": (fresh_s, fl) if fresh_s else None, "net1h": (net_s, fl),
                 "multi": 2, "crowd": crowd, "spike": (spike_z, 1_000_000, 0.005) if spike_z else None,
                 "conc": (0.05, fl)},
              mode="combo", strong=("size", "huge") if size_s else ("huge",), window_s=win,
              unknown_recipient_is_fresh=True, pool_ignore_known_lp=True,
              label=f"size {size_s} fresh {fresh_s} net1h {net_s} crowd {crowd} spike {spike_z} win {win} floor {fl:g}")
        out.append(p)
    return out


def pareto(rows, keys=("pages_per_bridge_week_all", "excess_loss_musd", "misses")):
    front = []
    for r in rows:
        dom = any(all(o[k] <= r[k] for k in keys) and any(o[k] < r[k] for k in keys) for o in rows)
        if not dom:
            front.append(r)
    return sorted(front, key=lambda r: r[keys[0]])


def main():
    args = common.parser(__doc__).parse_args()
    common.setup(args)
    dss = common.load_all(args)
    streams = {ds.key: engine.cached_stream(ds) for ds in dss}
    floors = {r["key"]: r["floor_6conf"] for r in json.loads((common.OUT / "floors.json").read_text())}
    O = common.OUT

    # 0. the current policy here vs the prototype's own replay/evaluate (sanity check)
    from bridgewatch.detector import DetectorConfig
    from bridgewatch.replay import run
    cur = score(dss, streams, floors, CURRENT)
    check = []
    for ds in dss:
        if ds.kind == "hack" and ds.thefts:
            rr = run(ds.src, DetectorConfig())
            check.append({"key": ds.key, "replay_before": rr["stolen_before_alert_usd"],
                          "here_before": round(cur.cases[ds.key].get("before_usd", -1), 2)})
    (O / "baseline-check.json").write_text(json.dumps({"cases": check, "summary": summary(cur)}, indent=1))

    # 1. single families
    single = []
    for p in single_family_grid():
        s = score(dss, streams, floors, p)
        single.append(summary(s))
    write_csv(O / "single-signal.csv", single)

    # 2. named combos
    combos, scores = [], {}
    for p in named_combos():
        s = score(dss, streams, floors, p)
        scores[p.label] = s
        combos.append(summary(s))
    write_csv(O / "combos.csv", combos)

    # per case / per window for the main policies
    main_labels = [c["policy"] for c in combos]
    pc = []
    for key in [k for k in scores[CURRENT.label].cases]:
        row = {"key": key, "floor_share": round(floors[key], 3)}
        for lab in [CURRENT.label, REC.label, "current, z 10, $1M floor, burst n30", "current rules, page only if >=2 agree"]:
            c = scores[lab].cases[key]
            row[f"{lab} | before_share"] = round(c["before_share"], 3) if c["detected"] else "MISS"
            row[f"{lab} | families"] = "+".join(c.get("families", []))
        pc.append(row)
    write_csv(O / "per-case.csv", pc)
    pw = []
    for key, v in scores[CURRENT.label].fa.items():
        row = {"key": key, "design": v[3], "role": v[4], "weeks": round(v[2], 2)}
        for lab in [CURRENT.label, "current, z 10, $1M floor, burst n30", "current rules, page only if >=2 agree",
                    REC.label, "REC without pool profile"]:
            vv = scores[lab].fa[key]
            row[lab] = round(vv[0] / vv[2], 2) if vv[2] else ""
        pw.append(row)
    write_csv(O / "per-window.csv", pw)

    # per design / role page rates for current vs REC
    pd = []
    for lab in [CURRENT.label, "current rules, page only if >=2 agree", REC.label]:
        sc = scores[lab]
        for grp in ("lockbox", "rollup", "oft-adapter", "pool", "mpc"):
            for role in ("normal", "stress", "pre-hack"):
                sel = [v for v in sc.fa.values() if v[3] == grp and v[4] == role]
                if not sel:
                    continue
                w = sum(v[2] for v in sel)
                pd.append({"policy": lab, "design": grp, "role": role, "windows": len(sel), "bridge_weeks": round(w, 2),
                           "pages": sum(v[0] for v in sel), "pages_per_bridge_week": round(sum(v[0] for v in sel) / w, 3),
                           "warnings_per_bridge_week": round(sum(v[1] for v in sel) / w, 3)})
    write_csv(O / "per-design.csv", pd)

    # 3. grid + Pareto
    grid_scores = []
    grid = combo_grid()
    for p in grid:
        s = score(dss, streams, floors, p)
        row = summary(s)
        row["misses"] = len(s.cases) - s.detected()
        row["_p"] = p
        row["_s"] = s
        grid_scores.append(row)
    write_csv(O / "grid.csv", [{k: v for k, v in r.items() if not k.startswith("_")} for r in grid_scores])
    front = pareto(grid_scores)
    write_csv(O / "pareto.csv", [{k: v for k, v in r.items() if not k.startswith("_")} for r in front])

    # 4. leave-one-hack-out: choose the grid config on 13 hacks (+ all FA windows except the held-out
    #    hack's own baseline), objective = fewest misses, then least excess loss, subject to
    #    pooled pages/bridge-week <= 0.5 and no non-pool window above 1/week; score the held-out case.
    hacks = [ds.key for ds in dss if ds.kind == "hack" and ds.thefts]

    def choose(train_keys, fa_keys):
        best = None
        for r in grid_scores:
            s = r["_s"]
            fa = [s.fa[k] for k in fa_keys if k in s.fa]
            w = sum(v[2] for v in fa)
            rate = sum(v[0] for v in fa) / w if w else 0
            worst_np = max((v[0] / v[2] for v in fa if v[3] != "pool" and v[2] > 0), default=0)
            if rate > 0.5 or worst_np > 1.0:
                continue
            cs = [s.cases[k] for k in train_keys]
            misses = sum(not c["detected"] for c in cs)
            excess = sum((c["before_usd"] if c["detected"] else c["stolen"]) - c["floor_usd"] for c in cs)
            key = (misses, excess, rate)
            if best is None or key < best[0]:
                best = (key, r)
        return best[1] if best else None

    loo = []
    for h in hacks:
        train = [k for k in hacks if k != h]
        fa_keys = [k for k in grid_scores[0]["_s"].fa if k != h]
        r = choose(train, fa_keys)
        c = r["_s"].cases[h]
        fa_h = r["_s"].fa.get(h)
        loo.append({"held_out": h, "chosen": r["policy"], "detected": c["detected"],
                    "before_share": round(c["before_share"], 3) if c["detected"] else None,
                    "floor_share": round(c["floor_share"], 3),
                    "at_floor": bool(c["detected"] and c["before_share"] <= c["floor_share"] + 1e-9),
                    "held_out_baseline_pages_per_week": round(fa_h[0] / fa_h[2], 2) if fa_h and fa_h[2] else None})
    (O / "loo.json").write_text(json.dumps({
        "rule": "choose on 13 hacks + FA windows minus the held-out hack's baseline; objective (misses, excess $, FA) "
                "subject to pooled pages/bridge-week <= 0.5 and every non-pool window <= 1/week",
        "detected": sum(x["detected"] for x in loo), "at_floor": sum(x["at_floor"] for x in loo), "n": len(loo),
        "cases": loo}, indent=1))

    # 5. time split: choose on <= 2023 data, score on 2024+ data
    year = {ds.key: int(common.fmt_ts(ds.first_theft_ts or ds.start_ts)[:4]) for ds in dss}
    train_h = [k for k in hacks if year[k] <= 2023]
    test_h = [k for k in hacks if year[k] >= 2024]
    fa_keys_all = list(grid_scores[0]["_s"].fa)
    train_fa = [k for k in fa_keys_all if year[k] <= 2023]
    test_fa = [k for k in fa_keys_all if year[k] >= 2024]
    r = choose(train_h, train_fa)
    s = r["_s"]
    fa = [s.fa[k] for k in test_fa]
    w = sum(v[2] for v in fa)
    ts_res = {"train_hacks": train_h, "test_hacks": test_h, "train_fa_windows": train_fa, "test_fa_windows": test_fa,
              "chosen": r["policy"],
              "test_cases": {k: {"detected": s.cases[k]["detected"],
                                 "before_share": round(s.cases[k].get("before_share", 1), 3),
                                 "floor_share": round(s.cases[k]["floor_share"], 3)} for k in test_h},
              "test_pages_per_bridge_week": round(sum(v[0] for v in fa) / w, 3) if w else None,
              "test_windows_over_1_per_week": [k for k in test_fa if s.fa[k][2] and s.fa[k][0] / s.fa[k][2] > 1]}
    (O / "time-split.json").write_text(json.dumps(ts_res, indent=1))

    for c in combos:
        print({k: c[k] for k in ("policy", "hacks_detected", "hacks_at_floor", "mean_stolen_before_share",
                                 "excess_loss_musd", "pages_per_bridge_week_all", "pages_per_bridge_week_nonpool",
                                 "pages_per_bridge_week_pool", "worst_nonpool_window", "nab_lowfp")})
    print("pareto points:", len(front), "| LOO detected", sum(x["detected"] for x in loo), "at floor",
          sum(x["at_floor"] for x in loo), "| time split:", ts_res["chosen"], ts_res["test_pages_per_bridge_week"])


if __name__ == "__main__":
    main()
