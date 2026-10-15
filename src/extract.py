"""Download FDIC bank-quarter observations and preserve an auditable snapshot."""
import csv
import hashlib
import json
import time
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


def quarter_ends(start, end):
    import calendar
    year, month = int(start[:4]), int(start[5:7])
    result = []
    while True:
        date = f"{year:04d}-{month:02d}-{calendar.monthrange(year, month)[1]:02d}"
        if date > end:
            return result
        result.append(date)
        month += 3
        if month > 12:
            year, month = year + 1, month - 12


def request_json(url):
    """Retry transient failures, but never hide a malformed response or 4xx."""
    for attempt in range(4):
        try:
            request = Request(url, headers={"User-Agent": "BankFundingMonitor/1.0 public-data-research"})
            with urlopen(request, timeout=45) as response:
                body = response.read()
            payload = json.loads(body)
            if "data" not in payload or "meta" not in payload:
                raise ValueError("Unexpected FDIC response schema")
            return body, payload
        except (HTTPError, URLError, TimeoutError) as exc:
            if isinstance(exc, HTTPError) and exc.code not in (429, 500, 502, 503, 504):
                raise
            if attempt == 3:
                raise
            time.sleep(2 ** attempt)


def download(root, config):
    snapshot_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    folder = root / "data" / "raw" / snapshot_id
    folder.mkdir(parents=True, exist_ok=False)
    manifest = {"snapshot_id": snapshot_id, "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
                "config": config, "pages": [], "quarters": []}
    rows = []
    for quarter in quarter_ends(config["start_quarter"], config["end_quarter"]):
        offset, expected, period_rows, seen = 0, None, [], set()
        filters = f"REPDTE:{quarter.replace('-', '')} AND BKCLASS:({' OR '.join(config['bank_classes'])})"
        while expected is None or offset < expected:
            params = {"filters": filters, "fields": ",".join(config["fields"]), "sort_by": "CERT",
                      "sort_order": "ASC", "limit": 10000, "offset": offset, "format": "json"}
            url = config["api_url"] + "?" + urlencode(params)
            body, payload = request_json(url)
            total = int(payload["meta"]["total"])
            if expected is not None and total != expected:
                raise ValueError("API total changed during pagination; retry a new snapshot")
            expected = total
            batch = [hit["data"] for hit in payload["data"]]
            if not batch:
                raise ValueError(f"No records returned for {quarter}; incomplete snapshot")
            ids = [(str(r.get("CERT")), str(r.get("REPDTE"))) for r in batch]
            if len(set(ids)) != len(ids) or seen.intersection(ids):
                raise ValueError("Duplicate bank-quarter from API pagination")
            seen.update(ids)
            name = f"financials_{quarter}_{offset:05d}.json"
            (folder / name).write_bytes(body)
            manifest["pages"].append({"file": name, "url": url, "rows": len(batch),
                                      "sha256": hashlib.sha256(body).hexdigest(),
                                      "api_meta": payload["meta"]})
            period_rows.extend(batch)
            offset += len(batch)
        if len(period_rows) != expected:
            raise ValueError("API count reconciliation failed")
        rows.extend(period_rows)
        manifest["quarters"].append({"quarter": quarter, "api_total": expected, "downloaded": len(period_rows)})
        print(f"Downloaded {quarter}: {len(period_rows):,} bank records", flush=True)
    # This is a flat copy of selected source fields, BEFORE cleaning or unit conversion.
    with (folder / "financials_raw.csv").open("w", newline="", encoding="utf-8-sig") as out:
        writer = csv.DictWriter(out, fieldnames=config["fields"], extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    manifest["raw_csv_sha256"] = hashlib.sha256((folder / "financials_raw.csv").read_bytes()).hexdigest()
    manifest["rows"] = len(rows)
    (folder / "manifest.json").write_text(json.dumps(manifest, indent=2))
    # Publish the pointer only after every page and count has been checked.
    (root / "data/raw/latest_snapshot.txt").write_text(snapshot_id + "\n")
    return folder


def read_snapshot(folder):
    manifest = json.loads((folder / "manifest.json").read_text())
    rows = []
    for page in manifest["pages"]:
        body = (folder / page["file"]).read_bytes()
        if hashlib.sha256(body).hexdigest() != page["sha256"]:
            raise ValueError(f"Source checksum mismatch: {page['file']}")
        rows.extend(hit["data"] for hit in json.loads(body)["data"])
    if len(rows) != manifest["rows"]:
        raise ValueError("Snapshot row count mismatch")
    raw_csv = folder / "financials_raw.csv"
    if hashlib.sha256(raw_csv.read_bytes()).hexdigest() != manifest["raw_csv_sha256"]:
        raise ValueError("Raw CSV checksum mismatch")
    return rows, manifest
