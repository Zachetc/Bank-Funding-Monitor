"""Regenerate the business memo and verify the delivered snapshot offline."""
import hashlib
import json
import platform
import re
import sqlite3
import subprocess
import sys
from contextlib import closing
from pathlib import Path
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parent


def hashes():
    return {p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((ROOT/"data/processed").glob("*.csv"))}


def main():
    # A second full offline build detects accidental accumulation or unstable outputs.
    before=hashes()
    with closing(sqlite3.connect(ROOT/"data/warehouse/bank_funding.sqlite")) as db:
        snapshot=db.execute("SELECT snapshot_id FROM pipeline_run").fetchone()[0]
    build=subprocess.run([sys.executable,str(ROOT/"pipeline.py"),"--snapshot",snapshot],cwd=ROOT,text=True,capture_output=True)
    if build.returncode:raise RuntimeError(build.stdout+build.stderr)
    after=hashes()
    if before!=after:raise AssertionError("Offline CSV outputs changed; rebuild once and investigate the diff")
    test=subprocess.run([sys.executable,"-m","unittest","discover","-s","tests","-v"],cwd=ROOT,text=True,capture_output=True)
    (ROOT/"reports/test_results.txt").write_text(test.stdout+test.stderr)
    if test.returncode:raise RuntimeError(test.stdout+test.stderr)
    count=int(re.search(r"Ran (\d+) tests",test.stdout+test.stderr).group(1))
    summary=json.loads((ROOT/"reports/summary.json").read_text())
    manifest=json.loads((ROOT/"data/raw"/snapshot/"manifest.json").read_text())
    with closing(sqlite3.connect(ROOT/"data/warehouse/bank_funding.sqlite")) as db:
        tables={name:db.execute('SELECT COUNT(*) FROM '+name).fetchone()[0] for name in
                ['dim_bank','dim_period','fact_financials','fact_peer_signals','pipeline_run']}
        integrity=db.execute("PRAGMA integrity_check").fetchone()[0]
        foreign_keys=db.execute("PRAGMA foreign_key_check").fetchall()
    peers=pd.read_csv(ROOT/"data/processed/latest_peers.csv")
    watch=pd.read_csv(ROOT/"data/processed/review_queue.csv")
    sensitivity=pd.read_csv(ROOT/"data/processed/threshold_sensitivity.csv")
    raw=pd.read_csv(ROOT/"data/raw"/snapshot/"financials_raw.csv")
    clean=pd.read_csv(ROOT/"data/processed/financials_clean.csv")
    profile={"raw_rows":len(raw),"clean_rows":len(clean),"rows_removed":len(raw)-len(clean),
        "duplicate_bank_quarters":int(raw.duplicated(["CERT","REPDTE"]).sum()),
        "source_missing_cells":{c:int(raw[c].isna().sum()) for c in raw.columns},
        "labels_with_outer_whitespace":{c:int(raw[c].astype(str).ne(raw[c].astype(str).str.strip()).sum()) for c in ['NAME','STALP','BKCLASS']},
        "latest_peers_missing_yoy":int(peers.deposit_yoy.isna().sum()),
        "latest_zero_deposit_peers":int(peers.deposits_k.eq(0).sum()),
        "latest_peer_segments":{str(k):int(v) for k,v in peers.segment.value_counts().items()}}
    (ROOT/"reports/data_profile.json").write_text(json.dumps(profile,indent=2))
    validation={"snapshot_id":snapshot,"retrieved_at_utc":manifest["retrieved_at_utc"],
        "source_rows_reconciled":len(raw)==manifest['rows']==tables['fact_financials'],
        "all_quarter_api_counts_match":all(q['api_total']==q['downloaded'] for q in manifest['quarters']),
        "unit_and_integration_tests":f"{count} passed", "sqlite_integrity":integrity,
        "foreign_key_violations":len(foreign_keys),"offline_rebuild_csv_hashes_identical":before==after,
        "tables":tables,"processed_csv_sha256":after,
        "versions":{"python":platform.python_version(),"pandas":pd.__version__,"numpy":np.__version__,"sqlite":sqlite3.sqlite_version},
        "tableau":json.loads((ROOT/"reports/tableau_validation.json").read_text())}
    (ROOT/"reports/validation.json").write_text(json.dumps(validation,indent=2))
    date=pd.Timestamp(summary['as_of'])
    rows='\n'.join(f"| {int(r.cert)} | {r.bank_name.strip()} | {r.state} | {r.deposit_yoy:.1%} | {r.loan_to_deposit:.1%} | ${r.deposit_loss_m:,.1f}m |" for r in watch.head(8).itertuples())
    sens='\n'.join(f"| P{r.peer_quantile*100:.0f} | {r.ratio_cutoff:.1%} | {int(r.review_banks)} | ${r.review_deposit_loss_m/1000:.3f}bn |" for r in sensitivity.itertuples())
    first=watch.iloc[0]
    memo=f'''# Bank Deposits and Lending — findings

**Reporting date:** {summary['as_of']}  
**Source retrieval:** {manifest['retrieved_at_utc']}  
**Audience:** banking research or treasury peer-monitoring team  
**Purpose:** identify comparable banks with falling deposits and relatively high lending ratios.

## Analytical approach

The review queue contains **{summary['review_banks']} banks** that combine shrinking
deposits with net loans/deposits at or above the same-quarter peer threshold.
Banks are ranked by absolute dollar decline. The resulting list supports
comparison across a defined peer group; the project has not measured analyst
time saved, prevented losses, funding-cost changes, or downstream business outcomes.

## What the data show

- The latest peer universe contains **{summary['latest_peer_banks']:,} banks** with
  assets from $1bn to under $10bn. **{summary['eligible_banks']:,}** have usable
  prior-year growth and lending ratios.
- Median bank deposit growth is **{summary['median_deposit_yoy']:.2%} YoY**.
  **{summary['contracting_banks']} banks** report contracting deposits, so the
  positive median does not describe every bank.
- The lending threshold is **{summary['loan_to_deposit_threshold']:.2%}**
  (P{summary['threshold_quantile']*100:g}). Combining it with contraction produces
  **{summary['review_banks']} review candidates**, or
  **{summary['review_banks']/summary['eligible_banks']:.1%} of eligible banks**.
- The review queue's combined gross YoY deposit decline is
  **${summary['review_deposit_losses_m']/1000:.3f}bn**. This is a balance change,
  not a forecast of cash outflows or lost revenue.
- Across all contracting peers, gross declines total
  **${summary['gross_deposit_losses_m']/1000:.3f}bn**. The ten largest contributors
  account for **{summary['top10_loss_share']:.2%}** of that total.
- **{summary['outlier_banks']} banks** have unusually weak growth under the
  modified-z rule. This is a separate exploratory flag, not the definition of
  the review queue.

## Largest declines within the review queue

| FDIC cert | Banking entity | State | Deposit growth YoY | Net loans/deposits | Gross deposit decline |
|---:|---|---|---:|---:|---:|
{rows}

These observations represent FDIC certificate-level banking entities rather
than consolidated holding companies.

## An observation that challenges the rule

The first row, **{first.bank_name.strip()} (CERT {int(first.cert)})**, shows
deposit growth of **{first.deposit_yoy:.1%}** and net loans/deposits of
**{first.loan_to_deposit:.1%}**, yet also reports cash/deposits of
**{first.cash_to_deposit:.1%}** and book equity/assets of
**{first.equity_to_assets:.1%}**. Those additional fields make a simple “distress”
label unsupported. Business model and funding structure can affect the
interpretation of these ratios. Cash and book equity are also incomplete
measures of liquidity and capital adequacy.

## Threshold sensitivity

| Lending percentile | Lending ratio cutoff | Review banks | Queue gross deposit declines |
|---|---:|---:|---:|
{sens}

P75 is a documented analytical choice rather than an optimized or regulatory
threshold. The alternative cutoffs show how queue size and represented deposit
declines change as the lending-ratio criterion becomes more selective.

## Evidence and limits

The source contains {summary['source_rows']:,} bank-quarter records over
{summary['quarters']} quarters. API totals reconcile to downloaded records.
Four early quarters cannot have YoY growth within this extract. Peer membership
changes with size, and the historical data reflect revisions known at retrieval,
not the information available at each old reporting date.

Data lineage: source API responses → raw CSV → typed CSV → SQLite financial
view → peer metrics → dashboard CSVs. The source manifest at
`data/raw/{snapshot}/manifest.json` records request URLs, API metadata, and
checksums. `reports/validation.json` records validation results, and
`docs/DATA_DICTIONARY.md` defines the KPIs.

Public source: [FDIC BankFind API](https://api.fdic.gov/banks/docs/).
'''
    (ROOT/"reports/BUSINESS_MEMO.md").write_text(memo)
    print(json.dumps({"tests":f"{count} passed","offline_rebuild_identical":before==after,"tables":tables},indent=2))


if __name__=="__main__":main()
