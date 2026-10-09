"""
Fetch the BridgeWatch evaluation datasets from public Ethereum JSON-RPC (no API keys).

Two kinds of dataset, both in the format of bridgewatch/data/orbit-2023.json:

  hack cases   bridgewatch/data/<key>.json         ~14 days before a known bridge hack
                                                   through a few hours after the drain
  normal       bridgewatch/data/normal/<key>.json  30 believed-normal days (no known
                                                   incident) for live bridges and for
                                                   vaults that were later drained

Each file holds every ERC-20 Transfer of the tracked tokens into or out of the vault,
the vault's balanceOf for each token at start_block, and one USD price per token
(stablecoins fixed at $1, everything else from a Chainlink feed at price_block).

WETH is special: a bridge that pays out native ETH by unwrapping WETH (Ronin) emits
WETH Withdrawal(src=vault), not a Transfer, and one that wraps deposits emits
Deposit(dst=vault). Those events are kept too, as rows with "kind" set to
"weth_unwrap" (out) or "weth_wrap" (in), counterparty = the WETH contract.
Native ETH that never touches WETH is not visible in logs and is not included.

Usage (from prototype/):
  python scripts/fetch_datasets.py --list
  python scripts/fetch_datasets.py                       # everything
  python scripts/fetch_datasets.py nomad-2022 ronin-2022  # selected datasets
  python scripts/fetch_datasets.py --rpc https://rpc.mevblocker.io,https://gateway.tenderly.co/public/mainnet

Resume-safe: every finished getLogs chunk is cached under --cache-dir (default: a
folder in the system temp dir), so an interrupted run picks up where it stopped.
Normal datasets for the live bridges end at a fixed block (LIVE_END_BLOCK) so a
rerun reproduces them; pass --live-end latest to move the window to the chain head.
"""

from __future__ import annotations

import argparse
import datetime as dt
import gzip
import hashlib
import json
import logging
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]          # prototype/
sys.path.insert(0, str(ROOT))
from bridgewatch.onchain import Rpc, RpcError, TRANSFER_TOPIC, _topic, redact  # noqa: E402

DATA_DIR = ROOT / "bridgewatch" / "data"
log = logging.getLogger("fetch_datasets")

ARCHIVE_RPCS = ("https://rpc.mevblocker.io", "https://gateway.tenderly.co/public/mainnet")
WETH_DEPOSIT = "0xe1fffcc4923d04b559f4d29a8bfc6cda04eb5b0d3c460751c2402c5c5cc9109c"     # Deposit(address indexed dst, uint wad)
WETH_WITHDRAWAL = "0x7fcf532c15f0a6db0bd6d0e038bea71d30d808c7d98cb3bf7268a95bf5081b65"  # Withdrawal(address indexed src, uint wad)
MAX_FILE_BYTES = 8_000_000

# ---------------------------------------------------------------- tokens and prices
# symbol -> (address, decimals, price spec). Price spec: a float (fixed USD) or
# ("chainlink", aggregator address, expected description).
TOKENS = {
    "USDT": ("0xdac17f958d2ee523a2206206994597c13d831ec7", 6, 1.0),
    "USDC": ("0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48", 6, 1.0),
    "DAI":  ("0x6b175474e89094c44da98b954eedeac495271d0f", 18, 1.0),
    "FRAX": ("0x853d955acef822db058eb8505911ed77f175b99e", 18, 1.0),
    "WBTC": ("0x2260fac5e5542a773aa44fbcfedf7c193bc2c599", 8, ("chainlink", "0xF4030086522a5bEEa4988F8cA5B36dbC97BeE88c", "BTC / USD")),
    "WETH": ("0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2", 18, ("chainlink", "0x5f4eC3Df9cbd43714FE2740f5E3616155c5b8419", "ETH / USD")),
    "LINK": ("0x514910771af9ca656af840dff83e8264ecf986ca", 18, ("chainlink", "0x2c1d072e956AFFC0D435Cb7AC38EF18d24d9127c", "LINK / USD")),
    "AAVE": ("0x7fc66500c84a76ad7e9c93437bfc5ac33e2ddae9", 18, ("chainlink", "0x547a514d5e3769680Ce22B2361c10Ea13619e8a9", "AAVE / USD")),
    "SUSHI": ("0x6b3595068778dd592e39a122f4f5a5cf09c90fe2", 18, ("chainlink", "0xCc70F09A6CC17553b2E31954cD36E4A2d89501f7", "SUSHI / USD")),
    "FXS":  ("0x3432b6a60d23ca0dfca7761b7ab56459d9c964d0", 18, ("chainlink", "0x6Ebc52C8C1089be9eB3945C4350B68B8E4C2233f", "FXS / USD")),
}
STABLES = ["USDT", "USDC", "DAI"]

