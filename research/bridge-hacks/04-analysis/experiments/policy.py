"""
Signal families, paging policies and the scorer used by sweep.py.

A policy sees the release stream of one dataset (engine.feature_stream rows) and
returns, per release, a level: 0 nothing, 1 warning (dashboard only), 2 page.
Pages on one bridge within COOLDOWN of each other are one incident = one page
(the prototype's notifier does the same).

Scoring (per policy, over all 29 windows):
  hacks      first page inside [first theft - 1 h, last theft + 1 h]; stolen-before =
             tracked theft with block time <= that page's detected_at (6 confirmations,
             15 s polls), as in bridgewatch.replay
  floor      the same share for an ideal detector that pages on the first theft
             (out/floors.csv, 6 confirmations): nothing outflow-based can do better
  FA         page incidents during each window's false-alarm period (normal windows after
             the 3-day warm-up; hack files from warm-up to 1 h before the first theft)
"""
from __future__ import annotations

import math
import statistics
from dataclasses import dataclass, field

from common import WEEK

COOLDOWN = 3_600.0
FAMILIES = ("huge", "size", "fresh", "net1h", "net10", "dd24", "conc", "multi", "crowd", "spike", "burst")


@dataclass(frozen=True)
class P:
    """Thresholds for every signal family (None = family off)."""
    huge: tuple | None = None                     # (share of TVL, USD floor) single release that empties the vault
    size: tuple | None = (0.02, 1_000_000)        # (share of TVL, USD floor) single release
    fresh: tuple | None = None                    # (share of TVL, USD floor) single release to a fresh recipient
    net1h: tuple | None = (0.05, 0)               # (share, USD floor) net outflow over 1 h
    net10: tuple | None = None
    dd24: tuple | None = None                     # (share, USD floor) drawdown from 24 h high
    conc: tuple | None = None                     # (share, USD floor) outflow to ONE recipient in 1 h
    multi: int | None = None                      # >= k tokens each >= 20% drained in 10 min
    crowd: int | None = None                      # >= k distinct never-seen recipients in 10 min
    spike: tuple | None = (6.0, 100_000, 0.005)   # (z, spread floor USD, min share of TVL) prototype outflow_spike
    burst: tuple | None = (6.0, 12)               # (z, min count) prototype withdrawal_burst
    # paging: "any" = any family pages (the prototype); "combo" = page on a strong signal or >= 2 families within window
    mode: str = "any"
    strong: tuple = ()                            # families that page alone in combo mode
    window_s: float = 1_800.0
    unknown_recipient_is_fresh: bool = False      # weth_unwrap rows: recipient not in Transfer logs
    pool_ignore_known_lp: bool = False            # pools: releases to past depositors never count for size/fresh/conc
    pool_profile: bool = False                    # pools: page only if net 1h >= 20% of TVL and >= $1M AND another family
    label: str = ""


def fired(r: dict, p: P, design: str) -> set[str]:
    f = set()
    usd = r["usd"]
    known_lp = p.pool_ignore_known_lp and design == "pool" and r["never_dep"] is False
    fresh = r["fresh"]
    if fresh is None and p.unknown_recipient_is_fresh and r["kind"] == "weth_unwrap" and r["warm"]:
        fresh = True
    if p.huge and not known_lp and r["share_tvl"] >= p.huge[0] and usd >= p.huge[1]:
        f.add("huge")
    if p.size and not known_lp and r["share_tvl"] >= p.size[0] and usd >= p.size[1]:
        f.add("size")
    if p.fresh and not known_lp and fresh and r["share_tvl"] >= p.fresh[0] and usd >= p.fresh[1]:
        f.add("fresh")
    if p.net1h and r["net1h_share"] >= p.net1h[0] and r["net1h"] >= p.net1h[1]:
        f.add("net1h")
    if p.net10 and r["net10_share"] >= p.net10[0] and r["net10"] >= p.net10[1]:
        f.add("net10")
    if p.dd24 and r["dd24"] >= p.dd24[0] and r["dd24_usd"] >= p.dd24[1]:
        f.add("dd24")
    if p.conc and not known_lp and r["cp1h_share"] >= p.conc[0] and r["cp1h"] >= p.conc[1]:
        f.add("conc")
    if p.multi and r["n_tok_drain10"] >= p.multi:
        f.add("multi")
    if p.crowd and r["n_new_rcpt10"] >= p.crowd:
        f.add("crowd")
    if p.spike and r["med_u"] is not None:
        z = (r["win_usd"] - r["med_u"]) / max(r["sp_u"], p.spike[1])
        if z >= p.spike[0] and r["win_usd"] >= p.spike[2] * r["ref1h"]:
            f.add("spike")
    if p.burst and r["med_c"] is not None:
        zc = (r["win_cnt"] - r["med_c"]) / r["sp_c"]
        if zc >= p.burst[0] and r["win_cnt"] >= p.burst[1]:
            f.add("burst")
    return f


