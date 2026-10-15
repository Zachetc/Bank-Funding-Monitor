# Data dictionary and KPI contract

**Source:** [FDIC BankFind financials API](https://api.fdic.gov/banks/docs/).
Field definitions are archived in `fdic_field_definitions.json` from the FDIC's
[financial field dictionary](https://api.fdic.gov/banks/docs/risview_properties.yaml).
The FDIC [financial reporting interface](https://banks.data.fdic.gov/bankfind-suite/financialreporting/report)
labels these balance fields as **thousands of USD**.

## Population and grain

One source observation is **one FDIC certificate at one quarter end**. The primary
key is `(cert, period_id)`, not bank name. A certificate identifies a banking legal
entity, which may be a subsidiary of a larger holding company.

The API extraction covers 2022-12-31 through 2026-06-30, inclusive, and charter
classes N, NM, SM, SB, SI and SL. It does not filter on today's ACTIVE flag.
Uninsured classifications and insured US branches of foreign institutions are
outside this selected population.

The analytical peer set is chosen independently each quarter:
`1,000,000 <= assets_k < 10,000,000`, equivalent to $1 billion through just under
$10 billion. Historical membership can change. Prior-year balances are retrieved
from the complete source population even if the bank was outside the peer band
one year earlier. The series is not a fixed-cohort performance study.

## Raw to clean mapping

| API field | Clean field | Type / unit | Meaning |
|---|---|---|---|
| CERT | cert | integer identifier | FDIC certificate identifying the banking entity |
| REPDTE | report_date | ISO date | Quarter-end balance-sheet date |
| ID | source_id | string | Source record identifier |
| NAME | bank_name | text | Legal entity label reported for the period |
| STALP | state | text | Reported headquarters state; not deposit geography |
| BKCLASS | bank_class | text | Charter / regulator classification |
| ASSET | assets_k | integer, USD thousands | Total assets, excluding off-balance-sheet items |
| DEP | deposits_k | integer, USD thousands | Total deposits, including foreign offices |
| DEPDOM | domestic_deposits_k | integer, USD thousands | Domestic office deposits |
| LNLSNET | net_loans_k | integer, USD thousands | Net loans and leases |
| CHBAL | cash_k | integer, USD thousands | Cash and balances due from depository institutions |
| EQ | equity_k | integer, USD thousands | Book equity capital, which may be negative |

`_m` means USD millions (`_k / 1,000`); `_b` means USD billions
(`_k / 1,000,000`). Financial stocks are never summed across quarters.

## KPI definitions

| Metric | Calculation | Denominator / interpretation |
|---|---|---|
| Deposit growth YoY | `(DEP_t - DEP_t-4) / DEP_t-4` | Same certificate, exact prior-year quarter, prior deposits > 0 |
| Net loans / deposits | `LNLSNET / DEP` | Total deposits > 0; deliberately labeled **net** loans |
| Cash / deposits | `CHBAL / DEP` | Cash buffer proxy; not the regulatory Liquidity Coverage Ratio |
| Equity / assets | `EQ / ASSET` | Book leverage proxy; not CET1, Tier 1 or risk-weighted capital |
| Peer lending threshold | 75th percentile of valid peer net-loan/deposit ratios | Pandas linear quantile interpolation, same quarter |
| Review flag | Deposit growth < 0 AND lending ratio >= peer threshold | Missing growth or ratio is ineligible, not a healthy observation |
| Review bank count | Sum of review flag | One row per bank in the latest quarter |
| Median deposit growth | Median of valid bank-level YoY growth | Equal weight per bank, excluding missing history |
| Matched deposit growth | `sum(current deposits) / sum(prior deposits) - 1` | Same matched bank pairs on both sides; different from mean or median growth |
| Aggregate loan/deposit ratio | `sum(net loans) / sum(deposits)` | Matching records with non-null loans and positive deposits |
| Gross deposit decline | `max(prior deposits - current deposits, 0)` | Only available with valid prior deposits; a balance decline, not lost revenue |
| Review queue declines | Sum of gross decline within flagged banks | Never netted against growing banks and not a claim of preventable loss |
| Top-10 decline share | 10 largest gross declines / all gross declines | All contracting latest peers, not only the review queue |
| Modified z-score | `0.67448975 * (growth - median) / MAD` | MAD = median absolute deviation; null when MAD=0 or no data |
| Deposit outlier flag | Modified z <= -3.5 | Exploratory signal; no labeled outcome or predictive accuracy claim |
| Possible structural change | `abs(deposit growth) > 50%` | Prompts investigation; does not prove a merger or reporting error |

All ratio fields are fractions, except dashboard convenience fields ending in
`_pct`, which are already multiplied by 100. A `deposit_yoy` value of 0.05
corresponds to `deposit_yoy_pct` of 5.0.

## Cleaning and omissions

- The pipeline preserves API response bytes and a flat raw CSV before transformation.
- Label whitespace is removed; dates and integer money values are parsed explicitly.
- Duplicate keys, impossible dates, invalid numeric tokens, and unexpected negative
  deposits/assets/loans/cash fail validation. Records are not silently discarded or averaged.
- Nulls remain distinct from zero. Financial values are not imputed or winsorized.
- Valid extreme observations remain in the dataset with separate analytical flags.
- The saved snapshot has no missing cells in the five main financial balance fields.
- Four initial quarters have no prior-year comparison because the extract starts
  in 2022 Q4. The trend with valid YoY growth begins in 2023 Q4.
- The historical fact retains period-specific names/state/class. `dim_bank` holds
  the most recent descriptive attributes, a documented Type 1 dimension.

## What is not observed

Account-level flows, deposit interest rates, uninsured deposit shares, maturity
ladders, unused borrowing capacity, securities liquidity, counterparty exposure,
customer satisfaction, merger-adjusted organic growth and subsequent outcomes
are not present. A balance-sheet comparison cannot establish liquidity stress,
customer churn, solvency, causation, or an investment recommendation.
