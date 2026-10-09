"""
Assign each of the 54 CONFIRMED catalog incidents to one primary pattern (patterns.md)
and total count and reported loss per pattern.

The assignment is a judgement from the catalog row (root cause, vault_drained,
malicious_tx_count, observable_signature) and the case pages; it is listed here so a
reviewer can disagree row by row.

  python pattern_counts.py -> out/pattern-counts.csv, out/pattern-assignment.csv
"""
from __future__ import annotations

import csv
from pathlib import Path

HERE = Path(__file__).resolve().parent
CAT = HERE.parent.parent / "01-hack-catalog" / "hacks.csv"

PATTERN = {
    "P1 key/keeper-authorised multi-asset sweep": [
        "2021-07-anyswap-v3", "2021-08-poly-network", "2022-06-harmony", "2023-07-multichain", "2023-11-heco-bridge",
        "2023-12-orbit-bridge", "2025-06-force-bridge", "2025-09-shibarium", "2026-02-iotex-iotube",
        "2026-05-gravity-bridge", "2026-05-thorchain-asgard", "2026-07-wanchain-cardano"],
    "P2 one or two huge releases (single-tx full drain)": [
        "2022-02-wormhole", "2022-03-ronin", "2023-07-poly-network", "2024-04-xbridge", "2024-08-ronin",
        "2026-04-kelpdao-rseth", "2026-05-verus-1", "2026-06-aztec-connect", "2026-06-aztec-bridge-escape",
        "2026-07-afx", "2026-07-verus-2"],
    "P3 copycat crowd drain": ["2022-08-nomad"],
    "P4 forged/invalid-proof releases, tx pattern unknown": [
        "2021-07-chainswap-1", "2021-07-thorchain-1", "2021-07-thorchain-2", "2021-09-pnetwork-pbtc", "2022-02-meter",
        "2026-05-tac-ton", "2026-08-allbridge-cctp", "2026-08-coreum-xrpl", "2026-09-liquid-network"],
    "P5 unbacked mint (escrow untouched)": [
        "2021-07-chainswap-2", "2022-01-qubit", "2022-10-bnb-token-hub", "2026-04-hyperbridge", "2026-05-adshares",
        "2026-05-map-protocol", "2026-06-syscoin", "2026-08-sandbox-oft"],
    "P6 approval drain through a router": [
        "2022-01-multichain-approvals", "2022-03-lifi", "2022-10-transit-swap", "2022-12-rubic",
        "2024-01-socket-bungee", "2024-07-lifi"],
    "P7 pool-pricing manipulation": ["2021-11-nerve-bridge", "2023-04-allbridge-core", "2026-07-allbridge-core-solana"],
    "P8 off-vault (solver, relayer, frontend)": [
        "2022-08-celer-cbridge", "2025-10-garden", "2026-07-across-solana", "2026-07-garden-htlc"],
}


def main():
    rows = {r["id"]: r for r in csv.DictReader(open(CAT, encoding="utf-8")) if r["status"] == "confirmed"}
    assigned = [i for v in PATTERN.values() for i in v]
    assert sorted(assigned) == sorted(rows), (set(rows) - set(assigned), set(assigned) - set(rows))
    out, assign = [], []
    total = sum(float(r["loss_usd"]) for r in rows.values())
    for p, ids in PATTERN.items():
        loss = sum(float(rows[i]["loss_usd"]) for i in ids)
        out.append({"pattern": p, "incidents": len(ids), "loss_musd": round(loss / 1e6, 1),
                    "share_of_loss": round(loss / total, 3),
                    "median_loss_musd": round(sorted(float(rows[i]["loss_usd"]) for i in ids)[len(ids) // 2] / 1e6, 2)})
        for i in ids:
            assign.append({"id": i, "pattern": p, "loss_musd": round(float(rows[i]["loss_usd"]) / 1e6, 2),
                           "root_cause": rows[i]["root_cause_category"], "design": rows[i]["design"]})
    for path, data in ((HERE / "out" / "pattern-counts.csv", out), (HERE / "out" / "pattern-assignment.csv", assign)):
        with open(path, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(data[0]))
            w.writeheader()
            w.writerows(data)
    for r in out:
        print(r)


if __name__ == "__main__":
    main()
