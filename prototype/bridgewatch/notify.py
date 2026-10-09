"""
Alert delivery to a webhook, on its own thread so a slow or failing receiver
never holds up ingest.

  BRIDGEWATCH_WEBHOOK_URL     where to POST (unset = notifications off)
  BRIDGEWATCH_WEBHOOK_FORMAT  "slack" (default): {"text": "..."} for a Slack-style incoming webhook
                              "json": {"incident", "bridge_name", "alerts": [...]} for your own receiver

How it works
  - The database is the queue: an alert is pending until the receiver answers
    2xx (at-least-once delivery, survives restarts).
  - One message per incident: alerts on one bridge within the cooldown of each
    other are sent together. A later alert that joins an incident already sent
    at the same severity is folded in silently; one that raises it from warning
    to critical sends a "now critical" update.
  - Failures back off exponentially (5 s, 10 s, 20 s ... capped at 10 min); a
    429 with Retry-After waits as long as the receiver asks. After max_attempts
    the incident is marked 'failed' and counted in /api/health.
  - Alerts found while catching up after downtime are sent, labelled LATE.
    Only alerts from the very first backfill (history, before BridgeWatch was
    watching) are never sent; the live monitor stores those as 'historical'.

The webhook URL is a secret; keep it in the environment, never in the repository.
"""

from __future__ import annotations
import datetime as dt
import logging
import threading
import time

import httpx

log = logging.getLogger("bridgewatch.notify")
LATE_AFTER_S = 300   # raised more than 5 minutes after the transfer was confirmed = LATE


def is_late(alert: dict) -> bool:
    d, c = alert.get("detected_at"), alert.get("confirmed_at")
    return d is not None and c is not None and d - c > LATE_AFTER_S


def _when(ts: float) -> str:
    return dt.datetime.fromtimestamp(ts, dt.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def render(alerts: list[dict], bridge_name: str, upgraded: bool = False) -> str:
    """One incident (one or more alerts on one bridge) as Slack-style text."""
    critical = any(a["severity"] == "critical" for a in alerts)
    head = ("LATE " if any(is_late(a) for a in alerts) else "") + ("CRITICAL" if critical else "Warning")
    rules = ", ".join(dict.fromkeys(a["rule"].replace("_", " ") for a in alerts))
    lines = [f"[BridgeWatch] {head}{' (now critical)' if upgraded else ''}: {bridge_name}, {rules} "
             f"at {_when(min(a['started'] for a in alerts))}"]
    for a in alerts:
        lines.append(a["message"])
        if a.get("worst"):
            lines.append(f"Worst so far: {a['worst']}")
    late = [a for a in alerts if is_late(a)]
    if late:
        mins = max(a["detected_at"] - a["confirmed_at"] for a in late) / 60
        lines.append(f"LATE: detected {mins:.0f} min after the transfers were confirmed (BridgeWatch was catching up).")
    return "\n".join(lines)


class Notifier:
    def __init__(self, url: str | None, fmt: str = "slack", client: httpx.Client | None = None,
                 max_attempts: int = 8, base_delay: float = 5.0, max_delay: float = 600.0, clock=time.time):
        self.url, self.fmt = url, fmt
        self.client = client or httpx.Client(timeout=10)
        self.max_attempts, self.base_delay, self.max_delay = max_attempts, base_delay, max_delay
        self.clock = clock
        self.store = None
        self.names: dict[str, str] = {}
        self.sent = 0          # messages delivered
        self.failed = 0        # delivery attempts that failed
        self.gave_up = 0       # incidents abandoned after max_attempts
        self._lock = threading.Lock()
        self._wake = threading.Event()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    @property
    def enabled(self) -> bool:
        return bool(self.url)

    def attach(self, store, bridge_names: dict[str, str]) -> None:
        self.store, self.names = store, bridge_names

    # --- worker thread --------------------------------------------------------
    def start(self) -> None:
        """Deliver in the background from now on (the live service calls this)."""
        if self._thread is None and self.enabled:
            self._thread = threading.Thread(target=self._run, daemon=True, name="bridgewatch-notify")
            self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._wake.set()

    def wake(self) -> None:
        """New alerts may be pending. With no worker thread (tests, CLIs) deliver right here."""
        if self._thread is not None:
            self._wake.set()
        else:
            self.deliver_pending()

    def _run(self) -> None:
        while not self._stop.is_set():
            self._wake.wait(timeout=1.0)
            self._wake.clear()
            try:
                self.deliver_pending()
            except Exception:   # never let the worker die
                log.exception("Notification pass failed")

    # --- delivery ---------------------------------------------------------------
    def post(self, body: dict) -> tuple[bool, float | None]:
        """POST once. Returns (delivered, seconds the receiver asked us to wait)."""
        try:
            resp = self.client.post(self.url, json=body)
        except httpx.HTTPError as e:
            log.warning("Webhook delivery failed: %s", type(e).__name__)
            return False, None
        if 200 <= resp.status_code < 300:
            return True, None
        retry_after = None
        if resp.status_code == 429:
            try:
                retry_after = float(resp.headers.get("retry-after", ""))
            except ValueError:
                retry_after = None
        log.warning("Webhook answered HTTP %d", resp.status_code)
        return False, retry_after

    def deliver_pending(self) -> int:
        """One pass over pending alerts, one message per incident. Returns messages sent."""
        if not self.enabled or self.store is None:
            return 0
        with self._lock:
            now, sent = self.clock(), 0
            groups: dict[str, list[dict]] = {}
            for a in self.store.pending_notifications():
                groups.setdefault(a["incident"] or f"alert-{a['id']}", []).append(a)
            for incident, pending in groups.items():
                if any(a["notify_next_at"] > now for a in pending):
                    continue                                   # backing off
                members = self.store.incident_alerts(incident) if pending[0]["incident"] else pending
                severity = "critical" if any(a["severity"] == "critical" for a in members) else "warning"
                told = {a["notified_severity"] for a in members} & {"warning", "critical"}
                ids = [a["id"] for a in pending]
                if "critical" in told or (told == {"warning"} and severity == "warning"):
                    self.store.mark_notified(ids, severity)    # already told at this level: fold in
                    continue
                bridge = pending[0]["bridge"]
                name = self.names.get(bridge, bridge)
                upgraded = told == {"warning"}
                body = ({"text": render(members, name, upgraded)} if self.fmt == "slack"
                        else {"incident": incident, "bridge_name": name, "upgraded": upgraded, "alerts": members})
                ok, retry_after = self.post(body)
                if ok:
                    self.sent += 1
                    sent += 1
                    self.store.mark_notified(ids, severity)
                    continue
                self.failed += 1
                attempts = max(a["notify_attempts"] for a in pending) + 1
                if attempts >= self.max_attempts:
                    self.gave_up += 1
                    self.store.mark_notified(ids, "failed")
                    log.error("Gave up notifying incident %s after %d attempts", incident, attempts)
                    continue
                delay = retry_after if retry_after is not None else min(self.base_delay * 2 ** (attempts - 1), self.max_delay)
                self.store.record_attempt(ids, attempts, now + delay)
            return sent
