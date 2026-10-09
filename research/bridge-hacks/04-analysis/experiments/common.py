"""
Shared loading code for the BridgeWatch detection experiments (04-analysis).

Nothing here modifies the prototype. It imports `bridgewatch` read-only from a
prototype folder (pass --prototype, or set BW_PROTOTYPE; run against a COPY of
prototype/ so no __pycache__ lands in the repo) and reads the datasets from:

  <research>/03-onchain-data/hacks/*.json         10 hack cases (incl. qubit negative control)
  <research>/03-onchain-data/normal/*.json[.gz]   10 normal / stress-normal windows
  <prototype>/bridgewatch/data/*.json             5 earlier hack cases
  <prototype>/bridgewatch/data/normal/*.json      5 earlier normal windows

Simulated pipeline (same as bridgewatch.replay): a transfer at block time t is
seen at the first 15 s poll after t + 6 x 12 s.
"""
from __future__ import annotations

import argparse
import datetime as dt
import math
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True

HERE = Path(__file__).resolve().parent
RESEARCH = HERE.parent.parent                      # research/bridge-hacks
REPO = RESEARCH.parent.parent
OUT = HERE / "out"

CONFIRM_S = 6 * 12.0
POLL_S = 15.0
WARMUP_S = 3 * 86_400
WEEK = 7 * 86_400


def detected_at(block_ts: float) -> float:
    """When live mode would see a transfer (first poll after 6 confirmations)."""
    return math.ceil((block_ts + CONFIRM_S) / POLL_S) * POLL_S


# Bridge design per dataset key (from the catalog's design column and the 03 README).
DESIGN = {
    # lock-box escrows (validator / multisig / message-verified lock-mint)
    "poly-2021": "lockbox", "poly-2023": "lockbox", "heco-2023": "lockbox", "ronin-2024": "lockbox",
    "force-bridge-2025": "lockbox", "shibarium-2025": "lockbox", "verus-2026": "lockbox",
    "xbridge-2024": "lockbox", "qubit-2022": "lockbox", "harmony-2022": "lockbox", "nomad-2022": "lockbox",
    "orbit-2023": "lockbox", "ronin-2022": "lockbox",
    "wormhole-portal-30d": "lockbox", "wormhole-portal-ftx-2022": "lockbox", "polygon-pos-erc20-30d": "lockbox",
    "polygon-pos-erc20-usdc-depeg-2023": "lockbox", "ronin-gateway-30d": "lockbox",
    "orbit-2023-normal-30d": "lockbox",
    # canonical rollup L1 gateways (lock-box too, with 7-day / challenge exits)
    "arbitrum-30d": "rollup", "base-30d": "rollup", "optimism-30d": "rollup",
    # LayerZero OFT adapters (lock-box whose releases come from LZ packets)
    "kelp-2026": "oft-adapter", "kelp-rseth-adapter-prehack-30d": "oft-adapter",
    "usdt0-oft-adapter-30d": "oft-adapter",
    # liquidity pools / intent spoke pools
    "stargate-v2-usdc-30d": "pool", "across-spokepool-7d": "pool", "celer-cbridge-30d": "pool",
    # MPC custody (EOA vault)
    "multichain-2023": "mpc", "multichain-2023-normal-30d": "mpc",
}
STRESS = {"wormhole-portal-ftx-2022", "polygon-pos-erc20-usdc-depeg-2023"}

# Native ETH thefts that Transfer logs cannot see (03-onchain-data/README.md and each case block).
# key -> (UTC time of the native theft, ETH amount, ETH/USD at the theft block per price_note)
NATIVE_ETH = {
    "poly-2021": ("2021-08-10 09:51:02", 2_857.49, 3_152.69),
    "heco-2023": ("2023-11-22 09:59:35", 10_145.0, 2_008.04),
    "ronin-2024": ("2024-08-06 09:37:23", 3_996.0, 2_449.48),
    "force-bridge-2025": ("2025-06-01 07:16:47", 539.09, 2_518.6),
    "shibarium-2025": ("2025-09-12 18:44:47", 224.57, 4_621.64),
    "verus-2026": ("2026-05-17 23:55:23", 1_625.37, 2_126.37),
}


