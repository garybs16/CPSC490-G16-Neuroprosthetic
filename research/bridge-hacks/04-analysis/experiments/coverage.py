"""
Coverage-gap estimate over the 54 CONFIRMED catalog incidents (01-hack-catalog/hacks.csv).

Each incident's reported loss is split (in $M) into the data a monitor needs to SEE it.
The split is a hand estimate from the case pages, the dataset `coverage` notes and the
catalog's main_assets column; where a split is unknown the whole loss goes to the main
bucket. Treat the totals as +/- 10%, not as measurements.

Buckets
  eth_token      ERC-20 (incl. WETH) released by an Ethereum vault, priced by a standard feed
  eth_longtail   ERC-20 from an Ethereum vault with no standard price (project tokens)
  eth_native     native ETH from an Ethereum vault (invisible to Transfer logs)
  other_evm      a vault on another EVM chain (BSC, Arbitrum, Polygon, ...)
  non_evm        a vault/peg on a non-EVM chain (Bitcoin, Liquid, TON, Cardano, Solana, XRPL)
  mint           value minted without backing; no escrow outflow (needs cross-chain accounting)
  approval       pulled from user wallets via router allowances (needs approval-spend monitoring)
  offvault       solver / relayer inventory or a frontend (needs monitoring outside the bridge)

  python coverage.py  -> out/coverage.csv, out/coverage.json
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
CAT = HERE.parent.parent / "01-hack-catalog" / "hacks.csv"
FLOORS = HERE / "out" / "floors.json"

# id -> ({bucket: $M}, config_change_lead, note)
SPLIT = {
    "2021-07-chainswap-1": ({"eth_longtail": 0.8}, "", "mapped project tokens"),
    "2021-07-anyswap-v3": ({"eth_token": 7.9}, "", "MPC pools; chain split unknown"),
    "2021-07-chainswap-2": ({"mint": 4.4}, "", ""),
    "2021-07-thorchain-1": ({"eth_native": 5.0}, "", "rotating vault EOAs (no fixed vault)"),
    "2021-07-thorchain-2": ({"eth_token": 8.0}, "", ""),
    "2021-08-poly-network": ({"eth_token": 264.0, "eth_native": 9.0, "other_evm": 338.0}, "2 min", "ETH leg ~$273M"),
    "2021-09-pnetwork-pbtc": ({"non_evm": 12.7}, "", "BTC collateral"),
    "2021-11-nerve-bridge": ({"other_evm": 0.54}, "", "BSC pool"),
    "2022-01-multichain-approvals": ({"approval": 1.4}, "", ""),
    "2022-01-qubit": ({"mint": 80.0}, "", "fake deposit on ETH, mint on BSC"),
    "2022-02-wormhole": ({"eth_token": 254.0, "mint": 72.0}, "", "93,750 ETH left as WETH; rest kept on Solana"),
    "2022-02-meter": ({"other_evm": 4.4}, "", "BSC / Moonriver side"),
    "2022-03-lifi": ({"approval": 0.6}, "", ""),
    "2022-03-ronin": ({"eth_token": 624.0}, "", "ETH left as a WETH unwrap (visible)"),
    "2022-06-harmony": ({"eth_token": 76.0, "eth_native": 14.5, "other_evm": 9.5}, "", "13,100 ETH from the ETH manager"),
    "2022-08-nomad": ({"eth_token": 169.0, "eth_longtail": 21.0}, "41 days", ""),
    "2022-08-celer-cbridge": ({"offvault": 0.24}, "", "frontend/DNS"),
    "2022-10-transit-swap": ({"approval": 21.2}, "", ""),
    "2022-10-bnb-token-hub": ({"mint": 570.0}, "", ""),
    "2022-12-rubic": ({"approval": 1.41}, "", ""),
    "2023-04-allbridge-core": ({"other_evm": 0.57}, "", "BSC pool"),
    "2023-07-poly-network": ({"eth_token": 5.0}, "", "catalog says mint, but the ETH LockProxy released $5.77M of stablecoins (poly-2023.json)"),
    "2023-07-multichain": ({"eth_token": 126.0}, "", "MPC EOA vault on Ethereum"),
    "2023-11-heco-bridge": ({"eth_token": 65.3, "eth_native": 20.4, "eth_longtail": 0.9}, "", ""),
    "2023-12-orbit-bridge": ({"eth_token": 59.8, "eth_native": 21.9}, "", "~9,500 ETH native"),
    "2024-01-socket-bungee": ({"approval": 3.3}, "3 days", ""),
    "2024-04-xbridge": ({"eth_longtail": 1.44}, "minutes (listToken)", "STC/SRLTY/Mazi"),
    "2024-07-lifi": ({"approval": 9.73}, "facet added (lead unknown)", ""),
    "2024-08-ronin": ({"eth_native": 9.8, "eth_token": 2.2}, "49 min", ""),
    "2025-06-force-bridge": ({"eth_token": 1.6, "eth_native": 1.36, "other_evm": 0.8}, "lead unknown", ""),
    "2025-09-shibarium": ({"eth_token": 1.59, "eth_native": 0.81}, "same session", "scaled to the $2.4M headline"),
    "2025-10-garden": ({"offvault": 11.0}, "", "solver inventory"),
    "2026-02-iotex-iotube": ({"eth_token": 4.4}, "18 min", "+ CIOTX mint"),
    "2026-04-hyperbridge": ({"eth_token": 0.56, "mint": 1.94}, "", "WETH from gateway; bridged DOT minted"),
    "2026-04-kelpdao-rseth": ({"eth_token": 292.0}, "weeks (DVN 1-of-1)", "single tx"),
    "2026-05-tac-ton": ({"non_evm": 2.86}, "", "TON"),
    "2026-05-thorchain-asgard": ({"non_evm": 10.7}, "", "threshold-key vault across BTC/ETH/BSC/Base"),
    "2026-05-adshares": ({"mint": 0.63}, "", ""),
    "2026-05-verus-1": ({"eth_token": 8.24, "eth_native": 3.34}, "", "single tx"),
    "2026-05-map-protocol": ({"mint": 0.11}, "", ""),
    "2026-05-gravity-bridge": ({"eth_token": 5.4}, "new validator 1 day (disputed)", ""),
    "2026-06-syscoin": ({"mint": 10.0}, "", ""),
    "2026-06-aztec-connect": ({"eth_native": 1.0, "eth_longtail": 1.19}, "", "single tx; split rough"),
    "2026-06-aztec-bridge-escape": ({"eth_native": 2.0, "eth_token": 0.2}, "", "1,158 ETH"),
    "2026-07-across-solana": ({"offvault": 4.5}, "", "relayer capital"),
    "2026-07-allbridge-core-solana": ({"non_evm": 1.65}, "", "Solana pool"),
    "2026-07-wanchain-cardano": ({"non_evm": 9.0}, "", "Cardano treasury"),
    "2026-07-afx": ({"other_evm": 24.15}, "", "Arbitrum vault; 200 s request window"),
    "2026-07-verus-2": ({"eth_token": 4.53, "eth_native": 3.0}, "", "split rough"),
    "2026-07-garden-htlc": ({"offvault": 0.45}, "", "solver"),
    "2026-08-coreum-xrpl": ({"non_evm": 0.2}, "", "XRPL"),
    "2026-08-allbridge-cctp": ({"other_evm": 0.19}, "", "Base router"),
    "2026-08-sandbox-oft": ({"mint": 0.68}, "delegate/config change", ""),
    "2026-09-liquid-network": ({"non_evm": 320.0}, "", "Bitcoin federation peg"),
}

LAYERS = [
    ("L0 today: ERC-20 outflows from Ethereum vaults (standard prices)", {"eth_token"}),
    ("L1 + native ETH (traces / balance diffs)", {"eth_native"}),
    ("L2 + long-tail token prices (DEX-derived, flagged)", {"eth_longtail"}),
    ("L3 + cross-chain accounting (supply vs collateral, unbacked mints)", {"mint"}),
    ("L4 + other EVM chains (same detector, more ingest)", {"other_evm"}),
    ("L5 + non-EVM pegs (Bitcoin/Liquid, Solana, TON, Cardano, XRPL)", {"non_evm"}),
    ("L6 + approval-spend and solver/relayer wallet monitoring", {"approval", "offvault"}),
]


def main():
    rows = [r for r in csv.DictReader(open(CAT, encoding="utf-8")) if r["status"] == "confirmed"]
    out, tot = [], {}
    missing = [r["id"] for r in rows if r["id"] not in SPLIT]
    assert not missing, missing
    for r in rows:
        split, cc, note = SPLIT[r["id"]]
        loss = float(r["loss_usd"]) / 1e6
        s = sum(split.values())
        # scale the split to the headline loss so totals match the catalog
        scaled = {k: v * loss / s for k, v in split.items()}
        for k, v in scaled.items():
            tot[k] = tot.get(k, 0) + v
        out.append({"id": r["id"], "loss_musd": round(loss, 2), **{k: round(v, 2) for k, v in scaled.items()},
                    "config_change_before_theft": cc, "note": note})
    grand = sum(tot.values())
    cum, layers = 0.0, []
    for name, buckets in LAYERS:
        add = sum(tot.get(b, 0) for b in buckets)
        cum += add
        layers.append({"layer": name, "adds_musd": round(add, 1), "cumulative_musd": round(cum, 1),
                       "cumulative_share": round(cum / grand, 3)})
    cc_rows = [o for o in out if o["config_change_before_theft"]]
    cc_loss = sum(o["loss_musd"] for o in cc_rows)
    floors = json.loads(FLOORS.read_text()) if FLOORS.exists() else []
    fl_tracked = sum(f["tracked_stolen_usd"] for f in floors)
    fl_first = sum(f["tracked_stolen_usd"] * f["floor_6conf"] for f in floors)
    summary = {
        "confirmed_incidents": len(rows), "total_loss_musd": round(grand, 1),
        "by_bucket_musd": {k: round(v, 1) for k, v in sorted(tot.items(), key=lambda x: -x[1])},
        "layers": layers,
        "config_change_flagged": {"incidents": len(cc_rows), "loss_musd": round(cc_loss, 1),
                                  "ids": [o["id"] for o in cc_rows]},
        "replay_cases_unpreventable_share": {
            "note": "share of TRACKED stolen value (14 replay cases) that left before the earliest possible "
                    "6-confirmation alert on the first theft (sum of floor_6conf x stolen / sum stolen)",
            "value": round(fl_first / fl_tracked, 3) if fl_tracked else None},
    }
    with open(HERE / "out" / "coverage.csv", "w", newline="") as f:
        cols = list(dict.fromkeys(k for o in out for k in o))
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(out)
    (HERE / "out" / "coverage.json").write_text(json.dumps(summary, indent=1) + "\n")
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
