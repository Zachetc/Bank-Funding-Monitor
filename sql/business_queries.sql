-- Open data/warehouse/bank_funding.sqlite in DB Browser for SQLite or sqlite3.
-- Monetary balance fields end in _k and are USD thousands. Ratios are fractions.

-- 1. Which peers deserve a funding review, and why?
SELECT cert, bank_name, state, report_date,
       ROUND(deposit_yoy * 100, 2) AS deposit_yoy_pct,
       ROUND(loan_to_deposit * 100, 2) AS net_loans_to_deposits_pct,
       ROUND(deposit_loss_k / 1000.0, 1) AS deposit_loss_usd_m,
       review_reason, possible_structural_change
FROM v_review_queue
ORDER BY deposit_loss_k DESC, cert;

-- 2. How concentrated are gross year-over-year deposit declines?
WITH latest_losses AS (
  SELECT m.cert, m.bank_name, m.deposit_loss_k
  FROM v_bank_metrics m JOIN fact_peer_signals s USING(cert,period_id)
  WHERE m.period_id=(SELECT MAX(period_id) FROM dim_period) AND m.deposit_loss_k>0
)
SELECT *,
       ROW_NUMBER() OVER(ORDER BY deposit_loss_k DESC,cert) AS loss_rank,
       1.0 * SUM(deposit_loss_k) OVER(ORDER BY deposit_loss_k DESC,cert ROWS UNBOUNDED PRECEDING)
       / SUM(deposit_loss_k) OVER() AS cumulative_loss_share
FROM latest_losses ORDER BY deposit_loss_k DESC,cert;

-- 3. Aggregate matched-bank deposit growth, not average bank growth.
SELECT m.report_date, COUNT(*) AS matched_banks,
       1.0 * SUM(m.deposits_k) / SUM(m.deposits_prior_year_k) - 1 AS matched_deposit_yoy
FROM v_bank_metrics m JOIN fact_peer_signals s USING(cert,period_id)
WHERE m.deposits_prior_year_k>0 AND m.deposits_k IS NOT NULL
GROUP BY m.period_id,m.report_date ORDER BY m.period_id;

-- 4. Describe one bank across time. Change the bound value in your SQL client.
SELECT cert, bank_name, report_date, assets_k, deposits_k, loan_to_deposit, deposit_yoy
FROM v_bank_metrics WHERE cert=628 ORDER BY period_id;

-- 5. Investigate abrupt changes before assuming they reflect organic flows.
SELECT m.cert,m.bank_name,m.report_date,m.deposit_yoy,s.deposit_modified_z
FROM v_bank_metrics m JOIN fact_peer_signals s USING(cert,period_id)
WHERE s.possible_structural_change=1 AND m.period_id=(SELECT MAX(period_id) FROM dim_period)
ORDER BY ABS(m.deposit_yoy) DESC;
