"""Data shapes shared by every part of BridgeWatch. A real data source (SonarX)
only has to produce FlowEvents; the detector and dashboard never change."""

from __future__ import annotations
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Bridge:
    id: str
    name: str
    chains: tuple[str, ...]
    escrow_usd: float          # value locked in the bridge at the start of the data


@dataclass(frozen=True)
class FlowEvent:
    ts: float                  # unix seconds
    bridge: str
    direction: str             # "out" = funds released from the bridge, "in" = deposit into it
    amount_usd: float
    tx: str
    # Did this release match a deposit on the source chain? None when the data
    # source can't tell (plain transfer data can't; bridge message data can).
    backed: bool | None = None


@dataclass
class Alert:
    id: int
    bridge: str
    rule: str                  # "outflow_spike" | "withdrawal_burst" | "escrow_drain" | "unbacked_release"
    severity: str              # "warning" | "critical"
    started: float
    last_seen: float
    observed: float            # the measured value that tripped the rule (USD, count, or share)
    expected: float            # what the baseline says is normal for that moment
    message: str               # what tripped the rule, as of when it fired
    worst: str = ""            # the same measure at its worst so far, if it got worse
    acknowledged: bool = False


@dataclass
class Incident:
    """Ground truth for a simulated exploit, used to score the detector."""
    bridge: str
    kind: str
    start: float
    end: float
    stolen_usd: float = 0.0
    events: list[FlowEvent] = field(default_factory=list, repr=False)
