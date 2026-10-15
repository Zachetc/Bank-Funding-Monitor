# Tableau workbook specification

The dashboard is packaged in [Bank_Funding_Monitor.twbx](../tableau/Bank_Funding_Monitor.twbx). It contains two native bar-chart worksheets, one dashboard, two CSV sources, and two active Hyper extracts.

## Workbook construction

[build_dashboard.py](../build_dashboard.py) generates the workbook XML with Python's `xml.etree.ElementTree`. Tableau Hyper API 0.0.20746 creates the extracts, and Python's `zipfile` packages the workbook and data in the TWBX archive. The workbook was generated programmatically rather than saved through the Tableau interface.

| Component | Source | Structure |
|---|---|---|
| Deposit direction chart | `Data/DepositCounts.csv` | Two rows: bank counts and labels for higher and lower deposits |
| Deposit balance comparison | `Data/BankBalances.csv` | Ten rows: five banking entities at two reporting dates |
| Count extract | `Data/Extracts/DepositCounts.hyper` | `Extract.Extract` table matching the count CSV |
| Balance extract | `Data/Extracts/BankBalances.hyper` | `Extract.Extract` table matching the balance CSV |
| Dashboard | `Bank Deposits and Lending` | Fixed 1440 × 1000 layout with two charts, selection criteria, units, and source attribution |

The analytical source for the full 40-bank queue is [review_queue.csv](../data/processed/review_queue.csv). The balance chart shows the five largest absolute deposit declines within that queue.

## Visual definitions

The count chart compares 730 banks with higher deposits against 159 with lower deposits. Its denominator is the 889 banks with valid comparisons for both June 2025 and June 2026.

The balance chart compares deposits in USD millions at the two reporting dates. Bank labels contain the reported dollar and percentage decline. The adjacent text defines the 95.30% net-loan/deposit threshold and identifies the 40 banks meeting the joint rule.

Bank names refer to FDIC certificate-level entities. The Wells Fargo entry is certificate 5146, a distinct banking entity rather than the consolidated group.

## Validation

The recorded checks cover XML parsing, required build metadata, lowercase hexadecimal colors, worksheet-window element order, package integrity, chart counts, and two reporting dates per displayed bank. Both Hyper extracts were reopened and every stored value was compared with its CSV source.

These are targeted structural and data checks. Native Tableau Desktop/Public opening and rendering have not been verified. [tableau_validation.json](../reports/tableau_validation.json) records the validation scope.

## Preview

[dashboard_preview.png](../reports/dashboard_preview.png) is a Matplotlib rendering based on the same dashboard CSVs. It is a companion visualization, not a screenshot of Tableau.
