"""
Replay a real bridge hack through the detector, using real on-chain data.

Case: the Orbit Chain bridge vault on Ethereum, 31 Dec 2023 (1 Jan 2024 in
Korea). The vault address was identified from the on-chain record itself: on
that evening it released 10M DAI, 230.88 WBTC, 30M USDT and 10M USDC to four
fresh addresses within 18 minutes, after small test transfers to some of the
same addresses. That matches public reports of the Orbit hack, but check it
against a published incident report before citing it.

The detector sees 14 days of the vault's ordinary traffic first (its
baseline), then the hack, exactly as it would have live.

  python -m bridgewatch.replay            # score from the saved data (offline)
  python -m bridgewatch.replay --fetch    # re-download from public RPCs (a few minutes)
"""

from __future__ import annotations
import argparse
import datetime as dt
import json
from dataclasses import asdict, dataclass
from pathlib import Path

from .detector import Detector, DetectorConfig
from .models import Bridge, FlowEvent

DATA_DIR = Path(__file__).resolve().parent / "data"


@dataclass(frozen=True)
class Case:
    key: str
    title: str
    vault: str
    tokens: tuple[tuple[str, str, int], ...]   # (address, symbol, decimals)
    start_block: int                            # baseline starts here (~14 days before)
    end_block: int                              # a few hours after the hack
    btc_usd_feed: str                           # Chainlink aggregator used to price WBTC
    price_block: int
    theft_min_usd: float                        # releases at least this large in the hack window count as stolen
    hack_window: tuple[int, int]                # blocks bracketing the theft


ORBIT = Case(
    key="orbit-2023",
    title="Orbit Chain bridge, Ethereum vault, 31 Dec 2023",
    vault="0x1bf68a9d1eaee7826b3593c20a0ca93293cb489a",
    tokens=(("0xdac17f958d2ee523a2206206994597c13d831ec7", "USDT", 6),
            ("0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48", "USDC", 6),
            ("0x6b175474e89094c44da98b954eedeac495271d0f", "DAI", 18),
            ("0x2260fac5e5542a773aa44fbcfedf7c193bc2c599", "WBTC", 8)),
    start_block=18_808_000,
    end_block=18_912_443,
    btc_usd_feed="0xF4030086522a5bEEa4988F8cA5B36dbC97BeE88c",
    price_block=18_908_000,
    theft_min_usd=1_000_000,
    hack_window=(18_907_104, 18_912_443),
)
CASES = {ORBIT.key: ORBIT}


def fetch(case: Case) -> dict:
    """Download the case's data from public RPCs and save it next to this module."""
    from .onchain import Rpc, Token, fetch_vault_flows, save
    rpc = Rpc()
    desc, btc = rpc.chainlink_price(case.btc_usd_feed, case.price_block)
    if desc != "BTC / USD":
        raise RuntimeError(f"Price feed describes itself as '{desc}', expected 'BTC / USD'.")
    prices = {"USDT": 1.0, "USDC": 1.0, "DAI": 1.0, "WBTC": btc}
    tokens = [Token(a, s, d, prices[s]) for a, s, d in case.tokens]
    balances = {t.symbol: rpc.balance_of(t.address, case.vault, case.start_block) / 10 ** t.decimals for t in tokens}
    rows = fetch_vault_flows(rpc, case.vault, tokens, case.start_block, case.end_block)
    data = {
        "case": asdict(case),
        "fetched": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat(),
        "source": "Ethereum mainnet via public JSON-RPC (" + ", ".join(rpc.urls) + ")",
        "prices_usd": prices,
        "price_note": "Stablecoins at $1; WBTC at the Chainlink BTC/USD answer at block "
                      f"{case.price_block}. Native ETH is not included (not visible in token logs).",
        "start_ts": rpc.block_time(case.start_block),
        "end_ts": rpc.block_time(case.end_block),
        "balances_at_start": balances,
        "transfers": rows,
    }
    save(DATA_DIR / f"{case.key}.json", data)
    return data


def load(case: Case) -> dict:
    return json.loads((DATA_DIR / f"{case.key}.json").read_text(encoding="utf-8"))


