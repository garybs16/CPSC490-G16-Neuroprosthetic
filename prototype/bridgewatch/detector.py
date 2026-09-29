"""
The detector: learns what normal looks like for each bridge, then flags
deviations the moment a release arrives.

Baseline of normal
  Every 10 minutes the bridge's outflow (USD) and release count are recorded
  under that hour of the day. The baseline for "now" is the median of the same
  hour over the past 7 days, and its spread is the median absolute deviation
  (MAD). Median/MAD rather than mean/standard deviation, so one whale or one
  past incident doesn't drag the baseline around. Comparing like hours keeps
  the daily cycle from reading as an anomaly.

Rules, checked on every release
  outflow_spike      last-10-minute outflow is z_threshold spreads above normal
                     AND moves at least min_escrow_share of the escrow
  withdrawal_burst   last-10-minute release count is z_threshold spreads above
                     normal AND at least burst_min_count releases
  escrow_drain       net outflow over the last hour exceeds drain_share of the
                     escrow (no baseline needed: losing 5% in an hour is never normal)
  unbacked_release   a release with no matching deposit (only when the data can
                     tell, i.e. use_message_matching and backed is False)

Alarm fatigue
  One alert per bridge and rule per cooldown: while an alert is live, new
  triggers update it (peak value, last seen) instead of raising another.
  No alerts during the warm-up, before the baseline has enough history.
"""

from __future__ import annotations
import statistics
from collections import deque
from dataclasses import dataclass, field

from .models import Alert, Bridge, FlowEvent

BUCKET = 600.0   # 10 minutes


@dataclass
class DetectorConfig:
    z_threshold: float = 6.0
    min_escrow_share: float = 0.005
    burst_min_count: int = 12
    drain_share: float = 0.05
    warmup: float = 3 * 86_400
    cooldown: float = 3_600
    history_days: int = 7
    use_message_matching: bool = False


def _fmt_usd(x: float) -> str:
    for div, unit in ((1e9, "B"), (1e6, "M"), (1e3, "K")):
        if abs(x) >= div:
            return f"${x / div:.1f}{unit}"
    return f"${x:,.0f}"


@dataclass
class Bucket:
    start: float
    out_usd: float = 0.0
    in_usd: float = 0.0
    out_count: int = 0
    expected_usd: float | None = None   # baseline median for this bucket's hour
    upper_usd: float | None = None      # outflow that would trip outflow_spike


