# Understand the bank deposits project

## A 60-second explanation

“I used public FDIC data to compare deposit changes at banks of a similar size.
I wanted to see which banks had falling deposits alongside relatively high
lending ratios. I downloaded the data with Python, checked it, stored it in
SQLite, and used SQL and Tableau to explore the results. Forty banks met both
conditions in the latest quarter. One interesting example also had a lot of
cash, which showed me why a flag needs more context. The next thing I would
check is whether mergers or differences in business models explain the changes.”

Use this only once you can demonstrate each claim. The Tableau workbook still
needs its native open/render check on your computer before a live interview.

## Read the code in this order

1. **`config.json`** — identify the time range, source fields, charter population,
   asset band and thresholds. Why is the sample fixed rather than silently using
   whatever the latest quarter happens to be?
2. **`src/extract.py`** — explain URL parameters, timeouts, transient retry rules,
   stable pagination, reconciled totals and immutable snapshots. A successful
   HTTP response is not proof that all rows were downloaded.
3. **`src/transform.py`** — explain the primary key, type parsing, null policy and
   why duplicate financial records fail rather than being silently dropped.
4. **`sql/schema.sql`** — draw the foreign keys, state the fact grain, and explain
   why dollars in thousands are integers. Read the exact-quarter self-join aloud.
5. **`src/load.py`** — explain a temporary database and atomic file replacement.
   The old core warehouse survives a failed core rebuild. Downstream exports are
   rebuilt separately; this is not a distributed transaction.
6. **`src/analyze.py`** — calculate one bank's ratios manually. Explain every
   Boolean in `review_flag`, the MAD formula and Pareto denominator.
7. **`sql/business_queries.sql`** — run the CTE/window queries without Python.
8. **`tests/test_pipeline.py`** — demonstrate a missing prior-year quarter, a zero
   denominator and a duplicate key. Explain the behavior each test protects.
9. **`tableau/Bank_Funding_Monitor.twbx`** — open the dashboard and trace one value
   through `tableau/Data` to a processed CSV, SQL view, clean row and raw JSON.

`build_dashboard.py` is packaging and presentation code. Understand what it
produces; the hand-built Tableau XML is not the core analytics claim. In Tableau,
you should also be able to rebuild the two bar charts directly from the CSVs.

## Questions a senior engineer may ask

**Why SQLite rather than a cloud warehouse?**

The current extract has 67,451 rows and one local consumer. SQLite gives me SQL,
composite keys, foreign keys, joins and indexes with a portable artifact and no
credentials. A cloud deployment would add operational complexity without solving
a measured scale problem. I would consider PostgreSQL for shared writes and
access control, and a warehouse for larger analytical workloads.

**Why these tables?**

`dim_bank` owns stable entity identity and latest descriptive attributes.
`dim_period` owns the calendar. `fact_financials` holds one bank-quarter balance
sheet. `fact_peer_signals` records derived observations at the same composite
grain. `pipeline_run` links financial facts to source provenance. The historical
fact also preserves period-reported labels so a latest-name update does not
rewrite historical evidence. That duplication is deliberate and documented.

**Why not `LAG(deposits,4)`?**

Four preceding rows need not mean four preceding calendar quarters if data are
missing. Joining the same certificate on `period_id - 4` enforces the definition.
An unmatched quarter remains null rather than being treated as zero growth.

**What is idempotence here?**

Rebuilding from the same saved snapshot and configuration produces the same
analytical tables and CSVs, without duplicate accumulation. The verification
script compares CSV hashes before and after a second offline build. A fresh API
snapshot may change because the publisher revises history; that is a different
input, not a violation of idempotence.

**How do you know all API data arrived?**

For each quarter, the downloader reads `meta.total`, pages with a stable sort,
checks unique bank-quarter keys, rejects changing totals, and reconciles fetched
rows to the API count. The manifest records request URLs, index metadata, byte
hashes and row counts. This detects truncation and local tampering, but cannot
prove the publisher's underlying records are correct or completely prevent an
upstream same-count change during pagination.