# ---------------------------------------------------------------- datasets
# Hack cases. Vault, first-theft tx and block were each confirmed against the
# references AND on-chain (the tx's receipt shows the vault releasing the tokens).
HACKS = [
    {
        "key": "nomad-2022",
        "title": "Nomad token bridge (BridgeRouter proxy), Ethereum, 1-2 Aug 2022",
        "vault": "0x88a69b4e698a4b090df6cf5bd7b2d47325ad30a3",
        "tokens": ["USDT", "USDC", "DAI", "FRAX", "WBTC", "WETH"],
        "start_block": None,                 # None: --days (default 14) before the first theft
        "end_block": 15_266_000,            # ~1 day after the first theft (copycat drain went on for hours)
        "first_theft_block": 15_259_101,
        # Earliest of the four 100-WBTC drains in block 15259101 (log index 0). DeFiHackLabs cites
        # 0xa5fe9d04...5460, the fourth one in the same block; Halborn notes all four.
        "first_theft_tx": "0x61497a1a8a8659a06358e130ea590e1eed8956edbd99dbb2048cfb46850a8f17",
        "hack_window": [15_259_100, 15_266_000],
        "theft_min_usd": 10_000,
        "references": [
            "https://github.com/SunWeb3Sec/DeFiHackLabs/blob/main/src/test/2022-08/NomadBridge_exp.sol",
            "https://www.halborn.com/blog/post/the-nomad-bridge-hack-a-deeper-dive",
            "https://www.certik.com/resources/blog/28fMavD63CpZJOKOjb9DX3-nomad-bridge-exploit-incident-analysis",
            "https://blog.coinbase.com/nomad-bridge-incident-analysis-899b425b0f34",
        ],
        "notes": "Copycat drain: hundreds of addresses replayed the exploit calldata. "
                 "Other drained tokens (e.g. CQT, HBOT, GERO, IAG) are not tracked.",
    },
    {
        "key": "harmony-2022",
        "title": "Harmony Horizon bridge (ERC20 manager), Ethereum, 23 Jun 2022",
        "vault": "0x2dccdb493827e15a5dc8f8b72147e6c4a5620857",
        "tokens": ["USDT", "USDC", "DAI", "FRAX", "WBTC", "WETH", "AAVE", "SUSHI", "FXS"],
        "start_block": None,
        "end_block": 15_014_000,
        "first_theft_block": 15_012_652,
        "first_theft_tx": "0x6e5251068aa99613366fd707f3ed99ce1cb7ffdea05b94568e6af4f460cecd65",
        "hack_window": [15_012_600, 15_014_000],
        "theft_min_usd": 100_000,
        "references": [
            "https://github.com/SunWeb3Sec/DeFiHackLabs/blob/main/src/test/2022-06/Harmony_multisig_exp.sol",
            "https://twitter.com/harmonyprotocol/status/1540110924400324608",
            "https://forklog.com/en/hacker-steals-about-100-million-in-harmonys-horizon-cross-chain-bridge-attack/",
        ],
        "notes": "Released through the 2-of-5 multisig 0x715cdda5e9ad30a0ced14940f9997ee611496de6 to attacker "
                 "0x0d043128146654c7683fbf30ac98d7b2285ded00. The ~13,100 native ETH taken from the separate ETH "
                 "manager 0xf9fb1c508ff49f78b60d3a96dea99fa5d7f3a8a6 is not visible here; nor is the AAG token.",
    },
    {
        "key": "ronin-2022",
        "title": "Ronin bridge (MainchainGateway), Ethereum, 23 Mar 2022",
        "vault": "0x1a2a1c938ce3ec39b6d47113c7955baa9dd454f2",
        "tokens": ["USDC", "WETH"],
        "start_block": None,
        "end_block": 14_444_000,
        "first_theft_block": 14_442_835,
        "first_theft_tx": "0xc28fad5e8d5e0ce6a2eaf67b6687be5d58113e16be590824d6cfa1a94467d0b7",
        "hack_window": [14_442_800, 14_444_000],
        "theft_min_usd": 1_000_000,
        "references": [
            "https://rekt.news/ronin-rekt/",
            "https://github.com/SunWeb3Sec/DeFiHackLabs/blob/main/src/test/2022-03/Ronin_exp.sol",
            "https://etherscan.io/tx/0xc28fad5e8d5e0ce6a2eaf67b6687be5d58113e16be590824d6cfa1a94467d0b7",
            "https://etherscan.io/tx/0xed2c72ef1a552ddaec6dd1f5cddf0b59a8f37f82bdda5257d9c7c37db7bb9b08",
        ],
        "notes": "The 173,600 ETH left as a WETH unwrap (WETH Withdrawal event, src = vault), kept as a "
                 "weth_unwrap row; the 25.5M USDC was an ordinary Transfer. Discovered only on 29 Mar 2022.",
    },
    {
        "key": "multichain-2023",
        "title": "Multichain Fantom bridge (MPC address), Ethereum, 6 Jul 2023",
        "vault": "0xc564ee9f21ed8a2d8e7e76c085740d5e4c5fafbe",
        "tokens": ["USDT", "USDC", "DAI", "WBTC", "WETH", "LINK"],
        "start_block": None,
        "end_block": 17_640_000,
        # 2 USDC "test" release at 16:21 UTC to 0x027f...5cd8, the address that got 27.65M USDC at 18:10.
        # First large release: 0xbd29fe07...7fc4 (block 17,636,491).
        "first_theft_block": 17_635_954,
        "first_theft_tx": "0xde3eed5656263b85d43a89f1d2f6af8fde0d93e49f4642053164d773507323f8",
        "hack_window": [17_635_954, 17_640_000],
        "theft_min_usd": 100_000,
        "references": [
            "https://www.coindesk.com/business/2023/07/06/multichain-bridges-experience-unannounced-outflows-of-over-130m-in-crypto/",
            "https://www.halborn.com/blog/post/explained-the-multichain-hack-july-2023",
            "https://etherscan.io/tx/0x448f2a6a6c071cdce254937e06305a033538e1aeb9339227d0e59e0458e6185c",
        ],
        "notes": "The vault is an EOA (MPC-controlled), so every release is a direct token transfer by it. "
                 "Ordinary small user releases continue inside the hack window; theft_min_usd separates them.",
    },
]