def run(case: Case, data: dict | None = None, cfg: DetectorConfig | None = None) -> dict:
    """Feed the saved transfers through the detector and score it against the theft."""
    data = data or load(case)
    prices = data["prices_usd"]
    escrow = sum(bal * prices[sym] for sym, bal in data["balances_at_start"].items())
    bridge = Bridge("orbit", "Orbit bridge vault", ("Ethereum",), escrow)
    cfg = cfg or DetectorConfig()
    det = Detector((bridge,), cfg)
    det.monitors["orbit"].first_ts = data["start_ts"]
    lo, hi = case.hack_window
    thefts = [r for r in data["transfers"]
              if r["direction"] == "out" and lo <= r["block"] <= hi and r["usd"] >= case.theft_min_usd]
    theft_txs = {r["tx"] for r in thefts}
    for r in data["transfers"]:
        det.observe(FlowEvent(r["ts"], "orbit", r["direction"], r["usd"], r["tx"],
                              backed=(False if r["tx"] in theft_txs else None)))
    det.advance(data["end_ts"])

    stolen = sum(r["usd"] for r in thefts)
    first_theft = min((r["ts"] for r in thefts), default=None)
    hack_alerts = [a for a in det.alerts if first_theft is not None and a.started >= first_theft - 3_600]
    false_alarms = [a for a in det.alerts if first_theft is None or a.started < first_theft - 3_600]
    first_alert = min(hack_alerts, key=lambda a: a.started) if hack_alerts else None
    # Funds that left in the same transaction as the alert were already gone; anything later could have been stopped
    after = [r for r in thefts if first_alert and r["ts"] > first_alert.started]
    baseline_days = (first_theft - data["start_ts"]) / 86_400 if first_theft else None
    return {
        "case": case.title,
        "vault": case.vault,
        "escrow_usd_at_start": round(escrow, 2),
        "baseline_days": round(baseline_days, 1) if baseline_days else None,
        "ordinary_transfers": sum(1 for r in data["transfers"] if r["tx"] not in theft_txs),
        "stolen_usd_tracked": round(stolen, 2),
        "thefts": [{"ts": r["ts"], "token": r["token"], "amount": r["amount"], "usd": round(r["usd"], 2),
                    "to": r["counterparty"], "tx": r["tx"]} for r in sorted(thefts, key=lambda r: r["ts"])],
        "alerts": [asdict(a) for a in hack_alerts],
        "first_alert_ts": first_alert.started if first_alert else None,
        "seconds_from_first_theft_to_alert": (first_alert.started - first_theft) if first_alert else None,
        "stolen_before_alert_usd": round(stolen - sum(r["usd"] for r in after), 2) if first_alert else None,
        "stolen_after_alert_usd": round(sum(r["usd"] for r in after), 2) if first_alert else None,
        "minutes_of_warning_for_later_thefts": [round((r["ts"] - first_alert.started) / 60, 1) for r in after] if first_alert else [],
        "false_alarms_during_baseline": len(false_alarms),
        "source": data["source"],
        "fetched": data["fetched"],
        "price_note": data["price_note"],
    }


def _print(result: dict) -> None:
    t = lambda ts: dt.datetime.fromtimestamp(ts, dt.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    print(f"\n{result['case']}\nVault {result['vault']}, tracked escrow at start ${result['escrow_usd_at_start']:,.0f}")
    print(f"Baseline: {result['baseline_days']} days, {result['ordinary_transfers']} ordinary transfers, "
          f"{result['false_alarms_during_baseline']} false alarms\n")
    print("Thefts (releases >= $1M in the hack window):")
    for r in result["thefts"]:
        print(f"  {t(r['ts'])}  {r['amount']:>16,.2f} {r['token']:<5} ${r['usd']:>14,.0f}  -> {r['to']}")
    print("\nAlerts:")
    for a in result["alerts"]:
        print(f"  {t(a['started'])}  {a['severity'].upper():8} {a['rule']:<17} {a['message']}")
    if result["first_alert_ts"]:
        print(f"\nFirst alert {result['seconds_from_first_theft_to_alert']:.0f} s after the first theft. "
              f"Stolen before it: ${result['stolen_before_alert_usd']:,.0f}; after it: ${result['stolen_after_alert_usd']:,.0f} "
              f"(warning of {result['minutes_of_warning_for_later_thefts']} minutes).")
    print(f"\n{result['price_note']}\nSource: {result['source']}, fetched {result['fetched']}.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--fetch", action="store_true", help="re-download the on-chain data first")
    ap.add_argument("--case", default=ORBIT.key, choices=list(CASES))
    args = ap.parse_args()
    case = CASES[args.case]
    import logging
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    data = fetch(case) if args.fetch or not (DATA_DIR / f"{case.key}.json").exists() else None
    _print(run(case, data))
