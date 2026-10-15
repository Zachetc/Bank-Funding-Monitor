"""Boundary and reconciliation tests; no network needed."""
import json
import sqlite3
import unittest
from pathlib import Path
import numpy as np
import pandas as pd
from src.transform import clean
from src.analyze import modified_z
from src.extract import quarter_ends, read_snapshot

ROOT = Path(__file__).resolve().parents[1]


def row(date="20241231", **overrides):
    value = dict(ID="1_"+date, CERT=1, REPDTE=date, NAME=" Test Bank ", STALP="NY", BKCLASS="N",
                 ASSET=2000, DEP=1000, DEPDOM=1000, LNLSNET=800, CHBAL=100, EQ=200)
    value.update(overrides)
    return value


class Boundaries(unittest.TestCase):
    def test_clean_types_null_zero_and_negative_equity(self):
        d = clean([row(CHBAL=None, DEP=0, EQ=-20)])
        self.assertTrue(pd.isna(d.cash_k.iloc[0]))
        self.assertEqual(d.deposits_k.iloc[0], 0)
        self.assertEqual(d.equity_k.iloc[0], -20)
        self.assertEqual(d.bank_name.iloc[0], "Test Bank")

    def test_duplicate_keys_fail(self):
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            clean([row(), row(DEP=900)])

    def test_invalid_money_fails(self):
        with self.assertRaises(ValueError):
            clean([row(DEP="oops")])

    def test_wrong_quarter_fails(self):
        with self.assertRaisesRegex(ValueError, "quarter-end"):
            clean([row(date="20241230")])

    def test_zero_mad_is_unknown_not_infinity(self):
        self.assertTrue(modified_z(pd.Series([0.1, 0.1, 0.1])).isna().all())

    def test_robust_outlier_retains_extreme_observation(self):
        scores = modified_z(pd.Series([0.01, 0.02, 0.03, 0.04, -0.9]))
        self.assertLess(scores.iloc[-1], -3.5)

    def test_quarter_generation(self):
        self.assertEqual(quarter_ends("2023-12-31", "2024-06-30"),
                         ["2023-12-31", "2024-03-31", "2024-06-30"])

    def test_missing_quarter_does_not_shift_yoy_and_zero_division_is_null(self):
        conn = sqlite3.connect(":memory:")
        conn.executescript((ROOT / "sql/schema.sql").read_text())
        conn.execute("INSERT INTO pipeline_run VALUES('test','2026-01-01',5,5,'test')")
        conn.execute("INSERT INTO dim_bank VALUES(1,'Test','NY','N','2024-12-31')")
        # Four preceding observations are NOT necessarily one calendar year.
        for period in [8091, 8092, 8093, 8094, 8096]:
            year, quarter = period // 4, period % 4 + 1
            dates = {1:'03-31',2:'06-30',3:'09-30',4:'12-31'}
            conn.execute("INSERT INTO dim_period VALUES(?,?,?,?)", (period,f"{year}-{dates[quarter]}",year,quarter))
            dep = 0 if period == 8096 else 100
            conn.execute("INSERT INTO fact_financials VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                         (1,period,200,dep,dep,80,10,20,'Test','NY','N',str(period),'test'))
        # 8094 has no 8090 row, so YoY is unknown, not a fabricated lag.
        self.assertIsNone(conn.execute("SELECT deposit_yoy FROM v_bank_metrics WHERE period_id=8094").fetchone()[0])
        result = conn.execute("SELECT deposit_yoy,loan_to_deposit FROM v_bank_metrics WHERE period_id=8096").fetchone()
        self.assertEqual(result[0], -1.0)
        self.assertIsNone(result[1])
        conn.close()


class DeliveredSnapshot(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db = sqlite3.connect(ROOT / "data/warehouse/bank_funding.sqlite")
        cls.summary = json.loads((ROOT / "reports/summary.json").read_text())

    @classmethod
    def tearDownClass(cls):
        cls.db.close()

    def test_source_checksums_and_counts(self):
        pointer = self.db.execute("SELECT snapshot_id FROM pipeline_run").fetchone()[0]
        rows, manifest = read_snapshot(ROOT / "data/raw" / pointer)
        self.assertEqual(len(rows), self.summary["source_rows"])
        for q in manifest["quarters"]:
            self.assertEqual(q["api_total"], q["downloaded"])
        self.assertEqual(self.db.execute("SELECT count(*) FROM fact_financials").fetchone()[0], len(rows))

    def test_relational_integrity(self):
        self.assertEqual(self.db.execute("PRAGMA integrity_check").fetchone()[0], "ok")
        self.assertEqual(self.db.execute("PRAGMA foreign_key_check").fetchall(), [])

    def test_sql_and_dashboard_review_queue_agree(self):
        sql_ids = {r[0] for r in self.db.execute("SELECT cert FROM v_review_queue")}
        csv_ids = set(pd.read_csv(ROOT / "data/processed/review_queue.csv").cert)
        self.assertEqual(sql_ids, csv_ids)
        self.assertEqual(len(sql_ids), self.summary["review_banks"])

    def test_ratio_units_and_independent_yoy(self):
        r = self.db.execute("SELECT net_loans_k,deposits_k,deposits_prior_year_k,loan_to_deposit,deposit_yoy FROM v_bank_metrics WHERE deposits_prior_year_k>0 AND deposits_k>0 LIMIT 1").fetchone()
        self.assertAlmostEqual(r[0] / r[1], r[3])
        self.assertAlmostEqual((r[1] - r[2]) / r[2], r[4])

    def test_weighted_ratio_uses_matching_nonnull_population(self):
        trend = pd.read_csv(ROOT / "data/processed/peer_trend.csv")
        peers = pd.read_csv(ROOT / "data/processed/latest_peers.csv")
        selected = peers.loc[peers.deposits_k.gt(0) & peers.net_loans_k.notna()]
        self.assertAlmostEqual(selected.net_loans_k.sum() / selected.deposits_k.sum(),
                               trend.weighted_loan_to_deposit.iloc[-1], places=8)

    def test_ranking_and_pareto_totals(self):
        p = pd.read_csv(ROOT / "data/processed/deposit_loss_pareto.csv")
        self.assertTrue(p.deposit_loss_k.is_monotonic_decreasing)
        self.assertAlmostEqual(p.cumulative_loss_share.iloc[-1], 1.0)
        self.assertAlmostEqual(p.deposit_loss_m.sum(), self.summary["gross_deposit_losses_m"], places=3)


if __name__ == "__main__":
    unittest.main(verbosity=2)