def utc(s: str) -> float:
    return dt.datetime.strptime(s, "%Y-%m-%d %H:%M:%S").replace(tzinfo=dt.timezone.utc).timestamp()


def fmt_ts(ts: float | None) -> str:
    return dt.datetime.fromtimestamp(ts, dt.timezone.utc).strftime("%Y-%m-%d %H:%M:%S") if ts else ""


def parser(desc: str) -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=desc)
    ap.add_argument("--prototype", default=os.environ.get("BW_PROTOTYPE", str(REPO / "prototype")),
                    help="a COPY of prototype/ (bridgewatch is imported read-only from here)")
    ap.add_argument("--research", default=str(RESEARCH), help="research/bridge-hacks folder")
    return ap


def setup(args) -> None:
    sys.path.insert(0, str(Path(args.prototype).resolve()))
    OUT.mkdir(parents=True, exist_ok=True)


def dataset_paths(args) -> list[Path]:
    r = Path(args.research) / "03-onchain-data"
    p = Path(args.prototype) / "bridgewatch" / "data"
    files = sorted((r / "hacks").glob("*.json")) + sorted(p.glob("*.json"))
    files += sorted((r / "normal").glob("*.json*")) + sorted((p / "normal").glob("*.json*"))
    return files


class Dataset:
    """A dataset file plus the labels the experiments need."""

    def __init__(self, path: Path):
        from bridgewatch.source import FileSource   # imported after setup()
        self.src = FileSource(path)
        self.key = self.src.key
        self.path = path
        self.case = self.src.case
        self.kind = self.src.kind                      # hack | normal
        self.design = DESIGN.get(self.key, "unknown")
        self.stress = self.key in STRESS
        self.start_ts, self.end_ts = self.src.start_ts, self.src.end_ts
        self.transfers = self.src.transfers()
        self.escrow0 = self.src.escrow_usd_at_start
        self.thefts = []
        self.first_theft_ts = self.last_theft_ts = None
        if self.kind == "hack":
            lo, hi = self.case["hack_window"]
            tmin = self.case.get("theft_min_usd", 1_000_000)
            # Same definition as bridgewatch.replay: outflows >= theft_min_usd inside hack_window
            self.thefts = [t for t in self.transfers if t.direction == "out" and lo <= t.block_number <= hi
                           and t.amount_usd is not None and t.amount_usd >= tmin]
            if self.thefts:
                self.first_theft_ts = min(t.block_time for t in self.thefts)
                self.last_theft_ts = max(t.block_time for t in self.thefts)
        self.theft_keys = {(t.tx_hash, t.log_index, t.token) for t in self.thefts}
        # FileSource drops the row's "kind" (weth_wrap / weth_unwrap); keep it here.
        self.kinds = {(r["tx"], int(r["log_index"]), r["token"]): r.get("kind") or ""
                      for r in self.src.data["transfers"] if r.get("kind")}

    def kind_of(self, t) -> str:
        return self.kinds.get((t.tx_hash, t.log_index, t.token), "")

    @property
    def role(self) -> str:
        if self.kind == "hack":
            return "hack"
        return "stress" if self.stress else "normal"

    def fa_period(self) -> tuple[float, float] | None:
        """Time span in which every alert counts as a false alarm (after warm-up)."""
        lo = self.start_ts + WARMUP_S
        if self.kind == "normal":
            hi = self.end_ts
        elif self.first_theft_ts is not None:
            hi = self.first_theft_ts - 3_600
        else:
            return None
        return (lo, hi) if hi > lo else None

    def fa_weeks(self) -> float:
        p = self.fa_period()
        return (p[1] - p[0]) / WEEK if p else 0.0

    def is_theft(self, t) -> bool:
        return (t.tx_hash, t.log_index, t.token) in self.theft_keys

    def stolen_usd(self) -> float:
        return sum(t.amount_usd for t in self.thefts)


def load_all(args) -> list[Dataset]:
    return [Dataset(p) for p in dataset_paths(args)]