# Believed-normal periods: no known incident on these vaults in these windows.
NORMAL_LIVE_END = 26_140_000
_bridges = json.loads((ROOT / "bridgewatch" / "bridges.json").read_text())["bridges"]
NORMAL = [
    {"key": f"{b['id']}-30d", "title": f"{b['name']} ({b['contract']}), 30 believed-normal days",
     "vault": b["vault"].lower(), "tokens": ["USDT", "USDC", "DAI", "WBTC", "WETH"],
     "end_block": "live", "days": 30, "references": [b["source"]]}
    for b in _bridges
] + [
    {"key": "orbit-2023-normal-30d", "title": "Orbit Chain bridge vault, 30 believed-normal days (Oct 2023, before the Dec 2023 hack)",
     "vault": "0x1bf68a9d1eaee7826b3593c20a0ca93293cb489a", "tokens": ["USDT", "USDC", "DAI", "WBTC", "WETH"],
     "end_block": 18_470_000, "days": 30, "references": ["bridgewatch/data/orbit-2023.json (same vault)"]},
    {"key": "multichain-2023-normal-30d", "title": "Multichain Fantom bridge MPC address, 30 believed-normal days (Mar 2023, before the Jul 2023 drain)",
     "vault": "0xc564ee9f21ed8a2d8e7e76c085740d5e4c5fafbe", "tokens": ["USDT", "USDC", "DAI", "WBTC", "WETH", "LINK"],
     "end_block": 16_940_000, "days": 30,
     "references": ["https://www.coindesk.com/business/2023/07/06/multichain-bridges-experience-unannounced-outflows-of-over-130m-in-crypto/"]},
]


