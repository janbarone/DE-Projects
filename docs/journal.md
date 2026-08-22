# Project Journal — plain human notes

One file for the whole human story: where we are, how we built it, what we did,
and what we learned. Keep it simple and conversational. Update it every session.

---

## ▶ STATUS — where we are now

> Update these three lines after every task. They must never go stale.

- **Last step:** Built Round 20 — added `gold fact_draft_sequence` (wide
  per-slot draft pivot), the MAIN "Match Draft Sequence" table, and hero
  pick/ban lists on Players/Teams pages. Then fixed `fact_draft_sequence` to
  cover all 4,098 matches with draft data and show the pick/ban order as a
  continuous 1–10 sequence across both teams.
- **Next step:** Open the report in Power BI Desktop and visually verify the
  Round-20 work (expect 32 tables / 53 relationships), then start the non-report
  backlog (matchup matrix via USERELATIONSHIP, player drill-through).
- **Next action items:**
  1. Verify the report in Power BI Desktop (keep Desktop closed while editing files).
  2. Backfill the live DB — the scrape has ~15k match files vs 4,299 loaded; run
     `load_bronze` + `dbt build`.
  3. Publish to GitHub (add `sample_data/`, push, confirm CI passes).
  4. Optional: swap the Airflow `BashOperator` for the dbt-cosmos provider.

---

## The story — how and why we built this

### What this is, in one line

A complete data pipeline that takes Dota 2 match data from the OpenDota API and
turns it into a polished Power BI dashboard — end to end, the way a real data
engineering team would.

### Why I built it / why it matters

I wanted a portfolio project that proves the whole journey: getting raw data,
storing it, cleaning and modeling it, orchestrating it, testing it, and
presenting it. Most projects stop at one step. This one shows I can carry data
from an API all the way to a dashboard a business person could open.

It matters because it mirrors real work: data isn't useful sitting in an API or
a raw dump — it becomes useful when it's reliable, documented, tested, and easy
to explore.

### The end-to-end flow

1. **Ingest** — Python scrapers pull match data from the OpenDota API (throttled
   to respect their rate limits) and save the raw JSON to disk, untouched.
2. **Bronze** — a loader upserts that raw JSON into PostgreSQL as `jsonb`
   (the "don't lose anything" layer).
3. **Silver / Gold** — dbt transforms it into clean, modeled tables
   (fact/dimension star schema) with tests and referential integrity.
4. **Orchestrate** — one shared runner script is wrapped by both Dagster and
   Airflow (I learned both on purpose).
5. **Present** — Power BI reads the gold layer over DirectQuery and shows a
   multi-page report.
6. **Ship safely** — GitHub Actions CI runs lint, tests, and a full dbt build;
   Alembic handles schema migrations; backups are taken on schedule.

### Tools — and why I picked them over the alternatives

- **OpenDota API** — free, rich, real-world Dota 2 data with public docs.
- **PostgreSQL (Docker)** — free, industry-standard, and it's what the dbt +
  Power BI combo expects. (vs SQLite: too toy; vs cloud warehouses: costs money.)
- **dbt** — the standard for transforming data in SQL, with built-in tests and
  docs. (vs hand-written SQL scripts: no tests, no lineage, hard to maintain.)
- **Dagster + Airflow** — the two biggest names in orchestration. I wrapped both
  around one runner to show I understand orchestration, not just one vendor's tool.
- **Power BI (PBIP/TMDL, DirectQuery)** — free, standard in business, and its
  text-based PBIP format is source-controllable. (vs Tableau/Looker: cost, and
  PBIP is more "engineer-friendly".)
- **GitHub Actions + ruff + sqlfluff + pytest** — free, standard CI for Python +
  SQL quality gates.

### Concepts behind it

