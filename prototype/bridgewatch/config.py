"""
All configuration in one place.

  settings_from_env()   every BRIDGEWATCH_* environment variable, read once
  detector_config()     the one DetectorConfig, built from those settings
  load_registry()       bridges.json: chains, tokens, bridges and per-bridge overrides

Environment variables (all optional):
  BRIDGEWATCH_MODE             live (default) | demo
  BRIDGEWATCH_DB               SQLite file (default bridgewatch.db)
  BRIDGEWATCH_CHAIN            which chain of bridges.json live mode watches (default ethereum)
  BRIDGEWATCH_RPC_URLS         comma-separated JSON-RPC endpoints, tried in order
  BRIDGEWATCH_RPC_PAUSE        seconds to wait after each RPC call (default 0.3; free tiers rate-limit)
  BRIDGEWATCH_POLL_SECONDS     default 15
  BRIDGEWATCH_CONFIRMATIONS    overrides the chain's confirmation count from bridges.json
  BRIDGEWATCH_HISTORY_DAYS     baseline window AND first-run backfill (default 7)
  BRIDGEWATCH_Z_THRESHOLD      outflow spike / burst threshold in spreads (default 6)
  BRIDGEWATCH_MIN_SPREAD_USD   smallest spread allowed for the outflow baseline (default 100000)
  BRIDGEWATCH_WEBHOOK_URL      where alerts are POSTed (secret; unset = off)
  BRIDGEWATCH_WEBHOOK_FORMAT   slack (default) | json
  BRIDGEWATCH_API_TOKEN        needed to acknowledge alerts; in live mode acknowledging is off without it
  BRIDGEWATCH_RESULTS_DIR      where evaluate/replay save JSON for the dashboard (default prototype/results)
  BRIDGEWATCH_SPEED, BRIDGEWATCH_SEED   demo clock speed and random seed
"""

from __future__ import annotations
import json
import os
from dataclasses import dataclass, field
from pathlib import Path

from .detector import DetectorConfig

PACKAGE_DIR = Path(__file__).resolve().parent
PROTOTYPE_DIR = PACKAGE_DIR.parent
REGISTRY_PATH = PACKAGE_DIR / "bridges.json"
DATA_DIR = PACKAGE_DIR / "data"

# Per-bridge overrides allowed in bridges.json ("overrides": {...}).
OVERRIDABLE = {"z_threshold", "min_escrow_share", "min_spread_usd", "burst_min_count", "drain_share",
               "large_withdrawal_share", "large_withdrawal_min_usd"}


@dataclass
class Settings:
    mode: str = "live"
    db_path: str = "bridgewatch.db"
    chain: str = "ethereum"
    rpc_urls: tuple[str, ...] = ()          # empty = the built-in public endpoints
    rpc_pause: float = 0.3
    poll_seconds: float = 15
    confirmations: int | None = None        # None = use the chain's value from bridges.json
    history_days: float = 7
    z_threshold: float = 6.0
    min_spread_usd: float = 100_000
    webhook_url: str | None = None
    webhook_format: str = "slack"
    api_token: str | None = None
    results_dir: Path = PROTOTYPE_DIR / "results"
    registry_path: Path = REGISTRY_PATH
    speed: float = 60
    seed: int = 7


def settings_from_env(env=None) -> Settings:
    env = os.environ if env is None else env
    get = lambda k, d=None: env.get(f"BRIDGEWATCH_{k}") or d   # noqa: E731 (empty string = unset)
    conf = get("CONFIRMATIONS")
    return Settings(
        mode=get("MODE", "live").lower(),
        db_path=get("DB", "bridgewatch.db"),
        chain=get("CHAIN", "ethereum"),
        rpc_urls=tuple(u.strip() for u in get("RPC_URLS", "").split(",") if u.strip()),
        rpc_pause=float(get("RPC_PAUSE", "0.3")),
        poll_seconds=float(get("POLL_SECONDS", "15")),
        confirmations=int(conf) if conf else None,
        history_days=float(get("HISTORY_DAYS", "7")),
        z_threshold=float(get("Z_THRESHOLD", "6")),
        min_spread_usd=float(get("MIN_SPREAD_USD", "100000")),
        webhook_url=get("WEBHOOK_URL"),
        webhook_format=get("WEBHOOK_FORMAT", "slack"),
        api_token=get("API_TOKEN"),
        results_dir=Path(get("RESULTS_DIR", str(PROTOTYPE_DIR / "results"))),
        speed=float(get("SPEED", "60")),
        seed=int(get("SEED", "7")),
    )


