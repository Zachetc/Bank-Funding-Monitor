# Dashboard interpretation

Bank Funding Monitor compares deposit balances and lending ratios among U.S. banking entities with $1 billion to under $10 billion in assets. The saved dashboard compares June 30, 2025 with June 30, 2026.

## Measures

| Measure | Calculation | Meaning |
|---|---|---|
| Deposit change | June 2026 deposits minus June 2025 deposits | Change in the reported balance |
| Deposit growth | Deposit change divided by June 2025 deposits | Percentage change over one year |
| Net loans/deposits | June 2026 net loans and leases divided by total deposits | Lending relative to the deposit base |

For example, a decrease from $100 million to $90 million is a $10 million decline and −10% growth. Net loans of $81 million against $90 million of deposits produce a 90% lending ratio. The ratio compares balance-sheet amounts; it does not trace individual deposits to specific loans.

## Population and selection

There are 890 banks in the June 2026 asset-size peer group. One lacks a valid prior-year comparison, leaving 889 comparable banks:

- 730 have higher deposits: 82.1%.
- 159 have lower deposits: 17.9%.
- None has an exactly unchanged deposit balance.

Each bank counts once regardless of its size. The review queue contains 40 banks with both falling deposits and a net-loan/deposit ratio at or above 95.30%. That cutoff is the 75th percentile of valid current ratios across the size peer group; it is an analytical choice rather than an FDIC rule or regulatory limit.

## Chart definitions

The first chart shows how common deposit increases and declines are across the comparable banks. The second shows paired deposit balances for the five largest dollar declines within the 40-bank review queue. The ranking uses absolute dollar decline rather than percentage decline or total bank size.

Balances are displayed in USD millions and rounded independently. Exact values are retained in the CSVs. The Wells Fargo entry is WELLS FARGO BANK S CNTL NA, FDIC certificate 5146; it does not represent the consolidated Wells Fargo group.

## Source lineage

The source is the [FDIC BankFind financials API](https://api.fdic.gov/banks/docs/). The October 12, 2026 snapshot contains 67,451 bank-quarter records from December 2022 through June 2026.

| Evidence | Location |
|---|---|
| Original API responses and raw CSV | `data/raw/20261012T004310946138Z/` |
| Request URLs, row counts, retrieval time, and checksums | `manifest.json` in the snapshot directory |
| Extraction implementation | `src/extract.py` |
| Source sample reconciliation | `reports/source_check/` |

On October 12, 2026, all five displayed banks at both reporting dates were re-fetched from the FDIC API. The ten records matched the saved snapshot for certificate, date, name, assets, deposits, net loans, and cash. All ten displayed balances also reconciled to the source deposit field. This sample check is separate from the full snapshot's page counts and checksums.

## Interpretation limits

A deposit decline can reflect corporate actions, transfers, deliberate balance-sheet changes, or differences in business model. The first displayed bank also reports cash of approximately 50% of deposits, which adds context to its lending ratio. These comparisons identify observable conditions; they do not establish financial distress or the cause of a balance change.
