"""
Real on-chain data: ERC-20 flows in and out of a bridge vault, read straight
from an Ethereum node over JSON-RPC.

This is the stand-in for SonarX until access arrives. It reads Transfer logs
for a list of tokens where the vault is the sender (a release) or receiver (a
deposit), so it sees what left the bridge but not why. Limits:
  - Native ETH moves in transactions, not logs, so it is not covered here.
  - Free public RPCs cap block ranges and rate; requests are chunked and
    retried, and fall back to a second endpoint.
  - USD values use the prices passed in (fixed per replay), not a price feed
    per transfer.
"""

from __future__ import annotations
import json
import logging
import time
from dataclasses import dataclass

import httpx

log = logging.getLogger("bridgewatch.onchain")

TRANSFER_TOPIC = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"  # Transfer(address,address,uint256)
PUBLIC_RPCS = ("https://rpc.mevblocker.io", "https://gateway.tenderly.co/public/mainnet")
# For recent blocks (live monitoring) publicnode also works; it refuses archive queries without a token.
LIVE_RPCS = ("https://ethereum-rpc.publicnode.com",) + PUBLIC_RPCS


class RpcError(Exception):
    pass


def _topic(address: str) -> str:
    return "0x" + "0" * 24 + address.lower()[2:]


@dataclass(frozen=True)
class Token:
    address: str
    symbol: str
    decimals: int
    price_usd: float


class Refused(RpcError):
    """The endpoint will never serve this request (e.g. archive data on a free tier): don't retry it there."""


def _refusal(status: int, err: dict | None) -> bool:
    if status in (400, 401, 403, 404, 405):
        return True
    if err is None:
        return False
    msg = str(err.get("message", "")).lower()
    return err.get("code") in (-32601, -32602) or any(w in msg for w in ("archive", "not supported", "require"))


class Rpc:
    """Minimal JSON-RPC client. Transient failures (timeouts, 429, 5xx) are retried
    with backoff; refusals move straight to the next endpoint. The endpoint that
    last answered is tried first next time."""

    def __init__(self, urls: tuple[str, ...] = PUBLIC_RPCS, timeout: float = 90, retries: int = 3, pause: float = 0.3):
        self.urls, self.retries, self.pause = urls, retries, pause
        self.http = httpx.Client(timeout=timeout, headers={"User-Agent": "BridgeWatch/0.1"})
        self._ts: dict[int, int] = {}
        self._preferred = 0
        self.calls = 0
        self.errors = 0

    def call(self, method: str, params: list):
        last = None
        n = len(self.urls)
        for k in range(n):
            i = (self._preferred + k) % n
            url = self.urls[i]
            for attempt in range(self.retries):
                try:
                    self.calls += 1
                    resp = self.http.post(url, json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params})
                    if resp.status_code in (429, 500, 502, 503, 504):
                        raise RpcError(f"HTTP {resp.status_code}")
                    try:
                        body = resp.json()
                    except ValueError:
                        body = {}
                    err = body.get("error") if isinstance(body, dict) else None
                    if resp.status_code != 200 or err is not None or "result" not in body:
                        cls = Refused if _refusal(resp.status_code, err) else RpcError
                        raise cls(f"HTTP {resp.status_code} {str(err)[:160] if err else ''}".strip())
                    self._preferred = i
                    time.sleep(self.pause)   # stay under free-tier rate limits
                    return body["result"]
                except Refused as e:
                    last = e
                    self.errors += 1
                    log.info("%s refused %s (%s); trying the next endpoint", url, method, e)
                    break
                except (httpx.TransportError, RpcError) as e:
                    last = e
                    self.errors += 1
                    log.warning("%s %s failed (%s), attempt %d", url, method, e, attempt + 1)
                    time.sleep(2 ** attempt)
        raise RpcError(f"All RPC endpoints failed for {method}: {last}")

    def block_time(self, block: int) -> int:
        if block not in self._ts:
            self._ts[block] = int(self.call("eth_getBlockByNumber", [hex(block), False])["timestamp"], 16)
        return self._ts[block]

    def head(self) -> int:
        return int(self.call("eth_blockNumber", []), 16)

    def balance_of(self, token: str, holder: str, block: int | str) -> int:
        data = "0x70a08231" + _topic(holder)[2:]
        tag = hex(block) if isinstance(block, int) else block
        return int(self.call("eth_call", [{"to": token, "data": data}, tag]), 16)

    def logs(self, addresses: list[str], topics: list, start: int, end: int, chunk: int = 5_000) -> list[dict]:
        """eth_getLogs over start..end in chunks. Adds 'ts' to each log (from the node's
        blockTimestamp when it sends one, else one block lookup per block)."""
        out, b = [], start
        while b <= end:
            e = min(b + chunk - 1, end)
            out += self.call("eth_getLogs", [{"address": addresses, "fromBlock": hex(b), "toBlock": hex(e), "topics": topics}])
            b = e + 1
        for lg in out:
            bt = lg.get("blockTimestamp")
            lg["ts"] = int(bt, 16) if bt else self.block_time(int(lg["blockNumber"], 16))
        return out

    def chainlink_price(self, feed: str, block: int | str = "latest") -> tuple[str, float]:
        """(description, price) from a Chainlink aggregator at a block."""
        tag = hex(block) if isinstance(block, int) else block
        raw = bytes.fromhex(self.call("eth_call", [{"to": feed, "data": "0x7284e416"}, tag])[2:])
        desc = raw[64:64 + int.from_bytes(raw[32:64], "big")].decode()
        dec = int(self.call("eth_call", [{"to": feed, "data": "0x313ce567"}, tag]), 16)
        r = self.call("eth_call", [{"to": feed, "data": "0xfeaf968c"}, tag])   # latestRoundData()
        answer = int(r[2 + 64:2 + 128], 16)
        return desc, answer / 10 ** dec

    def transfers(self, token: str, vault: str, start: int, end: int, direction: str, chunk: int = 5_000) -> list[dict]:
        """Transfer logs of `token` out of (direction='out') or into ('in') `vault`, blocks start..end."""
        topics = [TRANSFER_TOPIC, _topic(vault)] if direction == "out" else [TRANSFER_TOPIC, None, _topic(vault)]
        logs, b = [], start
        while b <= end:
            e = min(b + chunk - 1, end)
            logs += self.call("eth_getLogs", [{"address": token, "fromBlock": hex(b), "toBlock": hex(e), "topics": topics}])
            b = e + 1
        return logs


def fetch_vault_flows(rpc: Rpc, vault: str, tokens: list[Token], start: int, end: int) -> list[dict]:
    """Every in/out transfer of the given tokens for the vault, as plain dicts (for caching)."""
    rows = []
    for tok in tokens:
        for direction in ("out", "in"):
            for lg in rpc.transfers(tok.address, vault, start, end, direction):
                block = int(lg["blockNumber"], 16)
                amount = int(lg["data"], 16) / 10 ** tok.decimals
                counterparty = "0x" + lg["topics"][2 if direction == "out" else 1][-40:]
                rows.append({"ts": rpc.block_time(block), "block": block, "token": tok.symbol,
                             "direction": direction, "amount": amount, "usd": amount * tok.price_usd,
                             "tx": lg["transactionHash"], "log_index": int(lg["logIndex"], 16),
                             "counterparty": counterparty})
            log.info("%s %s: %d transfers so far", tok.symbol, direction, len(rows))
    rows.sort(key=lambda r: (r["block"], r["log_index"]))
    return rows


def save(path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=1) + "\n", encoding="utf-8")
