# Bank Deposits and Lending — findings

**Reporting date:** 2026-06-30  
**Source retrieval:** 2026-10-12T00:43:10.946248+00:00  
**Audience:** banking research or treasury peer-monitoring team  
**Purpose:** identify comparable banks with falling deposits and relatively high lending ratios.

## Analytical approach

The review queue contains **40 banks** that combine shrinking
deposits with net loans/deposits at or above the same-quarter peer threshold.
Banks are ranked by absolute dollar decline. The resulting list supports
comparison across a defined peer group; the project has not measured analyst
time saved, prevented losses, funding-cost changes, or downstream business outcomes.

## What the data show

- The latest peer universe contains **890 banks** with
  assets from $1bn to under $10bn. **889** have usable
  prior-year growth and lending ratios.
- Median bank deposit growth is **5.07% YoY**.
  **159 banks** report contracting deposits, so the
  positive median does not describe every bank.
- The lending threshold is **95.30%**
  (P75). Combining it with contraction produces
  **40 review candidates**, or
  **4.5% of eligible banks**.
- The review queue's combined gross YoY deposit decline is
  **$3.325bn**. This is a balance change,
  not a forecast of cash outflows or lost revenue.
- Across all contracting peers, gross declines total
  **$18.197bn**. The ten largest contributors
  account for **50.45%** of that total.
- **5 banks** have unusually weak growth under the
  modified-z rule. This is a separate exploratory flag, not the definition of
  the review queue.

## Largest declines within the review queue

| FDIC cert | Banking entity | State | Deposit growth YoY | Net loans/deposits | Gross deposit decline |
|---:|---|---|---:|---:|---:|
| 5146 | WELLS FARGO BANK S CNTL NA | TX | -30.5% | 102.1% | $733.7m |
| 10988 | STEARNS BANK NATIONAL ASSN | MN | -15.6% | 114.8% | $441.3m |
| 29546 | GREAT SOUTHERN BANK | MO | -7.2% | 98.6% | $338.4m |
| 30052 | BLUE FOUNDRY BANK | NJ | -15.5% | 134.6% | $225.0m |
| 90215 | AVIDIA BANK | MA | -8.9% | 100.1% | $217.1m |
| 27074 | STATE BANK OF TEXAS | TX | -6.8% | 96.8% | $155.8m |
| 35274 | BLUE RIDGE BANK NA | VA | -7.5% | 96.8% | $153.2m |
| 597 | CHEMUNG CANAL TRUST CO | NY | -4.4% | 98.9% | $108.7m |

These observations represent FDIC certificate-level banking entities rather
than consolidated holding companies.

## An observation that challenges the rule

The first row, **WELLS FARGO BANK S CNTL NA (CERT 5146)**, shows
deposit growth of **-30.5%** and net loans/deposits of
**102.1%**, yet also reports cash/deposits of
**50.2%** and book equity/assets of
**30.1%**. Those additional fields make a simple “distress”
label unsupported. Business model and funding structure can affect the
interpretation of these ratios. Cash and book equity are also incomplete
measures of liquidity and capital adequacy.

## Threshold sensitivity

| Lending percentile | Lending ratio cutoff | Review banks | Queue gross deposit declines |
|---|---:|---:|---:|
| P70 | 93.7% | 51 | $4.447bn |
| P75 | 95.3% | 40 | $3.325bn |
| P80 | 97.7% | 35 | $3.006bn |
| P90 | 102.4% | 21 | $1.321bn |

P75 is a documented analytical choice rather than an optimized or regulatory
threshold. The alternative cutoffs show how queue size and represented deposit
declines change as the lending-ratio criterion becomes more selective.

## Evidence and limits

The source contains 67,451 bank-quarter records over
15 quarters. API totals reconcile to downloaded records.
Four early quarters cannot have YoY growth within this extract. Peer membership
changes with size, and the historical data reflect revisions known at retrieval,
not the information available at each old reporting date.

Data lineage: source API responses → raw CSV → typed CSV → SQLite financial
view → peer metrics → dashboard CSVs. The source manifest at
`data/raw/20261012T004310946138Z/manifest.json` records request URLs, API metadata, and
checksums. `reports/validation.json` records validation results, and
`docs/DATA_DICTIONARY.md` defines the KPIs.

Public source: [FDIC BankFind API](https://api.fdic.gov/banks/docs/).
