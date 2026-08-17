# AGENTS.md — Project rules for AI agents working in this repo

## Mandatory: update documentation after every process

**Every time you complete a task, session, round, or any meaningful change to
the project, you MUST update the documentation to track progress.** This is not
optional and is part of "done".

Where to log what:

- **`docs/report_status.md`** — the running ledger for the Power BI report
  (`.pbip`), the semantic model (TMDL), and any report/visual/model change.
  Append a new section (e.g. `§5x. Round N — <summary>`) describing what was
  done, what was verified, and any known caveats. Keep the `▶ RESUME HERE`
  block at the top of the file updated to reflect the new state.
- **`README.md`** — update the Project Status, row counts, table inventories,
  and any "Round N" entries whenever the data layer, model, or pipeline changes.
- **`docs/audit_2026-08-18.md`** — the prioritized (P0–P4) issue list from the
  master audit. When you fix an issue, mark it done or move it to a resolved
  section so the audit stays current.
- **`docs/data_model.md` / `docs/power_bi_setup.md`** — when gold models,
  relationships, or Power BI setup change.

Rules of thumb:

- Keep "done" = code changed + verified (tests/lint/build pass) + **docs updated**.
- Never leave the docs describing a state older than the working tree.
- If a change is too small to deserve a new section, still update the existing
  counts/lists (row counts, table counts, relationship counts) that it touches.
- Check `git status` at the end of a session; the docs should be part of the
  commit with the code.

## Project overview

DOTA 2 data pipeline (portfolio): OpenDota API → raw JSON (`data/`) →
PostgreSQL bronze (jsonb) → dbt silver/gold (`transform/`) → Power BI
(`.pbip`, PBIP/TMDL). Orchestrated by Dagster *and* Airflow via the single
shared runner `scripts/run_pipeline.py`.

See `readme.txt` (original instructions), `README.md`, and `docs/`.

## Working conventions

- **Power BI Desktop must be closed** while editing `.pbip` files, otherwise it
  overwrites the JSON/TMDL on save.
- **Heavy dbt builds may OOM-kill Postgres on this machine — run them with
  `--threads 1`** (`dbt build --profiles-dir . --project-dir transform
  --threads 1`).
- dbt profile is committed at `profiles.yml` (repo root); always invoke with
  `--profiles-dir . --project-dir transform`.
- Postgres runs in Docker (`dota_postgres`, db `dota`, user/pass `postgres`).
  Check it is up with `docker ps` before DB/dbt work.
- `sample_data/` is the committed reproducible dataset (200 matches);
  `data/` is the live scrape (gitignored, 26k+ files — far ahead of bronze).
- Key/ID columns are **text** in silver/gold (Power BI DirectQuery requirement);
  `jsonb` columns are stored as text too. Preserve this convention in new models.
- New gold models need: the SQL model, `schema.yml` tests, the TMDL table file,
  `model.tmdl` + `relationships.tmdl` wiring, and the PBI_QueryOrder/query refs.
- Run checks before finishing: `ruff check .`, `pytest -q`, and for SQL/dbt
  changes a `dbt build` (or at least `dbt compile`) against the running Postgres.

## Key files

- `scripts/run_pipeline.py` — single shared runner (load → dbt → freshness → backup)
- `scripts/load_bronze.py` — JSON → bronze upsert loader
- `data/dota_common.py` — shared scraper/HTTP/rate-limit helpers
- `data/_fetch_matches.py` — main match scraper
- `transform/models/silver/`, `transform/models/gold/` — dbt models
- `.pbip/dota pipeline.Report/` (PBIR) + `.pbip/dota pipeline.SemanticModel/` (TMDL)
- `docs/report_status.md` — the progress ledger; update it every session
- `docs/audit_2026-08-18.md` — prioritized backlog (P0–P4); tick items off as fixed

## Priority reminder

Start work on the `docs/audit_2026-08-18.md` backlog from P0 (critical) down.
Re-read it at the start of each session to know where to continue.
