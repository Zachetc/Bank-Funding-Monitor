PRAGMA foreign_keys = ON;
CREATE TABLE dim_bank (
    cert INTEGER PRIMARY KEY,
    bank_name TEXT NOT NULL,
    state TEXT NOT NULL,
    bank_class TEXT NOT NULL,
    attributes_as_of TEXT NOT NULL
);
CREATE TABLE dim_period (
    period_id INTEGER PRIMARY KEY,
    report_date TEXT NOT NULL UNIQUE,
    year INTEGER NOT NULL,
    quarter INTEGER NOT NULL CHECK (quarter BETWEEN 1 AND 4)
);
CREATE TABLE fact_financials (
    cert INTEGER NOT NULL REFERENCES dim_bank(cert),
    period_id INTEGER NOT NULL REFERENCES dim_period(period_id),
    assets_k INTEGER CHECK (assets_k >= 0),
    deposits_k INTEGER CHECK (deposits_k >= 0),
    domestic_deposits_k INTEGER CHECK (domestic_deposits_k >= 0),
    net_loans_k INTEGER CHECK (net_loans_k >= 0),
    cash_k INTEGER CHECK (cash_k >= 0),
    equity_k INTEGER,
    reported_name TEXT NOT NULL,
    reported_state TEXT NOT NULL,
    reported_class TEXT NOT NULL,
    source_id TEXT NOT NULL UNIQUE,
    snapshot_id TEXT NOT NULL REFERENCES pipeline_run(snapshot_id),
    PRIMARY KEY (cert, period_id)
);
CREATE INDEX idx_financials_period ON fact_financials(period_id);
CREATE TABLE pipeline_run (
    snapshot_id TEXT PRIMARY KEY,
    retrieved_at_utc TEXT NOT NULL,
    raw_rows INTEGER NOT NULL,
    loaded_rows INTEGER NOT NULL,
    source_url TEXT NOT NULL
);
CREATE VIEW v_bank_metrics AS
SELECT f.*, p.report_date, p.year, p.quarter,
       f.reported_name AS bank_name, f.reported_state AS state,
       1.0 * f.net_loans_k / NULLIF(f.deposits_k, 0) AS loan_to_deposit,
       1.0 * f.cash_k / NULLIF(f.deposits_k, 0) AS cash_to_deposit,
       1.0 * f.equity_k / NULLIF(f.assets_k, 0) AS equity_to_assets,
       prev.deposits_k AS deposits_prior_year_k,
       1.0 * (f.deposits_k - prev.deposits_k) / NULLIF(prev.deposits_k, 0) AS deposit_yoy,
       CASE WHEN prev.deposits_k > 0 THEN f.deposits_k - prev.deposits_k END AS deposit_change_k,
       CASE WHEN prev.deposits_k > 0 THEN MAX(prev.deposits_k - f.deposits_k, 0) END AS deposit_loss_k
FROM fact_financials f
JOIN dim_period p USING (period_id)
-- Exact calendar-quarter join: LAG(...,4) would be wrong if a bank missed a row.
LEFT JOIN fact_financials prev ON prev.cert = f.cert AND prev.period_id = f.period_id - 4;