def levels(rows: list[dict], p: P, design: str) -> list[tuple[dict, int, frozenset]]:
    out = []
    last: dict[str, float] = {}
    for r in rows:
        now = fired(r, p, design)
        for k in now:
            last[k] = r["ts"]
        if not now:
            out.append((r, 0, frozenset()))
            continue
        if p.mode == "any":
            out.append((r, 2, frozenset(now)))
            continue
        active = {k for k, t in last.items() if r["ts"] - t <= p.window_s}
        if p.pool_profile and design == "pool":
            deep = r["net1h_share"] >= 0.20 and r["net1h"] >= 1_000_000
            out.append((r, 2 if deep and len(active) >= 2 else 1, frozenset(active)))
            continue
        if now & set(p.strong) or len(active) >= 2:
            out.append((r, 2, frozenset(active)))
        else:
            out.append((r, 1, frozenset(active)))
    return out


def incidents(events: list[tuple[float, frozenset]]) -> list[tuple[float, frozenset]]:
    """Group (ts, families) into incidents: a new one starts after COOLDOWN of silence."""
    out, last = [], -math.inf
    for ts, fam in events:
        if ts - last >= COOLDOWN:
            out.append((ts, fam))
        last = ts
    return out


@dataclass
class Score:
    label: str
    cases: dict = field(default_factory=dict)       # key -> per-case result
    fa: dict = field(default_factory=dict)          # key -> (pages, warnings, weeks, design, role)

    # --- hack metrics -----------------------------------------------------------
    def detected(self) -> int:
        return sum(c["detected"] for c in self.cases.values())

    def at_floor(self) -> int:
        return sum(c["detected"] and c["before_share"] <= c["floor_share"] + 1e-9 for c in self.cases.values())

    def before_half(self) -> int:
        return sum(c["detected"] and c["before_share"] < 0.5 for c in self.cases.values())

    def mean_before(self) -> float:
        return statistics.mean(c["before_share"] if c["detected"] else 1.0 for c in self.cases.values())

    def excess_usd(self) -> float:
        """Theft that a floor detector would have stopped but this one did not (missed = all after the floor)."""
        return sum((c["before_usd"] if c["detected"] else c["stolen"]) - c["floor_usd"] for c in self.cases.values())

    def median_latency(self) -> float | None:
        lat = [c["latency_s"] for c in self.cases.values() if c["detected"]]
        return statistics.median(lat) if lat else None

    # --- false alarms ------------------------------------------------------------
    def fa_rate(self, pred=lambda k, v: True, warn=False) -> float:
        sel = [(v[1] if warn else v[0], v[2]) for k, v in self.fa.items() if pred(k, v)]
        w = sum(x[1] for x in sel)
        return sum(x[0] for x in sel) / w if w else 0.0

    def fa_worst(self, pred=lambda k, v: True) -> tuple[str, float]:
        cand = [(k, v[0] / v[2]) for k, v in self.fa.items() if v[2] > 0 and pred(k, v)]
        return max(cand, key=lambda x: x[1]) if cand else ("", 0.0)

    def windows_over(self, limit=1.0, pred=lambda k, v: True) -> int:
        return sum(v[2] > 0 and v[0] / v[2] > limit for k, v in self.fa.items() if pred(k, v))

    def nab(self, a_fp=0.22, a_fn=1.0) -> float:
        """NAB-style normalized score (low-FP profile weights). Window per hack = first theft
        to max(last theft, first theft + 10 min); reward = scaled sigmoid of relative position."""
        raw, n = 0.0, len(self.cases)
        for c in self.cases.values():
            if not c["detected"]:
                raw -= a_fn
                continue
            length = max(c["window_len"], 600.0)
            y = (c["det_rel"] - length) / length          # -1 at window start, 0 at end
            raw += 2 / (1 + math.exp(5 * y)) - 1
        raw -= a_fp * sum(v[0] for v in self.fa.values())
        null, perfect = -a_fn * n, float(n)
        return 100 * (raw - null) / (perfect - null)


