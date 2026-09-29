"""
Alert delivery to a webhook.

  BRIDGEWATCH_WEBHOOK_URL     where to POST (unset = notifications off)
  BRIDGEWATCH_WEBHOOK_FORMAT  "slack" (default): {"text": "..."} for a Slack-style incoming webhook
                              "json": the full alert record, for your own receiver

Delivery is at-least-once: an alert is marked sent only after the receiver
answers 2xx, and unsent alerts are retried on every poll. The webhook URL is a
secret; keep it in the environment, never in the repository.
"""

from __future__ import annotations
import datetime as dt
import logging

import httpx

log = logging.getLogger("bridgewatch.notify")


def render(alert: dict, bridge_name: str) -> str:
    when = dt.datetime.fromtimestamp(alert["started"], dt.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    head = "CRITICAL" if alert["severity"] == "critical" else "Warning"
    upgraded = " (now critical)" if alert.get("notified_severity") == "warning" else ""
    lines = [f"[BridgeWatch] {head}{upgraded}: {bridge_name}, {alert['rule'].replace('_', ' ')} at {when}",
             alert["message"]]
    if alert.get("worst"):
        lines.append(f"Worst so far: {alert['worst']}")
    return "\n".join(lines)


class Notifier:
    def __init__(self, url: str | None, fmt: str = "slack", client: httpx.Client | None = None):
        self.url, self.fmt = url, fmt
        self.client = client or httpx.Client(timeout=10)
        self.sent = 0
        self.failed = 0

    @property
    def enabled(self) -> bool:
        return bool(self.url)

    def send(self, alert: dict, bridge_name: str) -> bool:
        if not self.enabled:
            return False
        body = {"text": render(alert, bridge_name)} if self.fmt == "slack" else {"alert": alert, "bridge_name": bridge_name}
        try:
            resp = self.client.post(self.url, json=body)
            ok = 200 <= resp.status_code < 300
        except httpx.HTTPError as e:
            log.warning("Webhook delivery failed: %s", type(e).__name__)
            ok = False
        if ok:
            self.sent += 1
        else:
            self.failed += 1
        return ok
