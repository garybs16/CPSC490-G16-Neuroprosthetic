"""
Validate dataset files built by fetch_more.py (or any file in the orbit-2023.json format).

Checks per file
  schema        required top-level and case keys; hack files need hack_window, first_theft_*, theft_min_usd
  rows          every row has the row keys, amount > 0, block inside [start_block, end_block],
                ts inside [start_ts, end_ts], usd == amount * price, token is one of the case tokens
  duplicates    no repeated (tx, log_index, token, direction)
  decimals      decimals() on-chain equals the case's decimals for every token
  balance       balanceOf(vault, start_block) equals balances_at_start for every token, and
                balances_at_start + in - out (rows after start_block; balances_at_start is the balance
                at the end of start_block) equals balanceOf(vault, end_block) (catches missing rows)
  first theft   the receipt of first_theft_tx is in first_theft_block, and (unless the case says
                the theft moved no tokens on Ethereum) it has a Transfer of a tracked token out of
                the vault that is also a row in the file

Usage: python validate.py [files...]   (default: hacks/* and normal/* next to this script)
Prints one line per check and writes nothing.
"""

from __future__ import annotations

import gzip
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROTO = HERE.parents[2] / "prototype"
sys.path.insert(0, str(PROTO))
from bridgewatch.onchain import Rpc, TRANSFER_TOPIC, _topic  # noqa: E402

RPCS = ("https://gateway.tenderly.co/public/mainnet", "https://rpc.mevblocker.io")
CASE_KEYS = {"key", "title", "vault", "tokens", "start_block", "end_block"}
HACK_KEYS = {"hack_window", "first_theft_tx", "first_theft_block", "theft_min_usd", "references", "coverage"}
TOP_KEYS = {"case", "prices_usd", "balances_at_start", "start_ts", "end_ts", "transfers"}
ROW_KEYS = {"ts", "block", "token", "direction", "amount", "usd", "tx", "log_index", "counterparty"}
WETH = "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2"


def load(p: Path) -> dict:
    if p.name.endswith(".gz"):
        with gzip.open(p, "rt", encoding="utf-8") as f:
            return json.load(f)
    return json.loads(p.read_text(encoding="utf-8"))


def close(a: float, b: float, rel: float = 1e-9, abs_: float = 1e-9) -> bool:
    return abs(a - b) <= max(abs_, rel * max(abs(a), abs(b)))


def validate(rpc: Rpc, path: Path) -> list[tuple[str, bool, str]]:
    out = []
    d = load(path)
    c = d.get("case", {})
    hack = bool(c.get("hack_window"))
    miss = (TOP_KEYS - d.keys()) | (CASE_KEYS - c.keys()) | ((HACK_KEYS - c.keys()) if hack else set())
    out.append(("schema", not miss, f"missing {sorted(miss)}" if miss else "ok"))
    vault = c["vault"].lower()
    toks = {sym: (addr.lower(), int(dec)) for addr, sym, dec in c["tokens"]}
    prices = d["prices_usd"]
    rows = d["transfers"]

    bad = []
    for r in rows:
        if ROW_KEYS - r.keys():
            bad.append(f"keys {r.get('tx')}")
        elif r["token"] not in toks or r["direction"] not in ("in", "out"):
            bad.append(f"token/direction {r['tx']}")
        elif not r["amount"] > 0:
            bad.append(f"amount {r['tx']}")
        elif not c["start_block"] <= r["block"] <= c["end_block"] or not d["start_ts"] <= r["ts"] <= d["end_ts"]:
            bad.append(f"range {r['tx']}")
        elif not close(r["usd"], r["amount"] * prices[r["token"]], 1e-6):
            bad.append(f"usd {r['tx']}")
    out.append(("rows", not bad, f"{len(rows)} rows ok" if not bad else f"{len(bad)} bad, e.g. {bad[:3]}"))
    keys = [(r["tx"], r["log_index"], r["token"], r["direction"]) for r in rows]
    out.append(("duplicates", len(keys) == len(set(keys)), f"{len(keys) - len(set(keys))} duplicates"))

    dec_bad = [s for s, (a, dec) in toks.items()
               if int(rpc.call("eth_call", [{"to": a, "data": "0x313ce567"}, hex(c["end_block"])]), 16) != dec]
    out.append(("decimals", not dec_bad, f"mismatch {dec_bad}" if dec_bad else f"{len(toks)} tokens ok"))

    bal_msgs, bal_ok = [], True
    for s, (a, dec) in toks.items():
        b0 = rpc.balance_of(a, vault, c["start_block"]) / 10 ** dec
        b1 = rpc.balance_of(a, vault, c["end_block"]) / 10 ** dec
        # balances_at_start is balanceOf at the END of start_block (the prototype's convention), so rows
        # in start_block itself are already inside it: reconcile with the rows after start_block.
        net = sum(r["amount"] if r["direction"] == "in" else -r["amount"] for r in rows
                  if r["token"] == s and r["block"] > c["start_block"])
        ok0 = close(b0, d["balances_at_start"].get(s, -1), 1e-9, 1e-6)
        ok1 = close(b0 + net, b1, 1e-6, max(1e-6, 1e-9 * abs(b1)) + 10 ** -dec * 10)
        bal_ok &= ok0 and ok1
        if not (ok0 and ok1):
            bal_msgs.append(f"{s}: start {b0} vs file {d['balances_at_start'].get(s)}; start+net {b0 + net} vs end {b1}")
    out.append(("balance", bal_ok, "; ".join(bal_msgs) if bal_msgs else f"start and start+in-out=end ok for {len(toks)} tokens"))

    if hack:
        tx = c["first_theft_tx"]
        rc = rpc.call("eth_getTransactionReceipt", [tx])
        blk_ok = int(rc["blockNumber"], 16) == c["first_theft_block"] and rc["status"] == "0x1"
        addr2sym = {a: s for s, (a, _) in toks.items()}
        moved = [(addr2sym[lg["address"].lower()], int(lg["logIndex"], 16)) for lg in rc["logs"]
                 if lg["topics"][0] == TRANSFER_TOPIC and len(lg["topics"]) == 3
                 and lg["address"].lower() in addr2sym and lg["topics"][1].lower() == _topic(vault)]
        in_file = {(r["tx"], r["log_index"]) for r in rows}
        no_move_expected = "NEGATIVE CONTROL" in c.get("notes", "")
        if no_move_expected:
            ok = blk_ok and not moved
            msg = f"receipt in block {int(rc['blockNumber'], 16)}; moves no tracked tokens out of the vault (expected)"
        else:
            ok = blk_ok and bool(moved) and all((tx, li) in in_file for _, li in moved)
            msg = f"receipt in block {int(rc['blockNumber'], 16)}; vault releases {[m[0] for m in moved]}; rows present: {ok}"
        out.append(("first_theft", ok, msg))
    return out


def main() -> None:
    files = [Path(f) for f in sys.argv[1:]] or sorted(p for sub in ("hacks", "normal") for p in (HERE / sub).glob("*.json*"))
    rpc = Rpc(RPCS, timeout=120, pause=0.05)
    all_ok = True
    for p in files:
        res = validate(rpc, p)
        ok = all(r[1] for r in res)
        all_ok &= ok
        print(f"{'PASS' if ok else 'FAIL'} {p.name}")
        for name, good, msg in res:
            print(f"   {'ok ' if good else 'BAD'} {name:12} {msg}")
    print("ALL PASS" if all_ok else "SOME CHECKS FAILED")


if __name__ == "__main__":
    main()