class BridgeMonitor:
    """Streaming state for one bridge. Feed it events in time order."""

    def __init__(self, bridge: Bridge, cfg: DetectorConfig, first_ts: float | None = None):
        self.bridge, self.cfg = bridge, cfg
        self.escrow = bridge.escrow_usd
        self.first_ts = first_ts
        per_hour = cfg.history_days * int(3_600 // BUCKET)
        self.hist_usd = {h: deque(maxlen=per_hour) for h in range(24)}
        self.hist_cnt = {h: deque(maxlen=per_hour) for h in range(24)}
        self.recent_out: deque[tuple[float, float]] = deque()   # releases, last 10 min
        self.hour_flows: deque[tuple[float, float]] = deque()   # signed flows, last hour
        self.win_usd = 0.0
        self.net_hour = 0.0
        self.bucket: Bucket | None = None
        self.buckets: deque[Bucket] = deque(maxlen=cfg.history_days * 24 * int(3_600 // BUCKET))
        self.live: dict[str, Alert] = {}

    # --- baseline -----------------------------------------------------------
    @staticmethod
    def _hour(ts: float) -> int:
        return int((ts % 86_400) // 3_600)

    @staticmethod
    def _robust(values) -> tuple[float, float]:
        med = statistics.median(values)
        mad = statistics.median(abs(v - med) for v in values)
        return med, mad

    def baseline(self, ts: float) -> tuple[float, float, float, float] | None:
        """(median usd, spread usd, median count, spread count) for this hour, or None while learning."""
        h = self._hour(ts)
        if len(self.hist_usd[h]) < 6 or self.first_ts is None or ts - self.first_ts < self.cfg.warmup:
            return None
        med_u, mad_u = self._robust(self.hist_usd[h])
        med_c, mad_c = self._robust(self.hist_cnt[h])
        # Spread floors: a quiet hour with MAD ~0 must not turn every release into a 50-sigma event
        return med_u, max(1.4826 * mad_u, 0.5 * med_u, 1.0), med_c, max(1.4826 * mad_c, 0.5 * med_c, 1.0)

    def learning(self, ts: float) -> bool:
        return self.baseline(ts) is None

    def _roll(self, ts: float) -> None:
        start = ts - ts % BUCKET
        if self.bucket is None:
            self.bucket = Bucket(start)
        while self.bucket.start < start:
            b = self.bucket
            self.hist_usd[self._hour(b.start)].append(b.out_usd)
            self.hist_cnt[self._hour(b.start)].append(b.out_count)
            self.buckets.append(b)
            self.bucket = Bucket(b.start + BUCKET)
        if self.bucket.expected_usd is None:
            base = self.baseline(self.bucket.start)
            if base:
                self.bucket.expected_usd = base[0]
                self.bucket.upper_usd = base[0] + self.cfg.z_threshold * base[1]

    def advance(self, ts: float) -> None:
        """Move the clock forward with no events (closes empty buckets)."""
        if self.first_ts is None:
            self.first_ts = ts
        self._roll(ts)
        self._expire(ts)

    def _expire(self, ts: float) -> None:
        while self.recent_out and self.recent_out[0][0] <= ts - BUCKET:
            self.win_usd -= self.recent_out.popleft()[1]
        while self.hour_flows and self.hour_flows[0][0] <= ts - 3_600:
            self.net_hour -= self.hour_flows.popleft()[1]

    # --- events -------------------------------------------------------------
    def observe(self, e: FlowEvent, next_id) -> list[Alert]:
        """Update state with one event; return alerts that were newly raised."""
        self.advance(e.ts)
        b = self.bucket
        if e.direction == "in":
            self.escrow += e.amount_usd
            b.in_usd += e.amount_usd
            self.hour_flows.append((e.ts, -e.amount_usd))
            self.net_hour -= e.amount_usd
            return []

        self.escrow -= e.amount_usd
        b.out_usd += e.amount_usd
        b.out_count += 1
        self.recent_out.append((e.ts, e.amount_usd))
        self.win_usd += e.amount_usd
        self.hour_flows.append((e.ts, e.amount_usd))
        self.net_hour += e.amount_usd

        cfg, raised = self.cfg, []
        escrow_ref = max(self.escrow + self.net_hour, 1.0)   # escrow as it stood an hour ago
        name = self.bridge.name

        def fire(rule, severity, observed, expected, message):
            a = self.live.get(rule)
            if a and e.ts - a.last_seen < cfg.cooldown:
                a.last_seen = e.ts
                if observed > a.observed:   # keep the first message; record the worst point separately
                    a.observed, a.worst = observed, message
                if severity == "critical":
                    a.severity = "critical"
                return
            a = Alert(next_id(), self.bridge.id, rule, severity, e.ts, e.ts, observed, expected, message)
            self.live[rule] = a
            raised.append(a)

        if cfg.use_message_matching and e.backed is False:
            fire("unbacked_release", "critical", e.amount_usd, 0.0,
                 f"{name} released {_fmt_usd(e.amount_usd)} with no matching deposit on the source chain.")

        if self.net_hour >= cfg.drain_share * escrow_ref:
            share = self.net_hour / escrow_ref
            fire("escrow_drain", "critical", share, cfg.drain_share,
                 f"{name} lost {_fmt_usd(self.net_hour)} net in the last hour: {share:.0%} of its "
                 f"{_fmt_usd(escrow_ref)} escrow.")

        base = self.baseline(e.ts)
        if base:
            med_u, spread_u, med_c, spread_c = base
            count = len(self.recent_out)
            z_u = (self.win_usd - med_u) / spread_u
            z_c = (count - med_c) / spread_c
            if z_u >= cfg.z_threshold and self.win_usd >= cfg.min_escrow_share * escrow_ref:
                big = self.win_usd >= 0.05 * escrow_ref
                normal = (f"about {_fmt_usd(med_u)} is normal at this hour" if med_u >= 1
                          else "normally nothing leaves at this hour")
                fire("outflow_spike", "critical" if big else "warning", self.win_usd, med_u,
                     f"{_fmt_usd(self.win_usd)} left {name} in the last 10 minutes; {normal}.")
            if z_c >= cfg.z_threshold and count >= cfg.burst_min_count:
                fire("withdrawal_burst", "warning", count, med_c,
                     f"{count} releases from {name} in the last 10 minutes; about {med_c:.0f} is normal at this hour.")
        return raised


@dataclass
class Detector:
    """Runs one BridgeMonitor per bridge and keeps the alert log."""
    bridges: tuple[Bridge, ...]
    cfg: DetectorConfig = field(default_factory=DetectorConfig)

    def __post_init__(self):
        self.monitors = {b.id: BridgeMonitor(b, self.cfg) for b in self.bridges}
        self.alerts: list[Alert] = []
        self._next = 0

    def _id(self) -> int:
        self._next += 1
        return self._next

    def observe(self, e: FlowEvent) -> list[Alert]:
        m = self.monitors.get(e.bridge)
        if m is None:
            return []
        raised = m.observe(e, self._id)
        self.alerts.extend(raised)
        return raised

    def advance(self, ts: float) -> None:
        for m in self.monitors.values():
            m.advance(ts)