# ---------------------------------------------------------------- RPC helpers
def batch(rpc: Rpc, calls: list[tuple[str, list]]) -> list:
    """JSON-RPC batch (one HTTP request for many calls), with endpoint fallback and retries."""
    last = None
    for attempt in range(4):
        for url in rpc.urls:
            try:
                rpc.calls += 1
                resp = rpc.http.post(url, json=[{"jsonrpc": "2.0", "id": i, "method": m, "params": p}
                                                for i, (m, p) in enumerate(calls)])
                body = resp.json()
                if resp.status_code != 200 or not isinstance(body, list):
                    raise RpcError(f"HTTP {resp.status_code}: {str(body)[:160]}")
                by_id = {r.get("id"): r for r in body}
                if any("result" not in by_id.get(i, {}) for i in range(len(calls))):
                    raise RpcError("batch had errors: " + str([r.get("error") for r in body if "error" in r][:2]))
                time.sleep(rpc.pause)
                return [by_id[i]["result"] for i in range(len(calls))]
            except Exception as e:   # noqa: BLE001 - any failure: try the next endpoint
                last = e
                rpc.errors += 1
                log.warning("batch on %s failed: %s", redact(url), e)
        time.sleep(2 ** attempt)
    raise RpcError(f"batch failed everywhere: {last}")


def block_times(rpc: Rpc, blocks: set[int]) -> None:
    """Fill rpc._ts for the given blocks, 50 per batch request."""
    todo = sorted(b for b in blocks if b not in rpc._ts)
    for i in range(0, len(todo), 50):
        part = todo[i:i + 50]
        for b, blk in zip(part, batch(rpc, [("eth_getBlockByNumber", [hex(b), False]) for b in part])):
            rpc._ts[b] = int(blk["timestamp"], 16)


def block_at(rpc: Rpc, ts: int, lo: int = 1, hi: int | None = None) -> int:
    """First block with timestamp >= ts (binary search)."""
    hi = hi or rpc.head()
    while lo < hi:
        mid = (lo + hi) // 2
        if rpc.block_time(mid) < ts:
            lo = mid + 1
        else:
            hi = mid
    return lo


class ChunkCache:
    """One JSON file per finished getLogs chunk, so an interrupted run resumes."""

    def __init__(self, folder: Path):
        self.folder = folder
        folder.mkdir(parents=True, exist_ok=True)

    def _path(self, params: dict) -> Path:
        return self.folder / (hashlib.sha1(json.dumps(params, sort_keys=True).encode()).hexdigest() + ".json")

    def get(self, params: dict):
        p = self._path(params)
        return json.loads(p.read_text()) if p.exists() else None

    def put(self, params: dict, logs: list) -> None:
        p = self._path(params)
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps(logs))
        tmp.replace(p)


