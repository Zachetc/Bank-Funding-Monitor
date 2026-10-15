"""Explainable data mining: peer segmentation, robust outliers, and Pareto loss."""
import json
import sqlite3
from contextlib import closing
import numpy as np
import pandas as pd


def modified_z(series):
    if series.notna().sum() == 0:
        return pd.Series(np.nan, index=series.index)
    median = series.median()
    mad = (series - median).abs().median()
    if pd.isna(mad) or mad == 0:
        return pd.Series(np.nan, index=series.index)
    return 0.67448975 * (series - median) / mad


def run_analysis(root, db_path, config):
    out = root / "data/processed"
    out.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(db_path)) as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        all_metrics = pd.read_sql_query("SELECT * FROM v_bank_metrics ORDER BY period_id,cert", conn)
        peers = all_metrics.loc[all_metrics.assets_k.ge(config["peer_min_assets_usd_thousands"]) &
                                all_metrics.assets_k.lt(config["peer_max_assets_usd_thousands_exclusive"])].copy()
        if peers.empty or peers.period_id.max() != all_metrics.period_id.max():
            raise ValueError("No peers exist in the latest source quarter; do not show a stale dashboard")
        peers["peer_loan_to_deposit_threshold"] = peers.groupby("period_id").loan_to_deposit.transform(
            lambda s: s.quantile(config["high_loan_to_deposit_quantile"]))
        peers["deposit_modified_z"] = peers.groupby("period_id").deposit_yoy.transform(modified_z)
        peers["eligible"] = (peers.deposit_yoy.notna() & peers.loan_to_deposit.notna()).astype(int)
        peers["contracting"] = peers.deposit_yoy.lt(0).astype(int)
        peers["high_loan_to_deposit"] = peers.loan_to_deposit.ge(peers.peer_loan_to_deposit_threshold).astype(int)
        peers["review_flag"] = ((peers.eligible == 1) & (peers.contracting == 1) &
                                 (peers.high_loan_to_deposit == 1)).astype(int)
        peers["deposit_outlier"] = peers.deposit_modified_z.le(config["deposit_outlier_modified_z"]).astype(int)
        peers["possible_structural_change"] = peers.deposit_yoy.abs().gt(
            config["possible_structural_change_abs_yoy"]).astype(int)
        peers["segment"] = np.select(
            [peers.eligible.eq(0), peers.review_flag.eq(1), peers.contracting.eq(1), peers.high_loan_to_deposit.eq(1)],
            ["Insufficient history", "Review funding", "Deposit contraction", "Lending intensive"],
            default="Other peers")
        percentile_label = f"P{100 * config['high_loan_to_deposit_quantile']:g}"
        peers["review_reason"] = np.where(peers.review_flag.eq(1),
            f"Deposits fell YoY; net loans/deposits at or above peer {percentile_label}", "Does not meet joint review rule")
        peers.loc[peers.eligible.eq(0), "review_reason"] = "Missing prior-year deposits or usable ratio"
        peers["is_latest"] = peers.period_id.eq(peers.period_id.max()).astype(int)
        peers["bank_label"] = peers.bank_name + " [" + peers.cert.astype(str) + "]"
        peers["assets_b"] = peers.assets_k / 1_000_000
        peers["deposits_b"] = peers.deposits_k / 1_000_000
        peers["deposit_loss_m"] = peers.deposit_loss_k / 1000
        peers["loan_to_deposit_pct"] = peers.loan_to_deposit * 100
        peers["deposit_yoy_pct"] = peers.deposit_yoy * 100
        peers["quarter_label"] = peers.year.astype(str) + " Q" + peers.quarter.astype(str)
        signals = peers[["cert", "period_id", "peer_loan_to_deposit_threshold", "deposit_modified_z", "eligible",
                         "review_flag", "deposit_outlier", "possible_structural_change", "segment", "review_reason"]]
        conn.execute("DROP TABLE IF EXISTS fact_peer_signals")
        conn.execute("""CREATE TABLE fact_peer_signals (
          cert INTEGER NOT NULL, period_id INTEGER NOT NULL,
          peer_loan_to_deposit_threshold REAL, deposit_modified_z REAL, eligible INTEGER NOT NULL,
          review_flag INTEGER NOT NULL, deposit_outlier INTEGER NOT NULL,
          possible_structural_change INTEGER NOT NULL, segment TEXT NOT NULL, review_reason TEXT NOT NULL,
          PRIMARY KEY (cert,period_id),
          FOREIGN KEY(cert,period_id) REFERENCES fact_financials(cert,period_id))""")
        signals.to_sql("fact_peer_signals", conn, if_exists="append", index=False)
        conn.executescript("""
          DROP VIEW IF EXISTS v_review_queue;
          CREATE VIEW v_review_queue AS
          SELECT m.*, s.peer_loan_to_deposit_threshold, s.deposit_modified_z,
                 s.review_flag, s.deposit_outlier, s.possible_structural_change, s.segment, s.review_reason
          FROM v_bank_metrics m JOIN fact_peer_signals s USING(cert,period_id)
          WHERE s.review_flag=1 AND m.period_id=(SELECT MAX(period_id) FROM dim_period);
        """)
        conn.commit()
    peers.to_csv(out / "bank_quarter.csv", index=False, encoding="utf-8-sig", float_format="%.10g")
    latest = peers.loc[peers.is_latest.eq(1)].copy()
    latest.to_csv(out / "latest_peers.csv", index=False, encoding="utf-8-sig", float_format="%.10g")
    watch = latest.loc[latest.review_flag.eq(1)].sort_values(["deposit_loss_k", "cert"], ascending=[False, True])
    watch.to_csv(out / "review_queue.csv", index=False, encoding="utf-8-sig", float_format="%.10g")
    trend = []
    for _, group in peers.groupby("period_id"):
        matched = group.loc[group.deposits_prior_year_k.gt(0) & group.deposits_k.notna()]
        ratio_rows = group.loc[group.deposits_k.gt(0) & group.net_loans_k.notna()]
        trend.append({"report_date": group.report_date.iloc[0], "quarter_label": group.quarter_label.iloc[0],
            "banks": len(group), "eligible_banks": int(group.eligible.sum()),
            "review_banks": int(group.review_flag.sum()), "median_deposit_yoy": group.deposit_yoy.median() if group.deposit_yoy.notna().any() else np.nan,
            "matched_deposit_yoy": (matched.deposits_k.sum() / matched.deposits_prior_year_k.sum() - 1)
                if len(matched) else np.nan,
            "weighted_loan_to_deposit": ratio_rows.net_loans_k.sum() / ratio_rows.deposits_k.sum(),
            "total_deposits_b": group.deposits_b.sum()})
    trend = pd.DataFrame(trend)
    trend.to_csv(out / "peer_trend.csv", index=False, encoding="utf-8-sig", float_format="%.10g")
    losses = latest.loc[latest.deposit_loss_k.gt(0)].sort_values(["deposit_loss_k", "cert"], ascending=[False, True]).copy()
    losses["loss_rank"] = np.arange(1, len(losses) + 1)
    losses["cumulative_loss_share"] = losses.deposit_loss_k.cumsum() / losses.deposit_loss_k.sum()
    losses.to_csv(out / "deposit_loss_pareto.csv", index=False, encoding="utf-8-sig", float_format="%.10g")
    sensitivity = []
    for quantile in [0.70, 0.75, 0.80, 0.90]:
        cutoff = latest.loan_to_deposit.quantile(quantile)
        flag = latest.deposit_yoy.lt(0) & latest.loan_to_deposit.ge(cutoff)
        sensitivity.append({"peer_quantile": quantile, "ratio_cutoff": cutoff,
                            "review_banks": int(flag.sum()), "review_deposit_loss_m": latest.loc[flag].deposit_loss_m.sum()})
    pd.DataFrame(sensitivity).to_csv(out / "threshold_sensitivity.csv", index=False)
    summary = {"as_of": latest.report_date.iloc[0], "source_rows": len(all_metrics),
        "source_banks": int(all_metrics.cert.nunique()), "quarters": int(all_metrics.period_id.nunique()),
        "peer_rows": len(peers), "latest_peer_banks": len(latest), "eligible_banks": int(latest.eligible.sum()),
        "review_banks": len(watch), "contracting_banks": int(latest.contracting.sum()),
        "outlier_banks": int(latest.deposit_outlier.sum()), "median_deposit_yoy": float(latest.deposit_yoy.median()),
        "loan_to_deposit_threshold": float(latest.loan_to_deposit.quantile(config["high_loan_to_deposit_quantile"])),
        "threshold_quantile": config["high_loan_to_deposit_quantile"],
        "peer_deposits_b": float(latest.deposits_b.sum()), "gross_deposit_losses_m": float(losses.deposit_loss_m.sum()),
        "review_deposit_losses_m": float(watch.deposit_loss_m.sum()),
        "top10_loss_share": float(losses.head(10).deposit_loss_k.sum() / losses.deposit_loss_k.sum()),
        "review_structural_change_flags": int(watch.possible_structural_change.sum()),
        "structural_change_flags": int(latest.possible_structural_change.sum()),
        "missing_financial_cells": {c: int(all_metrics[c].isna().sum()) for c in
                                   ["assets_k", "deposits_k", "net_loans_k", "cash_k", "equity_k"]}}
    (root / "reports").mkdir(exist_ok=True)
    (root / "reports/summary.json").write_text(json.dumps(summary, indent=2, allow_nan=False))
    (root / "reports/analysis_config.json").write_text(json.dumps(config, indent=2))
    return summary
