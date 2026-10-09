"""
Synthetic bridge traffic, with exploits that can be injected on demand.

Nothing here is real data. The bridges are fictional and every number is a
generation parameter chosen to look plausible, not measured from a real
bridge. It exists so the detector and dashboard can be built and scored
before SonarX data access arrives; swap in a real source by producing the
same FlowEvents.

Normal traffic: deposits and releases arrive at random (Poisson), busier in
the afternoon (UTC) and quieter at weekends, with log-normal sizes and an
occasional legitimate "whale" transfer 40-120x the usual size. Whales are
there on purpose: they are what makes false alarms hard to avoid.

Exploit shapes, loosely modelled on the public accounts of past bridge hacks:
  mass_drain      hundreds of unbacked releases over ~2 hours until most of the
                  escrow is gone (a copy-paste exploit anyone can join)
  key_compromise  two huge releases minutes apart (stolen signer keys)
  slow_bleed      extra unbacked releases of ordinary size for 12 hours
                  (the hard case: each one looks normal)
"""

from __future__ import annotations
import math
import random
from typing import Iterator

from .models import Bridge, FlowEvent, Incident

BRIDGES = (
    Bridge("alpha", "Alpha Bridge", ("Chain A", "Chain B"), 400e6),
    Bridge("beta", "Beta Bridge", ("Chain A", "Chain C"), 150e6),
    Bridge("gamma", "Gamma Bridge", ("Chain B", "Chain D"), 60e6),
    Bridge("delta", "Delta Bridge", ("Chain A", "Chain E"), 900e6),
)
BRIDGE_BY_ID = {b.id: b for b in BRIDGES}

# Per-bridge traffic parameters: transfers per hour (each direction), median size (USD)
TRAFFIC = {"alpha": (40, 8_000), "beta": (25, 5_000), "gamma": (12, 3_000), "delta": (70, 15_000)}
SIZE_SIGMA = 1.1          # log-normal spread of transfer sizes
WHALES_PER_DAY = 1.5      # legitimate very large releases per bridge per day
INCIDENT_KINDS = ("mass_drain", "key_compromise", "slow_bleed")
SLICE = 60.0              # generation step (seconds)


def _poisson(rng: random.Random, lam: float) -> int:
    if lam > 30:  # normal approximation keeps big slices fast
        return max(0, round(rng.gauss(lam, math.sqrt(lam))))
    limit, k, p = math.exp(-lam), 0, 1.0
    while True:
        p *= rng.random()
        if p <= limit:
            return k
        k += 1


def activity(ts: float) -> float:
    """Relative traffic level: a daily cycle peaking ~15:00 UTC, weekends at 70%."""
    hour = (ts % 86_400) / 3_600
    daily = 1 + 0.5 * math.sin(2 * math.pi * (hour - 9) / 24)
    weekday = int(ts // 86_400 + 3) % 7   # 1970-01-01 was a Thursday; 5, 6 = Sat, Sun
    return daily * (0.7 if weekday >= 5 else 1.0)


class SyntheticSource:
    """Generates traffic for all bridges, slice by slice, deterministically from a seed."""

    def __init__(self, seed: int = 7, bridges: tuple[Bridge, ...] = BRIDGES):
        self.rng = random.Random(seed)
        self.bridges = bridges
        self.pending: list[FlowEvent] = []   # scheduled exploit events not yet emitted
        self.incidents: list[Incident] = []
        self._n = 0

    def _tx(self) -> str:
        self._n += 1
        return f"syn-{self._n:08d}"

    def events_between(self, t0: float, t1: float) -> Iterator[FlowEvent]:
        """All events with t0 <= ts < t1, in time order."""
        out: list[FlowEvent] = []
        t = t0
        while t < t1:
            end = min(t + SLICE, t1)
            dt = end - t
            level = activity(t)
            for b in self.bridges:
                per_hour, median = TRAFFIC.get(b.id, (20, 5_000))
                for direction in ("in", "out"):
                    for _ in range(_poisson(self.rng, per_hour * level * dt / 3_600)):
                        amt = self.rng.lognormvariate(math.log(median), SIZE_SIGMA)
                        out.append(FlowEvent(self.rng.uniform(t, end), b.id, direction, amt, self._tx(), True))
                if self.rng.random() < WHALES_PER_DAY * dt / 86_400:
                    amt = median * self.rng.uniform(40, 120)
                    out.append(FlowEvent(self.rng.uniform(t, end), b.id, "out", amt, self._tx(), True))
            t = end
        due = [e for e in self.pending if t0 <= e.ts < t1]
        if due:
            self.pending = [e for e in self.pending if e.ts >= t1]
            out.extend(due)
        out.sort(key=lambda e: e.ts)
        return iter(out)

    def inject(self, bridge_id: str, kind: str, start: float, escrow_usd: float | None = None) -> Incident:
        """Schedule an exploit on a bridge starting at `start`. Returns its ground truth."""
        if kind not in INCIDENT_KINDS:
            raise ValueError(f"Unknown incident kind '{kind}'. Use one of: {', '.join(INCIDENT_KINDS)}.")
        bridge = next(b for b in self.bridges if b.id == bridge_id)
        escrow = escrow_usd if escrow_usd is not None else bridge.escrow_usd
        rng, events = self.rng, []
        if kind == "mass_drain":
            n, dur = 300, 7_200
            target = escrow * rng.uniform(0.75, 0.9)
            weights = [rng.uniform(0.5, 1.5) for _ in range(n)]
            scale = target / sum(weights)
            # Starts slowly (the first few attackers), then accelerates as others copy it
            times = sorted(start + dur * (rng.random() ** 0.6) for _ in range(n))
            events = [FlowEvent(ts, bridge.id, "out", w * scale, self._tx(), False) for ts, w in zip(times, weights)]
        elif kind == "key_compromise":
            events = [FlowEvent(start, bridge.id, "out", escrow * 0.35, self._tx(), False),
                      FlowEvent(start + 360, bridge.id, "out", escrow * 0.45, self._tx(), False)]
        elif kind == "slow_bleed":
            per_hour, median = TRAFFIC.get(bridge.id, (20, 5_000))
            dur, t = 12 * 3_600, start
            while True:
                t += rng.expovariate(per_hour / 3_600)   # doubles the normal release rate
                if t >= start + dur:
                    break
                events.append(FlowEvent(t, bridge.id, "out", rng.lognormvariate(math.log(median), SIZE_SIGMA),
                                        self._tx(), False))
        inc = Incident(bridge.id, kind, start, max(e.ts for e in events), sum(e.amount_usd for e in events), events)
        self.pending.extend(events)
        self.incidents.append(inc)
        return inc
