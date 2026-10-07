"""
Where transfers come from. Every source yields the same records, so the rest of
BridgeWatch (store, detector, alerts, API) doesn't care which one is running:

    for batch in source.batches(cursor):
        detector sees batch.transfers  ->  store saves them and the new cursor

  Transfer     one token movement in or out of a monitored vault
  Batch        the transfers of a block range, plus the cursor (last block covered)
               and safe_time (block time of that last block: nothing earlier is missing)
  Source       anything with batches(cursor) -> Iterator[Batch]

Implementations
  RpcSource    a JSON-RPC node (live mode): eth_getLogs for Transfer events of the
               monitored tokens to/from the monitored vaults, only blocks that have
               the chain's confirmations
  FileSource   a saved dataset file (bridgewatch/data/*.json[.gz], the format of
               orbit-2023.json) for replay, evaluation and load_data
  (later)      SonarX Kafka / warehouse sources produce the same Transfers

to_flow_event() is the one place a Transfer becomes the detector's FlowEvent.
"""

from __future__ import annotations
import gzip
import json
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import Callable, Iterator, Protocol

from .models import FlowEvent
from .onchain import TRANSFER_TOPIC, _topic


@dataclass(frozen=True)
class Transfer:
    chain: str
    block_number: int
    block_time: int
    tx_hash: str
    log_index: int
    bridge: str
    vault: str
    token: str                 # symbol
    direction: str             # "in" | "out" (relative to the vault)
    amount_raw: int            # token units, exact (no float rounding)
    decimals: int
    amount_usd: float | None   # priced when ingested; None = no price was available
    counterparty: str
    block_hash: str | None = None

    @property
    def key(self) -> tuple[str, str, int]:
        return (self.chain, self.tx_hash, self.log_index)

    @property
    def amount(self) -> float:
        return self.amount_raw / 10 ** self.decimals


@dataclass
class Batch:
    transfers: list[Transfer]
    chain: str
    cursor: int                # last block this batch covers
    safe_time: float           # block time of `cursor`


class Source(Protocol):
    def batches(self, cursor: int | None) -> Iterator[Batch]: ...


def to_flow_event(t: Transfer, confirm_seconds: float = 0.0) -> FlowEvent | None:
    """The detector's view of a transfer. None when it has no USD value (no price)."""
    if t.amount_usd is None:
        return None
    return FlowEvent(t.block_time, t.bridge, t.direction, t.amount_usd, t.tx_hash,
                     log_index=t.log_index, confirmed_at=t.block_time + confirm_seconds)


def transfer_from_row(r: dict) -> Transfer:
    """A row of the store's transfers table back as a Transfer."""
    return Transfer(chain=r["chain"], block_number=r["block_number"], block_time=r["block_time"],
                    tx_hash=r["tx_hash"], log_index=r["log_index"], bridge=r["bridge"], vault=r["vault"],
                    token=r["token"], direction=r["direction"], amount_raw=int(r["amount_raw"]),
                    decimals=r["decimals"], amount_usd=r["amount_usd"], counterparty=r["counterparty"],
                    block_hash=r["block_hash"])


def sort_key(t: Transfer) -> tuple:
    return (t.block_time, t.block_number, t.log_index)


# --- live: a JSON-RPC node ---------------------------------------------------------
@dataclass
class RpcSource:
    """Reads confirmed blocks from a node. `vaults` maps vault address -> bridge id;
    `tokens` maps token address -> (symbol, decimals); `price` gives the current USD
    price of a symbol (None if unknown), applied at ingest."""
    rpc: object
    chain: str
    vaults: dict[str, str]
    tokens: dict[str, tuple[str, int]]
    price: Callable[[str], float | None]
    confirmations: int = 6
    block_time_s: float = 12.0
    history_days: float = 7
    chunk_blocks: int = 2_000
    head: int | None = field(default=None, init=False)
    safe_head: int | None = field(default=None, init=False)

    def tip(self) -> tuple[int, int]:
        """(chain head, newest block with enough confirmations)."""
        self.head = self.rpc.head()
        self.safe_head = self.head - self.confirmations
        return self.head, self.safe_head

    def history_blocks(self) -> int:
        return int(self.history_days * 86_400 / self.block_time_s)

    def batches(self, cursor: int | None, max_blocks: int | None = None) -> Iterator[Batch]:
        """Batches from the block after `cursor` up to the confirmed head, chunk_blocks
        at a time. With no cursor (first run) it starts history_days back. Never more
        than history_days behind the head (older blocks can't affect the baseline)."""
        _, safe = self.tip()
        start = safe - self.history_blocks()
        if cursor is not None:
            start = max(cursor + 1, start)
        end_all = safe if max_blocks is None else min(safe, start + max_blocks - 1)
        b = start
        while b <= end_all:
            e = min(b + self.chunk_blocks - 1, end_all)
            yield self.fetch(b, e)
            b = e + 1

    def fetch(self, start: int, end: int) -> Batch:
        """Every transfer of a monitored token in or out of a monitored vault, blocks start..end."""
        # The block time of `end` first: if it fails, nothing has been read or stored yet.
        safe_time = self.rpc.block_time(end)
        vault_topics = {_topic(v): (v.lower(), bridge) for v, bridge in self.vaults.items()}
        topics_list = list(vault_topics)
        out = []
        for direction, topics in (("out", [TRANSFER_TOPIC, topics_list]), ("in", [TRANSFER_TOPIC, None, topics_list])):
            for lg in self.rpc.logs(list(self.tokens), topics, start, end):
                tok = self.tokens.get(lg["address"].lower())
                if tok is None or len(lg["topics"]) < 3:
                    continue
                hit = vault_topics.get(lg["topics"][1 if direction == "out" else 2].lower())
                if hit is None:
                    continue
                vault, bridge = hit
                symbol, decimals = tok
                raw = int(lg["data"], 16)
                price = self.price(symbol)
                out.append(Transfer(
                    chain=self.chain, block_number=int(lg["blockNumber"], 16), block_time=int(lg["ts"]),
                    tx_hash=lg["transactionHash"], log_index=int(lg["logIndex"], 16), bridge=bridge, vault=vault,
                    token=symbol, direction=direction, amount_raw=raw, decimals=decimals,
                    amount_usd=None if price is None else raw / 10 ** decimals * price,
                    counterparty="0x" + lg["topics"][2 if direction == "out" else 1][-40:],
                    block_hash=lg.get("blockHash")))
        out.sort(key=sort_key)
        return Batch(out, self.chain, end, safe_time)


