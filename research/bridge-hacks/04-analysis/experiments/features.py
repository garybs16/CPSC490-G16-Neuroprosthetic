"""
One row per hack case with on-chain data -> 04-analysis/features.csv (+ out/features.json).

Run (from anywhere, with the prototype's Python):
  PYTHONDONTWRITEBYTECODE=1 python features.py --prototype <copy of prototype/>
"""
from __future__ import annotations

import csv
import datetime as dt
import json
import statistics

import common
from common import NATIVE_ETH, fmt_ts, utc

# Catalog row for each dataset (01-hack-catalog/hacks.csv id).
CATALOG_ID = {
    "poly-2021": "2021-08-poly-network", "poly-2023": "2023-07-poly-network", "heco-2023": "2023-11-heco-bridge",
    "ronin-2024": "2024-08-ronin", "force-bridge-2025": "2025-06-force-bridge", "shibarium-2025": "2025-09-shibarium",
    "kelp-2026": "2026-04-kelpdao-rseth", "verus-2026": "2026-05-verus-1", "xbridge-2024": "2024-04-xbridge",
    "qubit-2022": "2022-01-qubit", "harmony-2022": "2022-06-harmony", "multichain-2023": "2023-07-multichain",
    "nomad-2022": "2022-08-nomad", "orbit-2023": "2023-12-orbit-bridge", "ronin-2022": "2022-03-ronin",
}

# Pre-attack signals from public reports (case pages, verified-ethereum-cases.md, dataset case notes).
# (on-chain precursor, lead time before first theft, source)
PRE_ATTACK = {
    "poly-2021": ("config: keeper public-key replacement (EthCrossChainManager)", "2 min 22 s",
                  "cases/2021-08-poly-network.md; verified-ethereum-cases.md"),
    "poly-2023": ("none public on-chain (keeper multisig signed forged unlocks)", "", "catalog; dataset notes"),
    "heco-2023": ("none known (compromised operator key)", "", "cases/2023-11-heco-bridge.md"),
    "ronin-2024": ("config: proxy Upgraded to MainchainGatewayV3 (operator weight uninitialised)", "48 min 36 s",
                   "cases/2024-08-ronin.md; verified-ethereum-cases.md"),
    "force-bridge-2025": ("failed attempt tx 0x69104f6b (block 22,608,287, ~19 blocks earlier); vault sunset announced 31 May",
                          "~4 min (failed attempt)", "dataset notes; catalog (Hacken)"),
    "shibarium-2025": ("validator stake shift (flash-loaned BONE) -> malicious checkpoint", "same session",
                       "cases/2025-09-shibarium.md"),
    "kelp-2026": ("config: DVN set reduced to 1-of-1 (LayerZero report)", "weeks", "cases/2026-04-kelpdao-rseth.md"),
    "verus-2026": ("none known on-chain", "", "cases/2026-05-verus.md"),
    "xbridge-2024": ("config: attacker re-listed STC via listToken (tx 0xe09d350d)", "minutes (same session)",
                     "dataset notes"),
    "qubit-2022": ("fake deposit event with no token movement IS the Ethereum-side signal", "0",
                   "dataset notes (negative control)"),
    "harmony-2022": ("multisig confirmTransaction by the same 2 signers just before each release", "seconds",
                     "cases/2022-06-harmony.md"),
    "multichain-2023": ("$2 USDC test release to the first theft recipient; operator unreachable for weeks (off-chain)",
                        "1 h 49 min (test)", "cases/2023-07-multichain.md; open-questions.md §1; this data"),
    "nomad-2022": ("config: faulty Replica initialisation; failed first exploit attempt", "41 days (init)",
                   "cases/2022-08-nomad.md; 02-defenses/techniques.md T10"),
    "orbit-2023": ("5 dust test releases ($1-$514) to the 4 later theft recipients; unauthorised access 20:52:47 (off-chain)",
                   "2 h 38 min to 27 min (tests)", "this data (orbit-2023.json); cases/2023-12-orbit-bridge.md"),
    "ronin-2022": ("attacker EOA funded from an exchange (off-vault)", "12 min", "cases/2022-03-ronin.md"),
}


def catalog_rows(args) -> dict:
    with open(f"{args.research}/01-hack-catalog/hacks.csv", newline="", encoding="utf-8") as f:
        return {r["id"]: r for r in csv.DictReader(f)}


def replay_current(ds) -> dict:
    from bridgewatch.detector import DetectorConfig
    from bridgewatch.replay import run
    return run(ds.src, DetectorConfig())


