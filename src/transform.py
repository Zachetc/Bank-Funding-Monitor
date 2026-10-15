"""Clean types without imputing missing financial values or deleting outliers."""
import pandas as pd

MAPPING = {"CERT": "cert", "REPDTE": "report_date", "NAME": "bank_name", "STALP": "state",
           "BKCLASS": "bank_class", "ASSET": "assets_k", "DEP": "deposits_k",
           "DEPDOM": "domestic_deposits_k", "LNLSNET": "net_loans_k", "CHBAL": "cash_k",
           "EQ": "equity_k", "ID": "source_id"}
MONEY = ["assets_k", "deposits_k", "domestic_deposits_k", "net_loans_k", "cash_k", "equity_k"]


def clean(rows):
    frame = pd.DataFrame(rows)
    missing = set(MAPPING) - set(frame.columns)
    if missing:
        raise ValueError(f"Missing source fields: {sorted(missing)}")
    frame = frame[list(MAPPING)].rename(columns=MAPPING)
    frame["cert"] = pd.to_numeric(frame["cert"], errors="raise").astype("int64")
    frame["report_date"] = pd.to_datetime(frame["report_date"], format="%Y%m%d", errors="raise")
    if frame.duplicated(["cert", "report_date"]).any():
        raise ValueError("Duplicate bank-quarter; no silent keep-first deduplication")
    if not frame["report_date"].dt.is_quarter_end.all():
        raise ValueError("Unexpected non-quarter-end reporting date")
    for col in ["bank_name", "state", "bank_class", "source_id"]:
        frame[col] = frame[col].astype("string").str.strip()
        if frame[col].isna().any() or frame[col].eq("").any():
            raise ValueError(f"Missing identifier/label: {col}")
    for col in MONEY:
        # Invalid tokens fail; true nulls remain null. Zero stays zero.
        frame[col] = pd.to_numeric(frame[col].replace("", None), errors="raise")
        if frame[col].dropna().mod(1).ne(0).any():
            raise ValueError(f"Unexpected non-integer USD-thousands value in {col}")
        frame[col] = frame[col].astype("Int64")
    for col in ["assets_k", "deposits_k", "domestic_deposits_k", "net_loans_k", "cash_k"]:
        if frame[col].dropna().lt(0).any():
            raise ValueError(f"Unexpected negative {col}; investigate the source")
    # Negative equity is possible and is preserved.
    frame["period_id"] = frame["report_date"].dt.year * 4 + frame["report_date"].dt.quarter - 1
    frame["report_date"] = frame["report_date"].dt.strftime("%Y-%m-%d")
    return frame.sort_values(["cert", "period_id"]).reset_index(drop=True)