**Why not delete outliers?**

A large balance change may be a real business event, a merger or a correction.
Deleting it can erase the thing an analyst should investigate. I retain it,
separately flag abrupt changes and avoid calling them organic customer flows.

**Why is this data mining? Where is machine learning?**

The project discovers peer segments, unusual growth observations and concentrated
deposit declines. MAD-based outlier detection is an unsupervised method. I chose
an interpretable screen because there are no reliable labeled liquidity-stress
outcomes in this dataset. Adding a classifier would require a defined target,
time-based validation and a plan to prevent leakage.

**Why P75 and a -3.5 modified z-score?**

They are explicit analyst design choices, not regulatory cutoffs or optimized
thresholds. I report sensitivity at P70/P75/P80/P90. The review queue contains
51/40/35/21 banks at those settings in this snapshot. A real team would choose
review capacity and test usefulness prospectively. The outlier flag is separate
from the two-condition review rule, so changing it does not secretly change the queue.

**Why not average all loan-to-deposit ratios?**

An unweighted mean answers a different question. For the aggregate balance-sheet
ratio, I divide the sum of net loans by the sum of deposits over the same valid
records. For the typical bank, I explicitly use the median. For aggregate deposit
growth, I use matched current/prior bank pairs on both sides.

**What biases remain?**

Peers are selected by contemporary size, so membership changes. The pipeline
includes historical banks rather than only today's survivors, but banks that
disappear no longer have observations; I do not convert absence to zero.
Charter type, business model and geography may make an asset-size-only peer
group imperfect. FDIC entities can be subsidiaries. Public records have lags,
revisions and missing economic context.

**How do you know flagged banks are actually stressed?**

I do not. For example, the largest decline in the queue belongs to a Wells Fargo
subsidiary with a large reported cash/deposit ratio. A two-factor flag is a reason
to inspect funding structure, not proof of distress. The next step is corporate
action review, funding-cost and deposit-concentration data, then an analyst's
documented finding. I do not report model accuracy without labels.

**What breaks first at 100 million rows?**

The extractor accumulates rows in memory, the transformations use full DataFrames,
and the workflow rebuilds the entire database. I would stream pages into typed
staging tables or partitioned files, use incremental merges keyed by bank/date,
re-fetch a correction window, and push transformations into the database. I
would benchmark before adopting orchestration or distributed processing.

**What is the security boundary?**

This project uses public aggregate bank financial data, no customer records or
secrets. It needs no API key. HTTP errors do not trigger infinite retries, raw
paths are controlled, and source checksums detect accidental changes. It is a
local portfolio pipeline, not a hardened public service.

**What did AI help with?**

Be candid: AI assisted implementation and documentation. Explain which parts you
reviewed, verified and modified. Do not imply independent authorship of code you
cannot yet explain. The evidence of understanding is a working trace, a correct
SQL query, and your ability to fix an injected bug.

## Four focused practice sessions

| Session | Deliverable you produce yourself | Check that proves understanding |
|---|---|---|
| 1: API + CSV | Fetch one bank/quarter and print selected fields | Explain why 1,000,000 in ASSET means $1bn |
| 2: SQL | Write the YoY self-join without looking | Missing prior quarter remains null |
| 3: Analysis | Recompute one flag and top-10 decline share | Use the right peer set and denominator |
| 4: Tableau + business story | Rebuild the bank-count and before/after bar charts, then present a five-minute review | Explain the 889-bank denominator and why 40 banks warrant further investigation |

## Resume wording after you complete those demonstrations

- Built a Python/SQL banking analytics pipeline using the FDIC API, preserving
  67,451 quarterly records with source checksums, relational constraints and
  repeatable CSV exports.
- Analyzed 890 peer banks using deposit growth, lending ratios, robust outliers
  and concentration analysis; produced a 40-bank review queue and Tableau
  dashboard with documented KPI definitions and threshold sensitivity.

Do not claim increased revenue, prevented losses, production adoption, measured
time savings or predictive accuracy. None has been established by this project.