# --- saved datasets -------------------------------------------------------------------
def find_datasets(root: str | Path) -> list[Path]:
    """Every dataset file under root (including subfolders such as normal/), sorted."""
    root = Path(root)
    return sorted(p for p in root.rglob("*") if p.is_file() and (p.name.endswith(".json") or p.name.endswith(".json.gz")))


def _read_json(path: Path) -> dict:
    if path.name.endswith(".gz"):
        with gzip.open(path, "rt", encoding="utf-8") as f:
            return json.load(f)
    return json.loads(path.read_text(encoding="utf-8"))


def _raw_units(amount: float, decimals: int) -> int:
    # Dataset files store float amounts; str() keeps the digits that were written.
    return int(Decimal(str(amount)) * (Decimal(10) ** decimals))


class FileSource:
    """A dataset file: {"case": {key, title, vault, tokens[[address, symbol, decimals]],
    start_block, end_block, hack_window?, theft_min_usd?, ...}, "prices_usd", "balances_at_start",
    "start_ts", "end_ts", "transfers": [{ts, block, token, direction, amount, usd, tx,
    log_index, counterparty, kind?}]}. Plain .json or .json.gz.

    The bridge id of every transfer is the case key, so datasets never mix with each
    other or with live bridges in the store or the detector."""

    def __init__(self, path: str | Path, chunk_blocks: int = 50_000):
        self.path = Path(path)
        self.data = _read_json(self.path)
        self.case: dict = self.data["case"]
        self.key: str = self.case["key"]
        self.title: str = self.case.get("title", self.key)
        self.chain: str = self.case.get("chain", "ethereum")
        self.vault: str = self.case["vault"].lower()
        self.decimals = {sym: int(dec) for _, sym, dec in self.case.get("tokens", [])}
        self.prices: dict[str, float] = self.data.get("prices_usd", {})
        self.start_ts: float = self.data["start_ts"]
        self.end_ts: float = self.data["end_ts"]
        self.chunk_blocks = chunk_blocks

    @property
    def kind(self) -> str:
        """'hack' when the case marks a hack window, else 'normal'."""
        return "hack" if self.case.get("hack_window") else "normal"

    @property
    def escrow_usd_at_start(self) -> float:
        return sum(bal * self.prices.get(sym, 0.0) for sym, bal in self.data.get("balances_at_start", {}).items())

    def transfers(self) -> list[Transfer]:
        out = []
        for r in self.data["transfers"]:
            dec = self.decimals.get(r["token"], 18)
            out.append(Transfer(
                chain=self.chain, block_number=int(r["block"]), block_time=int(r["ts"]), tx_hash=r["tx"],
                log_index=int(r["log_index"]), bridge=self.key, vault=self.vault, token=r["token"],
                direction=r["direction"], amount_raw=_raw_units(r["amount"], dec), decimals=dec,
                amount_usd=r.get("usd"), counterparty=r.get("counterparty", "")))
        out.sort(key=sort_key)
        return out

    def batches(self, cursor: int | None = None) -> Iterator[Batch]:
        """The file's transfers after `cursor`, chunk_blocks blocks per batch."""
        rows = [t for t in self.transfers() if cursor is None or t.block_number > cursor]
        i = 0
        while i < len(rows):
            limit = rows[i].block_number + self.chunk_blocks
            j = i
            while j < len(rows) and rows[j].block_number < limit:
                j += 1
            part = rows[i:j]
            yield Batch(part, self.chain, part[-1].block_number, part[-1].block_time)
            i = j
