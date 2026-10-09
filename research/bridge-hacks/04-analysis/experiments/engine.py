"""
Per-release feature stream for offline signal experiments.

For every outflow (release) of a dataset, compute the candidate signals listed in
04-analysis/experiments.md at the moment the release is seen, using only data up
to and including that release (streaming, no look-ahead):

  share_tvl       release USD / tracked vault USD just before it
  tok_share       release units / that token's balance just before it
  net10_share     net outflow (out - in) in the last 10 min / vault value 10 min ago
  net1h_share     net outflow in the last hour / vault value an hour ago
  gross10_share   gross outflow in the last 10 min / vault value 10 min ago
  dd24 / dd24_usd drawdown of vault USD from its 24 h high
  new_cp          recipient never seen in this vault's history (either direction); None = unknown
                  (weth_unwrap rows: the real recipient is not in Transfer logs)
  never_dep       recipient never deposited into the vault
  fresh           recipient has < $1,000 of prior flow with the vault (never seen, or only dust "test"
                  releases, as in Orbit 2023 and Multichain 2023); None = unknown recipient
  n_new_rcpt10    distinct never-seen recipients in the last 10 min
  n_rcpt10        distinct recipients in the last 10 min
  n_tok_drain10   distinct tokens with a release >= 20% of that token's balance (and >= $50K) in the last 10 min
  cp1h_share      outflow to this same recipient in the last hour / vault value an hour ago
  z_u, z_c        the prototype's hour-of-day robust z for 10-min outflow USD and count
                  (spread floors applied later, so the floor can be swept)

The prototype's BridgeMonitor runs alongside (read-only use of its baseline
history), so z values match bridgewatch.detector exactly for a given floor.
"""
from __future__ import annotations

import statistics
from collections import deque, defaultdict

from common import WARMUP_S, detected_at

BUCKET = 600.0
HOUR = 3_600.0
DAY = 86_400.0
WETH_CONTRACT = "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2"


def _robust(values):
    med = statistics.median(values)
    mad = statistics.median(abs(v - med) for v in values)
    return med, mad