def main():
    ap = common.parser(__doc__)
    args = ap.parse_args()
    common.setup(args)
    cat = catalog_rows(args)
    rows = []
    for ds in common.load_all(args):
        if ds.kind != "hack":
            continue
        c = cat.get(CATALOG_ID.get(ds.key, ""), {})
        r = replay_current(ds)
        th = sorted(ds.thefts, key=lambda t: (t.block_time, t.log_index))
        stolen = ds.stolen_usd()
        native = NATIVE_ETH.get(ds.key)
        native_usd = native[1] * native[2] if native else 0.0
        native_ts = utc(native[0]) if native else None
        row = {
            "key": ds.key, "catalog_id": CATALOG_ID.get(ds.key, ""), "design": ds.design,
            "root_cause": c.get("root_cause_category", ""), "reported_loss_usd": c.get("loss_usd", ""),
            "vault": ds.src.vault, "tracked_escrow_usd_at_start": round(ds.escrow0),
            "tracked_stolen_usd": round(stolen), "n_thefts": len(th),
            "native_eth_untracked_usd": round(native_usd),
        }
        pre = PRE_ATTACK.get(ds.key, ("", "", ""))
        row.update({"pre_attack_signal": pre[0], "pre_attack_lead": pre[1], "pre_attack_source": pre[2]})
        if not th:
            row.update({"notes": "no tracked theft (negative control)"})
            rows.append(row)
            continue
        f = th[0]
        first_ts = f.block_time
        d = dt.datetime.fromtimestamp(first_ts, dt.timezone.utc)
        WETH = "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2"   # weth_unwrap rows: real recipient not in the logs
        recips = []
        for t in th:
            cp = t.counterparty.lower()
            if cp != WETH and cp not in recips:
                recips.append(cp)
        prior = {}
        for t in ds.transfers:
            cp = t.counterparty.lower()
            if t.block_time < first_ts and cp in recips:
                prior.setdefault(cp, []).append(t)
        tests = [t for v in prior.values() for t in v if t.direction == "out" and t.amount_usd < 1_000]
        gaps = [b.block_time - a.block_time for a, b in zip(th, th[1:])]
        tokseq = []
        for t in th:
            if t.token not in tokseq:
                tokseq.append(t.token)
        first_tx_usd = sum(t.amount_usd for t in th if t.tx_hash == f.tx_hash)
        # current detector
        det = r["first_alert_detected_at"]
        before = r["stolen_before_alert_usd"]
        incl_native_before = None
        if det is not None:
            incl_native_before = before + (native_usd if native_ts is not None and native_ts <= det else 0.0)
        total_incl = stolen + native_usd
        escrow_before_first = None
        # vault value just before the first theft (tracked tokens)
        esc = ds.escrow0
        tok_bal = dict(ds.src.data.get("balances_at_start", {}))
        for t in ds.transfers:
            if t.block_time > first_ts or (t.block_time == first_ts and t.log_index >= f.log_index):
                break
            if t.amount_usd is None:
                continue
            esc += t.amount_usd if t.direction == "in" else -t.amount_usd
            tok_bal[t.token] = tok_bal.get(t.token, 0) + (t.amount if t.direction == "in" else -t.amount)
        escrow_before_first = esc
        row.update({
            "first_theft_utc": fmt_ts(first_ts), "hour_utc": d.hour, "weekday": d.strftime("%a"),
            "first_theft_tx": f.tx_hash, "first_token": f.token,
            "first_theft_usd": round(f.amount_usd), "first_tx_usd_all_tokens": round(first_tx_usd),
            "first_theft_share_tvl": round(f.amount_usd / escrow_before_first, 3),
            "tracked_tvl_before_first_theft_usd": round(escrow_before_first),
            "stolen_share_of_tvl_before_first_theft": round(stolen / escrow_before_first, 3),
            "first_theft_share_of_token_balance": round(f.amount / tok_bal.get(f.token, f.amount), 3) if tok_bal.get(f.token) else "",
            "first_tx_share_of_tracked_theft": round(first_tx_usd / stolen, 3),
            "token_sequence": ">".join(tokseq),
            "n_recipients": len(recips) + (1 if any(t.counterparty.lower() == WETH for t in th) else 0),
            "first_recipient_seen_before": ("unknown (WETH unwrap)" if f.counterparty.lower() == WETH
                                            else "yes" if f.counterparty.lower() in prior else "no"),
            "dust_test_releases_to_theft_recipients": len(tests),
            "first_test_lead_min": round((first_ts - min(t.block_time for t in tests)) / 60, 1) if tests else "",
            "drain_duration_min": round((th[-1].block_time - first_ts) / 60, 1),
            "inter_theft_gap_median_s": round(statistics.median(gaps)) if gaps else "",
            "inter_theft_gap_max_s": max(gaps) if gaps else "",
            "native_eth_first": ("yes" if native_ts is not None and native_ts < first_ts else
                                 "same tx" if native_ts is not None and native_ts == first_ts else "no"),
            "native_eth_lead_min": round((first_ts - native_ts) / 60, 1) if native_ts is not None else "",
            "current_first_rule": r["first_alert_rule"],
            "current_latency_s": r["detection_latency_s"],
            "current_stolen_before_usd": round(before) if before is not None else "",
            "current_stolen_before_share": round(before / stolen, 3) if before is not None else "",
            "current_alert_before_half": (before / stolen < 0.5) if before is not None else False,
            "current_stolen_before_share_incl_native": round(incl_native_before / total_incl, 3)
            if incl_native_before is not None else "",
            "current_alert_after_first_any_theft_min": round((det - (native_ts or first_ts)) / 60, 1)
            if det is not None and native_ts is not None and native_ts < first_ts else "",
            "current_baseline_false_alarms": r["false_alarms_during_baseline"],
            "notes": "",
        })
        rows.append(row)
    cols = []
    for r in rows:
        for k in r:
            if k not in cols:
                cols.append(k)
    out = common.HERE.parent / "features.csv"
    with open(out, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        for r in rows:
            w.writerow(r)
    (common.OUT / "features.json").write_text(json.dumps(rows, indent=1) + "\n", encoding="utf-8")
    for r in rows:
        print({k: r.get(k) for k in ("key", "first_theft_usd", "first_theft_share_tvl", "first_tx_share_of_tracked_theft",
                                      "n_thefts", "n_recipients", "drain_duration_min", "native_eth_first",
                                      "current_first_rule", "current_stolen_before_share", "hour_utc")})
    print("wrote", out)


if __name__ == "__main__":
    main()
