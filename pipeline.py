"""Run from any directory: python pipeline.py [--refresh] [--snapshot SNAPSHOT_ID]."""
import argparse
import json
from pathlib import Path
from src.extract import download, read_snapshot
from src.transform import clean
from src.load import load_database
from src.analyze import run_analysis


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh", action="store_true", help="Fetch a new immutable API snapshot")
    parser.add_argument("--snapshot", help="Rebuild a specific saved snapshot instead of latest")
    args = parser.parse_args()
    if args.refresh and args.snapshot:
        parser.error("Use either --refresh or --snapshot, not both")
    root = Path(__file__).resolve().parent
    config = json.loads((root / "config.json").read_text())
    if args.refresh:
        folder = download(root, config)
    else:
        pointer = root / "data/raw/latest_snapshot.txt"
        if not args.snapshot and not pointer.exists():
            parser.error("No snapshot exists. Run python pipeline.py --refresh first.")
        snapshot_id = args.snapshot or pointer.read_text().strip()
        if Path(snapshot_id).name != snapshot_id or snapshot_id in (".", ".."):
            parser.error("Snapshot must be a directory name, not a path")
        folder = root / "data/raw" / snapshot_id
    rows, manifest = read_snapshot(folder)
    frame = clean(rows)
    (root / "data/processed").mkdir(parents=True, exist_ok=True)
    frame.to_csv(root / "data/processed/financials_clean.csv", index=False, encoding="utf-8-sig")
    db = load_database(root, frame, manifest)
    summary = run_analysis(root, db, config)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