def feature_stream(ds, history_days: float = 7.0) -> list[dict]:
    from bridgewatch.detector import BridgeMonitor, DetectorConfig
    from bridgewatch.models import Bridge
    from bridgewatch.source import to_flow_event

    cfg = DetectorConfig(history_days=history_days)
    mon = BridgeMonitor(Bridge(ds.key, ds.key, ("ethereum",), ds.escrow0), cfg, first_ts=ds.start_ts)
    prices = ds.src.prices
    tok_bal = dict(ds.src.data.get("balances_at_start", {}))
    escrow = ds.escrow0
    seen: dict[str, float] = {}
    cp_usd: dict[str, float] = defaultdict(float)   # prior USD moved with each counterparty (both directions)
    depositors: set[str] = set()
    out10: deque = deque()     # (ts, usd, cp, token, tok_share, is_new)
    in10: deque = deque()      # (ts, usd)
    out1h: deque = deque()     # (ts, usd, cp)
    in1h: deque = deque()
    hi24: deque = deque()      # monotonic (ts, escrow) for 24 h max
    base_cache: dict = {}
    rows = []

    def push_escrow(ts, val):
        while hi24 and hi24[-1][1] <= val:
            hi24.pop()
        hi24.append((ts, val))

    push_escrow(ds.start_ts, escrow)
    for t in ds.transfers:
        e = to_flow_event(t, 72.0)
        if e is None:
            continue
        ts = t.block_time
        for dq, span in ((out10, BUCKET), (in10, BUCKET), (out1h, HOUR), (in1h, HOUR)):
            while dq and dq[0][0] <= ts - span:
                dq.popleft()
        while hi24 and hi24[0][0] <= ts - DAY:
            hi24.popleft()
        mon.observe(e, lambda: 0, ts)
        cp = (t.counterparty or "").lower()
        kind = ds.kind_of(t)
        usd = t.amount_usd
        if t.direction == "in":
            escrow += usd
            tok_bal[t.token] = tok_bal.get(t.token, 0.0) + t.amount
            in10.append((ts, usd))
            in1h.append((ts, usd))
            if cp and cp != WETH_CONTRACT:
                seen.setdefault(cp, ts)
                depositors.add(cp)
                cp_usd[cp] += usd
            push_escrow(ts, escrow)
            continue

        escrow_before = escrow
        tok_before = tok_bal.get(t.token, 0.0)
        hi = max([v for _, v in hi24] + [escrow_before])
        escrow -= usd
        tok_bal[t.token] = tok_before - t.amount
        tok_share = t.amount / tok_before if tok_before > 0 else 1.0
        cp_known = bool(cp) and cp != WETH_CONTRACT
        history_ok = ts - ds.start_ts >= WARMUP_S
        is_new = (cp not in seen) if cp_known else None
        prior_usd = cp_usd[cp] if cp_known else None
        fresh = (prior_usd < 1_000) if cp_known else None
        never_dep = (cp not in depositors) if cp_known else None
        out10.append((ts, usd, cp if cp_known else None, t.token, tok_share, bool(is_new) and history_ok))
        out1h.append((ts, usd, cp if cp_known else None))
        if cp_known:
            seen.setdefault(cp, ts)
            cp_usd[cp] += usd
        push_escrow(ts, escrow)

        g10 = sum(x[1] for x in out10)
        n10 = g10 - sum(x[1] for x in in10)
        g1h = sum(x[1] for x in out1h)
        n1h = g1h - sum(x[1] for x in in1h)
        ref10 = max(escrow + n10, 1.0)
        ref1h = max(escrow + n1h, 1.0)
        cp1h = sum(x[1] for x in out1h if cp_known and x[2] == cp)
        toks = {x[3] for x in out10 if x[4] >= 0.2 and x[1] >= 50_000}

        # Prototype baseline (hour of day, 7 days, median / MAD) without the spread floor.
        h = int((ts % DAY) // HOUR)
        med_u = sp_u = med_c = sp_c = None
        if len(mon.hist_usd[h]) >= 6 and ts - ds.start_ts >= cfg.warmup:
            key = (h, mon._closed)
            if key not in base_cache:
                mu, au = _robust(mon.hist_usd[h])
                mc, ac = _robust(mon.hist_cnt[h])
                base_cache[key] = (mu, max(1.4826 * au, 0.5 * mu), mc, max(1.4826 * ac, 0.5 * mc, 1.0))
            med_u, sp_u, med_c, sp_c = base_cache[key]

        rows.append({
            "ts": ts, "det": detected_at(ts), "usd": usd, "token": t.token, "tx": t.tx_hash, "cp": cp,
            "kind": kind or "", "theft": ds.is_theft(t),
            "escrow_before": escrow_before, "share_tvl": usd / max(escrow_before, 1.0),
            "tok_share": tok_share,
            "net10": n10, "net10_share": n10 / ref10, "net1h": n1h, "net1h_share": n1h / ref1h,
            "gross10": g10, "gross10_share": g10 / ref10, "ref1h": ref1h,
            "dd24": (hi - escrow) / hi if hi > 0 else 0.0, "dd24_usd": hi - escrow,
            "new_cp": (is_new if history_ok else None), "never_dep": never_dep,
            "fresh": (fresh if history_ok else None), "cp_prior_usd": prior_usd,
            "n_new_rcpt10": len({x[2] for x in out10 if x[5] and x[2]}),
            "n_rcpt10": len({x[2] for x in out10 if x[2]}),
            "n_out10": len(out10),
            "n_tok_drain10": len(toks),
            "cp1h": cp1h, "cp1h_share": cp1h / ref1h,
            "win_usd": mon.win_usd, "win_cnt": len(mon.recent_out),
            "med_u": med_u, "sp_u": sp_u, "med_c": med_c, "sp_c": sp_c,
            "warm": ts - ds.start_ts >= WARMUP_S,
        })
    return rows


_CACHE: dict = {}


def cached_stream(ds) -> list[dict]:
    if ds.key not in _CACHE:
        _CACHE[ds.key] = feature_stream(ds)
    return _CACHE[ds.key]
