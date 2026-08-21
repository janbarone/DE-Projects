# DOTA 2 Data Pipeline

An end-to-end data pipeline that pulls Dota 2 match data from the
[OpenDota API](https://docs.opendota.com/) and turns it into a Power BI
dashboard — the whole way from a raw API response to a dashboard a business
person can open.

**This is a portfolio project.** Most data projects stop at one step; this one
shows the full journey: ingest → store → model → orchestrate → test → present.

## The flow

```
OpenDota API
    │  throttled, quota-aware HTTP (60/min, 3,000/day)
    ▼
raw JSON files (data/)
    │  scripts/load_bronze.py (idempotent upsert)
    ▼
PostgreSQL (Docker, postgres:16)
    │  bronze (raw jsonb) → silver → gold (dbt)
    │
    │  orchestrated by Dagster AND Airflow
    ▼
Power BI report (PBIP / DirectQuery)
```

It's reproducible: `git clone` + `docker compose up` runs the whole thing
against a committed 200-match sample — no API re-scrape needed.

## Tech stack — and why

| Tool | Why I picked it |
|---|---|
| OpenDota API | Free, real Dota 2 data with public docs |
| PostgreSQL (Docker) | Industry-standard, free, and what dbt + Power BI expect |
| dbt | The standard way to transform data in SQL — with built-in tests and docs |
| Dagster + Airflow | The two big orchestrators; both wrap one shared runner |
| Power BI (PBIP, DirectQuery) | Free, standard in business, source-controllable text format |
| GitHub Actions + ruff + sqlfluff + pytest | Free, standard CI for Python + SQL quality |

## Quick start

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt -r requirements-dev.txt

docker compose up -d                                              # Postgres

.\.venv\Scripts\python.exe scripts\load_bronze.py --data-dir sample_data
.\.venv\Scripts\dbt.exe build --profiles-dir . --project-dir transform --threads 1

# one-command version (what the orchestrators run):
.\.venv\Scripts\python.exe scripts\run_pipeline.py --data-dir sample_data
```

Then open `.pbip/dota pipeline.pbip` in Power BI Desktop (with Docker running)
to see the report.

## What's done

- **Ingestion** — throttled, quota-aware, resumable OpenDota scrapers
- **Bronze** — raw `jsonb` + `loaded_at` stamp, idempotent loader
- **Silver / Gold** — dbt: 32 gold models, clean star schema, referential integrity, freshness checks
- **Power BI** — multi-page report on the gold layer (DirectQuery)
- **Orchestration** — Dagster *and* Airflow over one shared runner
- **CI/CD** — lint + pytest + full `dbt build` on every push
- **Reproducibility** — committed 200-match sample + pinned deps + portable `profiles.yml`
- **Migrations** — Alembic for the bronze schema

## What's next

1. Final visual verification of the latest report round in Power BI Desktop.
2. Backfill the live DB (the scrape has ~15k match files vs ~4,300 loaded).
3. Optionally swap Airflow's `BashOperator` for the dbt-cosmos provider.

## Project layout

```
data/            scrapers + raw JSON (live scrape is gitignored)
scripts/         load_bronze.py, run_pipeline.py, make_sample.py
transform/       dbt project (silver + gold models)
orchestration/   Dagster + Airflow definitions
.pbip/           Power BI report + semantic model (PBIP/TMDL)
sample_data/     committed 200-match reproducible dataset
db/              init SQL + Alembic migrations
tests/           pytest
```

## Documentation

- **`docs/journal.md`** — the human story: where we are, how we built it, and lessons learned
- **`docs/history.md`** — the full round-by-round changelog
- **`docs/data_model.md`** — gold schema and relationships
- **`docs/power_bi_setup.md`** — how the Power BI report/model is wired
- **`docs/audit_2026-08-18.md`** — prioritized backlog (P0–P4)