- **Medallion architecture** (bronze → silver → gold): keep raw, clean it, then model it.
- **ELT vs ETL**: load raw first, transform in the warehouse (dbt).
- **Star schema**: fact tables (events) + dimension tables (heroes, teams, matches).
- **DirectQuery vs import**: DirectQuery keeps the dashboard live against Postgres.
- **Orchestration**: schedule and order the steps, retry on failure.
- **Data quality**: dbt tests, referential integrity, freshness checks, CI.

### What this project proves

That I can take a real, messy, rate-limited public API and deliver a reliable,
tested, orchestrated, documented, and visually presentable data product — and
that I write down what I learned along the way.

---

## Log — what we did

_Append new entries at the bottom (newest at the bottom, like a diary)._
_Format: date — what you did — outcome/result (and any errors → see Lessons)._

> Short version here; the full round-by-round changelog lives in
> `docs/history.md`.

- **2026-08-18 (seeded):** End-to-end pipeline complete and reproducible —
  ingestion, bronze loader, dbt silver/gold (227 passing gold build steps),
  Power BI 6+ page report (PBIP/DirectQuery), Dagster + Airflow orchestration,
  GitHub Actions CI, Alembic migrations. See `README.md` for full status.
- **2026-08-18 (seeded):** Round 20 of the Power BI report shipped
  (`fact_draft_sequence` + MAIN draft-sequence table + pick/ban lists), then
  the draft-sequence fact was fixed to cover all matches with draft data.
  Full detail in `docs/history.md`.