def get_logs(rpc: Rpc, cache: ChunkCache, address: str, topics: list, start: int, end: int, chunk: int) -> list[dict]:
    """eth_getLogs over start..end; chunks that fail are split in half until they succeed."""
    out, stack = [], [(start, min(start + chunk - 1, end))]
    nxt = stack[0][1] + 1
    while stack or nxt <= end:
        if not stack:
            stack.append((nxt, min(nxt + chunk - 1, end)))
            nxt = stack[-1][1] + 1
        a, b = stack.pop()
        params = {"address": address, "fromBlock": hex(a), "toBlock": hex(b), "topics": topics}
        cached = cache.get(params)
        if cached is None:
            try:
                cached = rpc.call("eth_getLogs", [params])
            except RpcError as e:
                if b - a < 50:
                    raise
                mid = (a + b) // 2
                log.info("  splitting %d-%d (%s)", a, b, str(e)[:80])
                stack += [(mid + 1, b), (a, mid)]
                continue
            cache.put(params, cached)
        out += cached
    return out


# ---------------------------------------------------------------- dataset build
def prices_at(rpc: Rpc, symbols: list[str], block: int) -> tuple[dict, list[str]]:
    prices, notes = {}, []
    for s in symbols:
        spec = TOKENS[s][2]
        if isinstance(spec, float):
            prices[s] = spec
            continue
        _, feed, expect = spec
        desc, px = rpc.chainlink_price(feed, block)
        if desc != expect:
            raise RuntimeError(f"Chainlink feed {feed} describes itself as {desc!r}, expected {expect!r}")
        prices[s] = px
        notes.append(f"{s} at Chainlink {expect} {px:,.2f}")
    return prices, notes


def flows(rpc: Rpc, cache: ChunkCache, vault: str, symbols: list[str], prices: dict, start: int, end: int, chunk: int) -> list[dict]:
    rows = []
    v = _topic(vault)
    for s in symbols:
        addr, dec, _ = TOKENS[s]
        queries = [("out", [TRANSFER_TOPIC, v], None), ("in", [TRANSFER_TOPIC, None, v], None)]
        if s == "WETH":
            queries += [("out", [WETH_WITHDRAWAL, v], "weth_unwrap"), ("in", [WETH_DEPOSIT, v], "weth_wrap")]
        for direction, topics, kind in queries:
            logs = get_logs(rpc, cache, addr, topics, start, end, chunk)
            for lg in logs:
                if kind is None and len(lg["topics"]) != 3:
                    continue          # not an ERC-20 Transfer (e.g. ERC-721 style)
                amount = int(lg["data"][:66], 16) / 10 ** dec
                if amount == 0:
                    continue          # zero-value spoof transfers (address poisoning), not real releases
                row = {"ts": int(lg["blockTimestamp"], 16) if lg.get("blockTimestamp") else None,
                       "block": int(lg["blockNumber"], 16), "token": s, "direction": direction,
                       "amount": amount, "usd": amount * prices[s], "tx": lg["transactionHash"],
                       "log_index": int(lg["logIndex"], 16),
                       "counterparty": addr if kind else "0x" + lg["topics"][2 if direction == "out" else 1][-40:]}
                if kind:
                    row["kind"] = kind
                rows.append(row)
            log.info("  %s %s%s: %d logs", s, direction, f" ({kind})" if kind else "", len(logs))
    block_times(rpc, {r["block"] for r in rows if r["ts"] is None})
    for r in rows:
        if r["ts"] is None:
            r["ts"] = rpc._ts[r["block"]]
    rows.sort(key=lambda r: (r["block"], r["log_index"]))
    return rows


