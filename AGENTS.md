# AGENTS.md — Project rules for AI agents working in this repo

These rules are **non-negotiable**. "Done" means the code is changed **and** the
docs below are updated. Never leave the docs describing a state older than the
working tree.

---

## The 4 rules (follow every session, every task)

1. **Always log what you do** — append an entry to **`docs/journal.md` → Log**
   (date, what you did, files touched, outcome). If it's not logged, it didn't happen.
2. **Always document implemented / tests / errors / how you fixed them** —
   update **`docs/journal.md` → Lessons** with every error + fix + "don't repeat"
   reminder, and update **`README.md`** (status, counts) when the project state changes.
3. **Always update Last step / Next step / Next action items** — keep the
   **`docs/journal.md` → ▶ STATUS** block current. If you finished the "next
   step", move it to "last step" and pick the new "next step".
4. **Keep the simple human story up to date** — maintain **`docs/journal.md` →
   The story** (how we built it, tools and why, concepts, issues + solutions,
   why it matters, end-to-end flow). Update it when the "why/how" changes.

`docs/journal.md` is the single source of truth for all four. Read it first each
session.

## Where to log what — quick map

| You did / saw… | Update this |
|---|---|
| Any task or session (what happened) | `docs/journal.md` → Log |
| An error / bug and its fix | `docs/journal.md` → Lessons (+ README if status changed) |
| Changed last/next/action state | `docs/journal.md` → ▶ STATUS |
| Implemented a feature / new model / pipeline change | `README.md` + `docs/journal.md` → Log/Story |
| Ran tests / lint / dbt build | `docs/journal.md` → Log (results), README if counts changed |
| Power BI report / TMDL / visual change | `docs/journal.md` → Log (+ `docs/power_bi_setup.md`) |
| Fixed an audit item | `docs/audit_2026-08-18.md` (tick it off) |
| Big-picture "why/how" changed | `docs/journal.md` → The story |

---

## Project overview

DOTA 2 data pipeline (portfolio): OpenDota API → raw JSON (`data/`) →
PostgreSQL bronze (jsonb) → dbt silver/gold (`transform/`) → Power BI
(`.pbip`, PBIR/TMDL, DirectQuery). Orchestrated by Dagster *and* Airflow via the
single shared runner `scripts/run_pipeline.py`.

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
- `docs/journal.md` — **the one human doc** (STATUS + Story + Log + Lessons)
- `docs/audit_2026-08-18.md` — prioritized backlog (P0–P4); tick items off as fixed
- `docs/data_model.md`, `docs/power_bi_setup.md` — technical reference (update only when those change)
- old detailed Power BI ledger — removed; recoverable from git branch `archive/report-status-history`

## Priority reminder

Start work on the `docs/audit_2026-08-18.md` backlog from P0 (critical) down.
Re-read it at the start of each session. At the end of each session, run
`git status` — the docs (journal, README, audit) must be part of the same commit
as the code.
