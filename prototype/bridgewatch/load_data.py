"""
Import every saved dataset (hack cases and believed-normal periods) into the
SQLite database, so the data can be queried in one place.

  python -m bridgewatch.load_data                   # every file under bridgewatch/data/, into bridgewatch-datasets.db
  python -m bridgewatch.load_data --db datasets.db  # a separate database
  python -m bridgewatch.load_data path/to/file.json.gz

Each dataset is stored under its own bridge id (the case key, e.g. "orbit-2023")
with source 'file:<key>', so imported data never mixes with live bridges and is
never removed by live mode's retention. Re-running inserts nothing new: the
primary key (chain, tx_hash, log_index) makes the import idempotent.
"""

from __future__ import annotations
import argparse
import json
from pathlib import Path

from .config import DATA_DIR
from .source import FileSource, find_datasets
from .store import Store

DATASETS_DB = "bridgewatch-datasets.db"


def load(store: Store, paths: list[Path]) -> list[dict]:
    """Import the given dataset files. Returns one summary per dataset."""
    out = []
    for path in paths:
        src = FileSource(path)
        transfers = src.transfers()
        new = 0
        for batch in src.batches():
            new += sum(store.add_transfers(batch.transfers, source=f"file:{src.key}").values())
        store.put(f"dataset:{src.key}", json.dumps({
            "title": src.title, "kind": src.kind, "vault": src.vault, "file": str(path.name),
            "start_ts": src.start_ts, "end_ts": src.end_ts, "transfers": len(transfers),
            "escrow_usd_at_start": src.escrow_usd_at_start}))
        out.append({"key": src.key, "kind": src.kind, "file": path.name, "transfers": len(transfers),
                    "new": new, "already_stored": len(transfers) - new})
    return out


def main(argv: list[str] | None = None) -> list[dict]:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("files", nargs="*", help="dataset files (default: every file under bridgewatch/data/)")
    ap.add_argument("--db", default=DATASETS_DB,
                    help=f"SQLite file (default: {DATASETS_DB}, kept separate from the live database)")
    args = ap.parse_args(argv)
    paths = [Path(f) for f in args.files] or find_datasets(DATA_DIR)
    if not paths:
        raise SystemExit(f"No dataset files found under {DATA_DIR}.")
    db = args.db
    store = Store(db)
    if store.get("cursor") is not None:
        # A live-mode database: the normal/ datasets cover the same vaults and dates as live mode,
        # and the (chain, tx, log_index) key would make live ingest silently skip those transfers.
        raise SystemExit(f"{db} is a live-mode database (it has an ingest cursor). "
                         f"Import datasets into a separate file, e.g. --db {DATASETS_DB}.")
    rows = load(store, paths)
    print(f"Database {db}")
    print(f"  {'dataset':34} {'kind':7} {'transfers':>9} {'new':>7} {'already':>8}")
    for r in rows:
        print(f"  {r['key']:34} {r['kind']:7} {r['transfers']:9,} {r['new']:7,} {r['already_stored']:8,}")
    print(f"  {'total':34} {'':7} {sum(r['transfers'] for r in rows):9,} {sum(r['new'] for r in rows):7,} "
          f"{sum(r['already_stored'] for r in rows):8,}")
    return rows


if __name__ == "__main__":
    main()