def build(rpc: Rpc, cache: ChunkCache, spec: dict, start: int, end: int, price_block: int, label: str) -> dict:
    symbols = spec["tokens"]
    prices, pnotes = prices_at(rpc, symbols, price_block)
    balances = {s: rpc.balance_of(TOKENS[s][0], spec["vault"], start) / 10 ** TOKENS[s][1] for s in symbols}
    rows = flows(rpc, cache, spec["vault"], symbols, prices, start, end, spec.get("chunk", 50_000))
    case = {"key": spec["key"], "title": spec["title"], "vault": spec["vault"],
            "tokens": [[TOKENS[s][0], s, TOKENS[s][1]] for s in symbols],
            "start_block": start, "end_block": end,
            "btc_usd_feed": TOKENS["WBTC"][2][1], "eth_usd_feed": TOKENS["WETH"][2][1],
            "price_block": price_block, "period": label}
    for k in ("theft_min_usd", "hack_window", "first_theft_tx", "first_theft_block", "notes", "references"):
        if k in spec:
            case[k] = spec[k]
    return {
        "case": case,
        "fetched": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat(),
        "source": "Ethereum mainnet via public JSON-RPC (" + ", ".join(redact(u) for u in rpc.urls) + ")",
        "prices_usd": prices,
        "price_note": "Stablecoins and FRAX at $1; " + ("; ".join(pnotes) or "no feed-priced tokens")
                      + f" (answers at block {price_block}). Native ETH is not included except where it passed "
                        "through WETH (rows with kind weth_wrap / weth_unwrap).",
        "start_ts": rpc.block_time(start),
        "end_ts": rpc.block_time(end),
        "balances_at_start": balances,
        "transfers": rows,
    }


def write(path: Path, data: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(data, indent=1) + "\n"
    if len(text.encode()) > MAX_FILE_BYTES:
        path = path.with_suffix(".json.gz")
        with gzip.open(path, "wt", encoding="utf-8") as f:
            f.write(json.dumps(data, separators=(",", ":")) + "\n")
    else:
        path.write_text(text, encoding="utf-8")
    return path


def summary(data: dict) -> str:
    t = data["transfers"]
    lo, hi = data["case"].get("hack_window") or (None, None)
    s = f"{len(t)} transfers ({sum(r['direction']=='in' for r in t)} in / {sum(r['direction']=='out' for r in t)} out)"
    if lo:
        s += f"; USD out in hack window ${sum(r['usd'] for r in t if r['direction']=='out' and lo <= r['block'] <= hi):,.0f}"
    return s


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("keys", nargs="*", help="dataset keys (default: all)")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--rpc", default=",".join(ARCHIVE_RPCS), help="comma-separated archive-capable endpoints, tried in order")
    ap.add_argument("--days", type=float, default=14, help="pre-hack baseline days when a case has no start_block")
    ap.add_argument("--live-end", default=str(NORMAL_LIVE_END), help="end block for live-bridge normal windows, or 'latest'")
    ap.add_argument("--cache-dir", default=str(Path(tempfile.gettempdir()) / "bridgewatch-fetch-cache"))
    ap.add_argument("--out-dir", default=str(DATA_DIR))
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)

    every = {c["key"]: ("hack", c) for c in HACKS} | {c["key"]: ("normal", c) for c in NORMAL}
    if args.list:
        for k, (kind, c) in every.items():
            print(f"{k:32} {kind:7} {c['title']}")
        return
    rpc = Rpc(tuple(u.strip() for u in args.rpc.split(",") if u.strip()), timeout=120, pause=0.2)
    out = Path(args.out_dir)
    for key in args.keys or list(every):
        kind, spec = every[key]
        log.info("== %s", key)
        cache = ChunkCache(Path(args.cache_dir) / key)
        if kind == "hack":
            end = spec["end_block"]
            anchor = spec["first_theft_block"] or spec["hack_window"][0]
            start = spec["start_block"] or block_at(rpc, rpc.block_time(anchor) - int(args.days * 86_400), anchor - 200_000, anchor)
            data = build(rpc, cache, spec, start, end, anchor, "hack: baseline before the incident, then the drain")
            path = write(out / f"{key}.json", data)
        else:
            end = spec["end_block"]
            if end == "live":
                end = rpc.head() - 64 if args.live_end == "latest" else int(args.live_end)
            start = block_at(rpc, rpc.block_time(end) - spec["days"] * 86_400, end - 400_000, end)
            data = build(rpc, cache, spec, start, end, end,
                         "believed-normal: no known incident on this vault in this window")
            path = write(out / "normal" / f"{key}.json", data)
        log.info("   wrote %s (%d bytes): %s", path, path.stat().st_size, summary(data))
    log.info("RPC calls %d, errors %d", rpc.calls, rpc.errors)


if __name__ == "__main__":
    main()
