"""Rebuild a small SQLite warehouse transactionally, then atomically replace it."""
import sqlite3
from .transform import MONEY


def load_database(root, clean, manifest):
    destination = root / "data/warehouse/bank_funding.sqlite"
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(".building.sqlite")
    temporary.unlink(missing_ok=True)
    conn = sqlite3.connect(temporary)
    try:
        conn.executescript((root / "sql/schema.sql").read_text())
        banks = clean.sort_values("period_id").groupby("cert", as_index=False).tail(1)
        banks[["cert", "bank_name", "state", "bank_class", "report_date"]].rename(
            columns={"report_date": "attributes_as_of"}).to_sql("dim_bank", conn, if_exists="append", index=False)
        dates = clean[["period_id", "report_date"]].drop_duplicates().sort_values("period_id")
        dates["year"] = dates["period_id"] // 4
        dates["quarter"] = dates["period_id"] % 4 + 1
        dates.to_sql("dim_period", conn, if_exists="append", index=False)
        facts = clean[["cert", "period_id", *MONEY, "bank_name", "state", "bank_class", "source_id"]].rename(
            columns={"bank_name": "reported_name", "state": "reported_state", "bank_class": "reported_class"})
        facts["snapshot_id"] = manifest["snapshot_id"]
        conn.execute("INSERT INTO pipeline_run VALUES (?,?,?,?,?)",
                     (manifest["snapshot_id"], manifest["retrieved_at_utc"], manifest["rows"], len(clean),
                      manifest["config"]["api_url"]))
        conn.commit()
        facts.to_sql("fact_financials", conn, if_exists="append", index=False)
        if conn.execute("PRAGMA foreign_key_check").fetchall():
            raise ValueError("Foreign key check failed")
        conn.commit()
    finally:
        conn.close()
    temporary.replace(destination)
    return destination