- **2026-08-21:** Made the draft sequence dynamic — `fact_draft_sequence` now
  derives its slot count from the data instead of hardcoding 5, so the new
  7-bans-per-team matches flow through (see Lessons #9). Also loosened brittle
  `accepted_values` tests, wired constants-refresh into the pipeline +
  orchestrators, and swapped the Airflow dbt step to dbt-cosmos.
- **2026-08-21:** League priority revised — the scraper now drains TI leagues
  first, then premium, then professional (see `docs/history.md` Round 22).
- **2026-08-21:** Phase-2 scraping optimized — `/proMatches` polling now backs
  off exponentially, stops at the `DAY_STOP_AT` safety margin, and quits after
  consecutive empty polls instead of burning the daily quota on an empty feed
  (see `docs/history.md` Round 23).
- **2026-08-21:** TI auto-discovery added — The International leagues are now
  found by name (`The International YYYY`) instead of a hand-maintained list, so
  new TIs are picked up automatically (see `docs/history.md` Round 24).
- **2026-08-21/22:** Got CI fully green (lint + pytest + full dbt build) and
  consolidated the repo on `main`. Added `shortcuts/` launchers for the routine
  pipeline operations, then ran a full `--full-refresh` rebuild — green
  (315 PASS / 0 ERR). See `docs/history.md` Round 25.
- **2026-08-22:** Fixed the Postgres OOM crashes during incremental builds —
  root cause was `NOT IN` anti-joins materializing duplicate match_ids; added
  `select distinct` + a pre-filter CTE in all 12 silver models (Lesson #10).
  Also added progress logging to load_bronze and step timing to run_pipeline.
  The full incremental build is now running green on 4 threads.

---

## Lessons — errors, fixes, and "don't repeat this"

Our project memory. Every time we hit an error, write it here: symptom, cause,
fix, and a **don't-repeat** reminder. Read this before starting new work.

### Environment / tooling

**1. Power BI Desktop overwrites hand-edited `.pbip` files**
- **Symptom:** JSON/TMDL changes silently reverted after re-opening the report.
- **Cause:** Power BI Desktop re-saves the PBIP/TMDL on save, overwriting our edits.
- **Fix:** Always close Power BI Desktop before editing `.pbip` files; diff before
  letting Desktop re-save.
- **Don't repeat:** Never edit `.pbip` files while Power BI Desktop is open.

**2. Heavy dbt builds OOM-kill Postgres**
- **Symptom:** Postgres container dies mid `dbt build` on this machine.
- **Cause:** Too many parallel threads → memory exhaustion.
- **Fix:** Run with `--threads 1`.
- **Don't repeat:** Always `dbt build --profiles-dir . --project-dir transform --threads 1`.

**3. Generate PBIR JSON with Python, not PowerShell**
- **Symptom:** PBIR JSON generated via PowerShell produced BOMs / broken files
  (Frown error in the report).
- **Fix:** Generate PBIR JSON with `.py` scripts; verify zero BOMs project-wide.
- **Don't repeat:** Use Python for any JSON/TMDL generation; check for BOMs.

### Power BI / modeling

**4. `jsonb` columns break DirectQuery query folding**
- **Symptom:** DirectQuery visuals error out on `jsonb` columns.
- **Cause:** `jsonb` doesn't fold through DirectQuery.
- **Fix:** Store `jsonb` and key/ID columns as **text** in silver/gold.
- **Don't repeat:** Keep key/ID columns text and never expose raw `jsonb` in the model.

**5. `AVERAGE` on a text column → MdxScript error**
- **Symptom:** Visual reports an MdxScript error.
- **Cause:** A measure/agg was applied to a text column.
- **Fix:** Cast / model the column as the right type, or fix the measure.
- **Don't repeat:** Check column types before writing measures.

**6. Cyclic-reference refresh error**
- **Symptom:** Model refresh fails with a cyclic-reference error.
- **Fix:** Remove the circular relationship/measure dependency (see
  `git history (branch archive/report-status-history)` §5o).
- **Don't repeat:** Trace relationship/measure dependencies before adding new ones.

**7. `USERELATIONSHIP` ambiguous-path error (`PFE_XL_USERELATIONSHIP_AMBIGUOUS_PATH`)**
- **Symptom:** DAX `USERELATIONSHIP` fails with an ambiguous path.
- **Fix:** Resolve via a second, clearly-scoped relationship.
- **Don't repeat:** Verify there's exactly one usable path when using `USERELATIONSHIP`.

**8. Frown error in visuals after JSON edits**
- **Symptom:** A visual shows the "frown" error face.
- **Cause:** Malformed `visual.json` (bad query ref, BOM, missing GUID).
- **Fix:** Note the visual's GUID from its `visual.json`, fix the query ref/JSON,
  and don't let Desktop re-save over hand-edited files without diffing.
- **Don't repeat:** Validate JSON after every edit; diff before re-saving.

**9. Hardcoded draft rule counts (5 bans/team) broke when Dota changed to 7**
- **Symptom:** Newest matches had 14 bans (7 per team); the draft-sequence
  pivot silently dropped ban slots 6–7, and the `slot` / `*_seq` tests failed.
- **Cause:** `generate_series(1, 5)` and `accepted_values [1..5]` / `> 10`
  hardcoded the old rule.
- **Fix:** Derive the slot count from the data (`max(team_seq)`), and loosen the
  pinned tests. See `docs/history.md` (Round 21).
- **Don't repeat:** Never hardcode game-rule counts (picks, bans, slots, phases);
  derive them from the data — rules change across patches.

**10. Incremental `NOT IN` anti-join OOM-killed Postgres (signal 9)**
- **Symptom:** dbt build crashed Postgres mid-silver-load ("server closed the
  connection unexpectedly", then "recovery mode"); Docker logs showed
  "server process terminated by signal 9: Killed" (the Linux OOM killer).
- **Cause:** `where match_id not in (select match_id from <this>)` materialized
  every duplicate match_id (1.35M rows for a table with only ~4.3k distinct
  matches), exhausting the Docker VM's memory.
- **Fix:** `select distinct match_id` in the subquery (1.35M -> 4.3k rows), plus
  pre-filtering new matches into a `new_matches` CTE before the JSONB lateral
  expansion. Memory dropped from OOM-at-9.7GB to ~1-2 GiB.
- **Don't repeat:** anti-joining against a fact table needs `distinct` (or a
  unique dim), and always check the subquery's cardinality — a streaming query
  can still OOM through a bloated subquery.

_Keep adding below as new issues come up._