def detector_config(settings: Settings | None = None) -> DetectorConfig:
    """The single place a DetectorConfig is built from settings (history days, thresholds)."""
    s = settings or settings_from_env()
    return DetectorConfig(history_days=s.history_days, z_threshold=s.z_threshold, min_spread_usd=s.min_spread_usd)


# --- bridges.json -----------------------------------------------------------------
@dataclass(frozen=True)
class ChainCfg:
    id: str
    name: str
    confirmations: int = 6
    block_time_s: float = 12.0
    explorer_tx: str = ""


@dataclass(frozen=True)
class TokenCfg:
    symbol: str
    address: str          # lower-case
    decimals: int
    price: dict           # {"fixed": 1.0} or {"chainlink": feed, "expect": "BTC / USD"}
    chain: str = "ethereum"


@dataclass(frozen=True)
class BridgeCfg:
    id: str
    name: str
    chain: str                    # chain the monitored vault lives on
    chains: tuple[str, ...]       # the chains it connects (for display)
    vault: str
    contract: str = ""
    source: str = ""
    overrides: dict = field(default_factory=dict)


@dataclass
class Registry:
    chains: dict[str, ChainCfg]
    tokens: list[TokenCfg]
    bridges: list[BridgeCfg]

    def tokens_on(self, chain: str) -> list[TokenCfg]:
        return [t for t in self.tokens if t.chain == chain]

    def bridges_on(self, chain: str) -> list[BridgeCfg]:
        return [b for b in self.bridges if b.chain == chain]

    def overrides(self) -> dict[str, dict]:
        return {b.id: b.overrides for b in self.bridges if b.overrides}


def load_registry(path: str | Path = REGISTRY_PATH) -> Registry:
    """Read bridges.json. Also accepts the older single-chain layout (top-level
    "chain" and "explorer_tx", no "chains" block)."""
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    default_chain = raw.get("chain", "ethereum")
    chains = {cid: ChainCfg(cid, c.get("name", cid), int(c.get("confirmations", 6)),
                            float(c.get("block_time_s", 12)), c.get("explorer_tx", ""))
              for cid, c in raw.get("chains", {}).items()}
    if not chains:
        chains = {default_chain: ChainCfg(default_chain, default_chain.title(), 6, 12.0, raw.get("explorer_tx", ""))}
    tokens = [TokenCfg(t["symbol"], t["address"].lower(), int(t["decimals"]), t["price"], t.get("chain", default_chain))
              for t in raw["tokens"]]
    bridges = []
    for b in raw["bridges"]:
        bad = set(b.get("overrides", {})) - OVERRIDABLE
        if bad:
            raise ValueError(f"bridges.json: bridge '{b['id']}' has unknown overrides {sorted(bad)}; "
                             f"allowed: {sorted(OVERRIDABLE)}")
        bridges.append(BridgeCfg(b["id"], b["name"], b.get("chain", default_chain), tuple(b.get("chains", ())),
                                 b["vault"], b.get("contract", ""), b.get("source", ""), dict(b.get("overrides", {}))))
    for b in bridges:
        if b.chain not in chains:
            raise ValueError(f"bridges.json: bridge '{b.id}' is on chain '{b.chain}', which has no entry in \"chains\".")
    return Registry(chains, tokens, bridges)

