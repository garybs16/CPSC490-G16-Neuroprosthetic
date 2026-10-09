"""
Real on-chain data: ERC-20 flows in and out of a bridge vault, read straight
from an Ethereum node over JSON-RPC.

This is the stand-in for SonarX until access arrives. It reads Transfer logs
for a list of tokens where the vault is the sender (a release) or receiver (a
deposit), so it sees what left the bridge but not why. Limits:
  - Native ETH moves in transactions, not logs, so it is not covered here.
  - Free public RPCs cap block ranges and rate; requests are chunked and
    retried, and fall back to a second endpoint.
  - Endpoint URLs can contain API keys, so logs show only scheme://host (redact()).

scripts/fetch_datasets.py imports Rpc, RpcError, TRANSFER_TOPIC and _topic, and
uses Rpc.call/head/block_time/balance_of/chainlink_price and Rpc._ts: keep them.
"""

from __future__ import annotations
import logging
import time
from collections import OrderedDict
from urllib.parse import urlsplit

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


def redact(url: str) -> str:
    """scheme://host only: paths and query strings often carry API keys."""
    parts = urlsplit(url)
    return f"{parts.scheme}://{parts.hostname}" if parts.hostname else "<rpc>"


class LruDict(OrderedDict):
    """A dict that forgets its least recently used entries beyond maxsize (block timestamps)."""

    def __init__(self, maxsize: int):
        super().__init__()
        self.maxsize = maxsize

    def __getitem__(self, key):
        value = super().__getitem__(key)
        self.move_to_end(key)
        return value

    def __setitem__(self, key, value):
        super().__setitem__(key, value)
        self.move_to_end(key)
        while len(self) > self.maxsize:
            self.popitem(last=False)


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

    def __init__(self, urls: tuple[str, ...] = PUBLIC_RPCS, timeout: float = 90, retries: int = 3, pause: float = 0.3,
                 ts_cache_size: int = 200_000):
        self.urls, self.retries, self.pause = urls, retries, pause
        self.http = httpx.Client(timeout=timeout, headers={"User-Agent": "BridgeWatch/0.1"})
        self._ts: LruDict = LruDict(ts_cache_size)   # block number -> timestamp
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
                    log.info("%s refused %s (%s); trying the next endpoint", redact(url), method, e)
                    break
                except (httpx.TransportError, RpcError) as e:
                    last = e
                    self.errors += 1
                    log.warning("%s %s failed (%s), attempt %d", redact(url), method, e, attempt + 1)
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
        desc, price, _ = self.chainlink_round(feed, block)
        return desc, price

    def chainlink_round(self, feed: str, block: int | str = "latest") -> tuple[str, float, int]:
        """(description, price, updatedAt unix seconds) from a Chainlink aggregator at a block."""
        tag = hex(block) if isinstance(block, int) else block
        raw = bytes.fromhex(self.call("eth_call", [{"to": feed, "data": "0x7284e416"}, tag])[2:])
        desc = raw[64:64 + int.from_bytes(raw[32:64], "big")].decode()
        dec = int(self.call("eth_call", [{"to": feed, "data": "0x313ce567"}, tag]), 16)
        r = self.call("eth_call", [{"to": feed, "data": "0xfeaf968c"}, tag])   # latestRoundData()
        # five words: roundId, answer, startedAt, updatedAt, answeredInRound
        answer, updated_at = int(r[2 + 64:2 + 128], 16), int(r[2 + 192:2 + 256], 16)
        return desc, answer / 10 ** dec, updated_at
