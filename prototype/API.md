# BridgeWatch API (v0.3)

Served by `bridgewatch/app.py` on port 8001 (`python run_bridgewatch.py`).
Interactive docs at `/docs`. All responses are JSON unless noted. Times are
unix seconds (UTC); money is USD.

The API does no heavy work per request. In live mode `/api/state` comes from a
snapshot rebuilt after each poll (about every 15 s), so **polling more often
than every 10 s gains nothing**. Evaluation and replay results are files
written by the command-line tools; the API only serves them.

## Changes since v0.2 (for the dashboard)

| Change | What to do |
|---|---|
| `/api/state`: `sim_time` removed (it duplicated `clock`) | use `clock` |
| `/api/replay` now returns every replayed case: `{"generated_at", "config", "simulated_pipeline", "cases": [case, ...]}` | iterate `cases`, or fetch one case from `/api/replay/{key}` (same shape as the old `/api/replay`, plus new fields) |
| `/api/replay` and `/api/evaluation` answer **404** with `{"detail": "...run python -m ..."}` until the CLI has saved a result (no more 202 "running") | show the detail text; stop retrying |
| New `/api/evaluation/real` | false alarms per bridge per week on real data |
| `/api/alerts` is ordered by `id` (newest first) and pages with `before_id` | next page: `?before_id=<last id>` |
| Alerts have new fields `confirmed_at`, `detected_at`, `incident`; live alerts also `notify_attempts`, `notify_next_at` | latency = `detected_at - confirmed_at` |
| New rule `large_withdrawal` | add a label ("Large withdrawal") |
| Live acknowledge needs `BRIDGEWATCH_API_TOKEN`: **403** when the server has no token, **401** when the token is wrong | ask for the token; explain 403 |
| `/api/health` (live) adds `chain`, `prices` (per token), `prices_stale`, `unpriced_transfers`, `last_detection_latency_s`, `notifications.gave_up`, `notifications.pending` | show a stale-price warning |

## Endpoints

### `GET /api/state`
Every bridge's status.

```json
{
  "mode": "live",                         // "live" | "demo"
  "data": "ethereum-mainnet",             // "synthetic" in demo
  "clock": 1791410507,                    // live: block time of the last processed block; demo: simulated clock
  "bridges": [{
    "id": "optimism", "name": "OP Mainnet bridge", "chains": ["Ethereum", "OP Mainnet"],
    "escrow_usd": 392938326.89,
    "outflow_last_hour_usd": 0.0,
    "normal_hour_usd": 0.0,               // null while the baseline is learning
    "status": "ok",                       // "ok" | "alert" | "learning"
    "worst_severity": null,               // null | "warning" | "critical" (unacknowledged alerts within the cooldown)
    "vault": "0x99C9...", "contract": "L1StandardBridgeProxy", "source": "https://...", "chain": "ethereum"   // live only
  }],
  // live only:
  "snapshot_at": 1791410648.7, "explorer_tx": "https://etherscan.io/tx/", "chain": "ethereum",
  "head": 26143371, "cursor": 26143365, "lag_blocks": 6, "phase": "live",   // phase: starting | backfilling | live | error
  "health": "ok", "transfers_stored": 1009,
  // demo only:
  "speed": 60, "events_processed": 123456
}
```
Before the first snapshot (live start-up) `bridges` is `[]` and `clock` is `null`.

### `GET /api/series/{bridge_id}?hours=24`
10-minute buckets for the chart; `hours` is capped at the baseline window (7 days). 404 for an unknown bridge.

```json
{"bridge": "alpha", "bucket_seconds": 600.0,
 "buckets": [{"t": 1791406800.0, "out_usd": 111578.64, "in_usd": 39674.86, "releases": 4,
              "normal_usd": 65799.07, "alert_line_usd": 665799.07, "partial": false}],   // normal/alert line null while learning; the last bucket is partial
 "alerts": [Alert, ...]}
```

### `GET /api/alerts?limit=50&before_id=&bridge=`
Newest first by `id`; `limit` 1-500. Next page: `before_id` = the last `id` received. An **Alert**:

```json
{"id": 12, "bridge": "optimism",
 "rule": "escrow_drain",          // outflow_spike | withdrawal_burst | escrow_drain | large_withdrawal | unbacked_release
 "severity": "critical",          // warning | critical
 "started": 1791410000,           // block time of the transfer that tripped the rule
 "last_seen": 1791410300,         // repeats within the cooldown (1 h) update the same alert
 "observed": 0.13, "expected": 0.05,   // USD, a count, or an escrow share, depending on the rule
 "message": "OP Mainnet bridge lost $40.0M net in the last hour: 13% of its $300.0M escrow.",
 "worst": "",                     // the same measure at its worst so far, if it got worse
 "acknowledged": false,
 "confirmed_at": 1791410072,      // block time + confirmations x block time
 "detected_at": 1791410085.3,     // when BridgeWatch raised it (wall clock live, simulated clock in demo)
 "incident": "optimism-1791410000",   // alerts on one bridge within the cooldown share it; one notification per incident
 // live only:
 "acknowledged_at": null,
 "notified_severity": "critical", // "" not sent yet | warning | critical | historical (first backfill, never sent) | failed
 "notify_attempts": 0, "notify_next_at": 0}
```

### `POST /api/alerts/{id}/ack`
Header `Authorization: Bearer <BRIDGEWATCH_API_TOKEN>`. Returns the updated Alert.
Live: 403 if the server has no token configured, 401 for a missing/wrong token. Demo: the token is
required only if one is configured. 404 for an unknown id.