def score(datasets, streams: dict, floors: dict, p: P, label: str = "") -> Score:
    s = Score(label or p.label)
    for ds in datasets:
        rows = streams[ds.key]
        lv = levels(rows, p, ds.design)
        per = ds.fa_period()
        if per:
            lo, hi = per
            pages = incidents([(r["ts"], f) for r, l, f in lv if l == 2 and lo <= r["ts"] < hi])
            warns = incidents([(r["ts"], f) for r, l, f in lv if l >= 1 and lo <= r["ts"] < hi])
            s.fa[ds.key] = (len(pages), len(warns), (hi - lo) / WEEK, ds.design, "pre-hack" if ds.kind == "hack" else ds.role)
        if ds.kind == "hack" and ds.thefts:
            stolen = ds.stolen_usd()
            lo_t, hi_t = ds.first_theft_ts - 3_600, ds.last_theft_ts + 3_600
            first = next(((r, f) for r, l, f in lv if l == 2 and lo_t <= r["ts"] <= hi_t), None)
            t0 = math.ceil((ds.first_theft_ts + 72.0) / 15.0) * 15.0     # ideal: page on the first theft
            fl = sum(t.amount_usd for t in ds.thefts if t.block_time <= t0) / stolen
            c = {"stolen": stolen, "floor_share": fl, "floor_usd": fl * stolen, "detected": first is not None,
                 "window_len": ds.last_theft_ts - ds.first_theft_ts}
            if first:
                r, fam = first
                before = sum(t.amount_usd for t in ds.thefts if t.block_time <= r["det"])
                c.update({"det": r["det"], "det_rel": r["det"] - ds.first_theft_ts, "before_usd": before,
                          "before_share": before / stolen, "latency_s": r["det"] - (ds.first_theft_ts + 72.0),
                          "families": sorted(fam)})
            s.cases[ds.key] = c
    return s


def summary(s: Score) -> dict:
    nonpool = lambda k, v: v[3] != "pool"
    normal_only = lambda k, v: v[4] in ("normal", "stress")
    w_np = s.fa_worst(nonpool)
    w_all = s.fa_worst()
    return {
        "policy": s.label,
        "hacks_detected": s.detected(), "hacks_at_floor": s.at_floor(), "hacks_before_half": s.before_half(),
        "mean_stolen_before_share": round(s.mean_before(), 3),
        "excess_loss_musd": round(s.excess_usd() / 1e6, 1),
        "median_latency_s": s.median_latency(),
        "pages_per_bridge_week_all": round(s.fa_rate(), 3),
        "pages_per_bridge_week_nonpool": round(s.fa_rate(nonpool), 3),
        "pages_per_bridge_week_pool": round(s.fa_rate(lambda k, v: v[3] == "pool"), 3),
        "pages_per_bridge_week_normal_windows": round(s.fa_rate(normal_only), 3),
        "pages_per_bridge_week_prehack": round(s.fa_rate(lambda k, v: v[4] == "pre-hack"), 3),
        "warnings_per_bridge_week_all": round(s.fa_rate(warn=True), 3),
        "worst_window": f"{w_all[0]} {w_all[1]:.2f}",
        "worst_nonpool_window": f"{w_np[0]} {w_np[1]:.2f}",
        "windows_over_1_per_week": s.windows_over(),
        "nonpool_windows_over_1_per_week": s.windows_over(pred=nonpool),
        "total_pages_in_fa_periods": sum(v[0] for v in s.fa.values()),
        "nab_lowfp": round(s.nab(), 1),
    }