### `POST /api/simulate` (demo only)
Body `{"bridge": "alpha", "kind": "mass_drain"}` (`kind`: mass_drain | key_compromise | slow_bleed).
Returns `{"bridge", "kind", "start", "end", "stolen_usd", "releases"}`. 409 in live mode or if an exploit is
already running on that bridge; 404 unknown bridge; 400 unknown kind.

### `GET /api/replay` and `GET /api/replay/{key}`
Saved by `python -m bridgewatch.replay` (file `results/replay.json`). 404 if missing.

```json
{"generated_at": 1791410000.0, "config": {DetectorConfig},
 "simulated_pipeline": {"confirmations": 6, "block_time_s": 12.0, "poll_seconds": 15.0},
 "cases": [{
   "key": "orbit-2023", "case": "Orbit Chain bridge, Ethereum vault, 31 Dec 2023", "dataset": "orbit-2023.json",
   "vault": "0x1bf6...", "escrow_usd_at_start": 70321852.0, "baseline_days": 14.0, "ordinary_transfers": 250,
   "stolen_usd_tracked": 59826263.0,
   "thefts": [{"ts": 1704056879, "token": "DAI", "amount": 10000000.0, "usd": 10000000.0, "to": "0x...", "tx": "0x..."}],
   "alerts": [Alert, ...],                     // alerts from 1 h before the first theft to 1 h after the last
   "first_theft_ts": 1704056879,
   "first_alert_ts": 1704056879,               // block time of the transfer that tripped the first alert
   "first_alert_detected_at": 1704056955,      // when it would have been raised
   "first_alert_rule": "escrow_drain",
   "seconds_from_first_theft_to_alert": 0,     // in block time (0 = the first theft itself tripped it)
   "detection_latency_s": 4.0,                 // detected_at - (first theft + 6 confirmations); target <= 60
   "latency_target_s": 60,
   "stolen_before_alert_usd": 10000000.0, "stolen_after_alert_usd": 49826263.0,
   "minutes_of_warning_for_later_thefts": [3.0, 9.3, 17.6],
   "false_alarms_during_baseline": 0,          // alerts more than 1 h before the first theft
   "false_alarms": [{"started", "rule", "severity", "message"}],
   "source": "...", "fetched": "...", "price_note": "..."}]}
```

### `GET /api/evaluation`
Synthetic scorecard saved by `python -m bridgewatch.evaluate` (`results/evaluation.json`), same shape as v0.2
plus `generated_at` and `false_alarms_per_bridge_week`:
`{"config", "by_kind": {kind: {"runs", "detected", "median_minutes_to_alert", "median_lost_before_alert"}},
"false_alarms_per_bridge_day", "false_alarms_per_bridge_week", "false_alarms_by_rule", "clean_bridge_days",
"sweep": [{"z_threshold", "detected", "runs", "false_alarms_per_bridge_day"}], "note"}`. 404 if missing.

### `GET /api/evaluation/real`
Objective 2.3 on real believed-normal datasets, saved by `python -m bridgewatch.evaluate --real`
(`results/evaluation-real.json`). 404 if missing.

```json
{"generated_at": 1791410000.0, "config": {DetectorConfig}, "target_per_bridge_week": 1.0,
 "datasets": [{"key": "optimism-30d", "title": "...", "vault": "0x...", "dataset": "optimism-30d.json",
               "days": 30.0, "weeks_counted": 3.86, "transfers": 3475, "escrow_usd_at_start": 1.0e9,
               "false_alarms": 0, "per_week": 0.0, "meets_target": true, "by_rule": {},
               "alerts_during_warmup": 0, "alerts": [{"started", "rule", "severity", "message"}]}],
 "overall": {"datasets": 5, "bridge_weeks": 19.3, "false_alarms": 14, "per_bridge_week": 0.725,
             "worst_per_week": 3.37, "all_meet_target": false},
 "note": "..."}
```

### `GET /api/health`
200 when `status` is `ok` or `starting`, 503 when `degraded` (no successful poll for 90 s / 3 polls, or more than
confirmations + 50 blocks behind). Demo: `{"status": "ok", "mode": "demo", "clock"}`. Live:

```json
{"mode": "live", "status": "ok", "phase": "live", "chain": "ethereum", "head": 26143371, "cursor": 26143365,
 "lag_blocks": 6, "confirmations": 6, "last_ok_at": 1791410648.7, "last_error": null, "consecutive_failures": 0,
 "rpc_calls": 96, "rpc_errors": 1,
 "notifications": {"enabled": false, "sent": 0, "failed": 0, "gave_up": 0, "pending": 0},
 "prices_usd": {"USDT": 1.0, "WBTC": 83158.11},
 "prices": {"WBTC": {"usd": 83158.11, "updated_at": 1791410000, "stale": false, "error": null}},
 "prices_stale": false,              // a feed failed (last good price kept) or its answer is over 2 h old
 "unpriced_transfers": 0,            // stored without USD because a token never had a price (not fed to the detector)
 "last_detection_latency_s": null}
```

### `GET /metrics`
Prometheus text: `bridgewatch_up`, and in live mode ingest lag, RPC calls/errors, failures, last OK time,
notifications sent/failed/gave_up, `bridgewatch_prices_stale`, `bridgewatch_unpriced_transfers_total`,
`bridgewatch_last_detection_latency_seconds`, transfers stored and alerts per bridge/rule, escrow per bridge.

### `GET /`
The dashboard (`web/bridgewatch.html`).
