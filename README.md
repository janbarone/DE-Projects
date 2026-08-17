# DOTA 2 Data Pipeline

A raw-fetch pipeline for the [OpenDota API](https://docs.opendota.com/) that stores untouched JSON payloads on disk, ready for a later load into a PostgreSQL medallion architecture (bronze / silver / gold) and Power BI.

**Goal:** show the full data flow from source to dashboard (ingestion -> PostgreSQL -> dbt/SQL transforms -> Power BI) as a junior data engineer portfolio project.

## Project Status

**Current state: end-to-end pipeline complete and reproducible.** The full flow
(OpenDota API → raw JSON → PostgreSQL medallion → dbt silver/gold → Power BI)
works, is wrapped by two orchestrators, and is covered by CI.

**Achieved:**
- **Ingestion** — throttled, quota-aware, resumable OpenDota scrapers (`data/`).
- **Bronze** — raw `jsonb` payloads + `loaded_at`, idempotent loader (`scripts/load_bronze.py`).
- **Silver/Gold** — dbt (`transform/`) with 32 gold tables (31 in the Power BI
  model), 227 passing gold build steps (194 data tests), referential integrity,
  `dbt source freshness`.
- **Power BI** — functional 6+ page report on the gold layer (PBIP, DirectQuery).
- **Orchestration** — Dagster *and* Airflow wrapping one shared `run_pipeline.py`.
- **Reproducibility** — committed `sample_data/` (200 curated matches + full
  reference files), pinned deps + lockfile, portable `profiles.yml`.
- **CI/CD** — GitHub Actions: ruff + sqlfluff lint, pytest, full `dbt build`.
- **Migrations** — Alembic for the bronze schema (`db/migrations/`).

**Next steps:**
1. `docker compose up` → run the full pipeline against `sample_data/` and
   re-verify the live DB is in sync (the scrape has ~15k match files vs 4,299
   loaded — run `load_bronze` + `dbt build` to backfill).
2. ~~Wire `dbt source freshness` into the scheduled DAG~~ (**done 2026-08-14** —
   the DAG now runs `dbt source freshness` and a `pg_dump` backup after the
   build; config in `sources.yml`).
3. Optionally swap the Airflow `BashOperator` for the dbt-cosmos provider.
4. Publish to GitHub (add `sample_data/`, push, confirm CI passes).

## Architecture

```
OpenDota API (api.opendota.com)
        |
        |  throttled, quota-aware HTTP (60/min, 3000/day)
        v
   Python fetch scripts  -->  raw JSON files (data/)
        |
        |  Python loader (scripts/load_bronze.py)
        v
   PostgreSQL (Docker: postgres:16)
        |
        |  bronze (raw jsonb)  --DONE--
        |  silver (dbt-core)   --DONE--
        |  gold (dbt marts)    --DONE--
        |
        |  orchestrator (Dagster / Airflow)  --DONE--
        v
      Power BI  --DONE--
```

Each fetch script stores **full raw payloads** (no column filtering) plus a `timestamp_fetched` stamp so the bronze layer can be rebuilt or re-loaded later.

## Scripts

All scripts live in `data/`. They are append-only, resumable, and skip anything already downloaded.

| Script | Fetches | Writes to | Frequency |
|---|---|---|---|
| `_pipeline.py` | `/leagues`, `/proPlayers`, `/teams` (all pages), `/heroStats` | `leagues/leagues.json`, `proPlayers/proPlayers.json`, `teams/teams.json`, `heroStats/heroStats.json` | daily |
| `_fetch_constants.py` | `/constants/{resource}` (24 resources) | `constants/*.json` | occasionally |
| `_fetch_matches.py` | league `/leagues/{id}/matchIds` first (drains every configured league), then `/proMatches` | `proMatches/<match_id>.json` | on demand (main scraper) |
| `_fetch_league_matches.py` | `/leagues/{id}/matchIds` (discovery) then `/matches/{id}` | `proMatches/<match_id>.json` | on demand (league-only helper) |

`_fetch_matches.py` is the single main match scraper - it runs in two phases:
first it downloads **every** match for the **premium** leagues, then the
**professional** leagues (all other tiers are disregarded), one league at a time
so each is fully drained; once those two tiers are exhausted it keeps polling
`/proMatches` and downloads new matches until the daily API quota runs out.
Running it with no arguments shows an interactive numbered menu (like the reddit
CLI) to pick the mode: `1 Full`, `2 Leagues`, `3 ProMatches`. For non-interactive
runs use `--mode` (`full` / `leagues` / `promatches`) - `--mode leagues` grinds
leagues exclusively, `--mode promatches` skips league discovery to scrape
proMatches alone. `--leagues` restricts phase 1 to specific ids;
`_fetch_league_matches.py` is the league-only helper (still using
`DEFAULT_LEAGUES`) kept for focused runs.

### Usage

```
python _pipeline.py                          # daily run
python _fetch_constants.py                   # update constants
python _fetch_constants.py --force           # re-fetch everything
python _fetch_matches.py                     # interactive: pick mode, then scrape
python _fetch_matches.py --mode full         # non-interactive: premium+professional leagues, then proMatches
python _fetch_matches.py --mode leagues      # non-interactive: only drain premium+professional leagues (phase 1)
python _fetch_matches.py --mode promatches   # non-interactive: only scrape proMatches (phase 2)
python _fetch_matches.py --limit 5           # stop after 5 matches
python _fetch_matches.py --leagues "600,2733"   # only these leagues, then proMatches
python _fetch_league_matches.py              # league-only run (all default leagues)
python _fetch_league_matches.py --league 600
python _fetch_league_matches.py --limit 10   # capped run
```

## Data layout

```
data/
  leagues/leagues.json           10,024 league rows (leagueid, ticket, banner, tier, name)
  proPlayers/proPlayers.json      5,078 pro player rows (account_id, team_id, name, rank_tier, ...)
  teams/teams.json               21,866 team rows (team_id, name, tag, logo_url, rating, ...)
  heroStats/heroStats.json         127 hero aggregate win/pick/ban rows
  constants/*.json                 24 static resources (heroes, items, abilities, game_mode, region, patch, ...)
  proMatches/<match_id>.json       one full match per file (players, teamfights, chat, objectives, ...)
  dota_common.py                   shared helpers (throttling, quota, file dedup)
  _pipeline_log.txt                daily run log (append-only)
  _league_matches_log.txt          league-match run log (append-only)
```

## Data model / relationships

```
LEAGUES (leagueid)
   |
   +---> MATCH (leagueid)  ........... proMatches/<match_id>.json
              |
              +---> HEROES (hero_id)  .......... constants/heroes.json
              +---> PROPLAYERS (account_id) .... proPlayers/proPlayers.json
              +---> TEAMS (radiant/dire_team_id) teams/teams.json
              +---> ITEMS / ABILITIES ......... constants/items.json, constants/abilities.json
              +---> game_mode / lobby_type / region / patch ... constants/*.json
```

Join keys live inside each match payload: `players[].hero_id`, `players[].account_id`, `radiant_team_id`, `dire_team_id`, `game_mode`, `lobby_type`, `region`, `patch`, `cluster`, and player `item_0..6` / `ability_uses`.

Note: a player's team *within a match* is resolved by `players[].team_number` (0=radiant, 1=dire) plus the match's team ids — `proPlayers.team_id` only reflects the player's *current* team snapshot.

## API rules and safeguards

OpenDota anonymous tier: **60 calls/minute, 3,000 calls/day**. The pipeline respects these in `dota_common.http_get`:

- **Throttling:** ~55 requests/min (`MIN_INTERVAL`), safely under the 60/min limit.
- **429 handling:** honors the `Retry-After` header; falls back to exponential backoff (5s, 10s, 20s, ...) on repeated rate-limits.
- **Transient errors:** retries 5xx and network errors up to `MAX_RETRIES` with backoff.
- **Quota tracking:** reads `X-Rate-Limit-Remaining-Minute` / `X-Rate-Limit-Remaining-Day` on every response; `print_quota()` reports what is left after each run.
- **Auto-stop:** long-running scripts stop early when the daily quota drops to 50 or below.
- **Header requirements:** sends a descriptive `User-Agent`.

## Operational behavior

- **No duplicates / resume:** any target file that already exists is skipped, so interrupted runs (Ctrl+C) can simply be re-run to continue.
- **Failure tolerance:** each item gets up to 2 tries, then is skipped and logged to `_league_matches_log.txt`.
- **Raw-only storage:** data is stored exactly as returned by the API (plus `timestamp_fetched`). No transformation happens at ingestion.

## Roadmap

- [x] 1. Team rosters and player profiles (scoped, resumable) *(partially - see Future steps)*
- [x] 2. PostgreSQL bronze schema + JSONB loader
- [x] 3. Silver transformations with dbt
- [x] 4. Gold marts (fct/dim) for Power BI
- [x] 5. Orchestrators (Dagster **and** Airflow) for scheduled runs
- [x] 6. Power BI dashboard on top of the gold layer
- [x] 7. CI/CD (GitHub Actions: lint + unit tests + full `dbt build` on sample data)
- [x] 8. Reproducible sample dataset (committed `sample_data/`) + pinned dependencies
- [x] 9. Data quality: dbt tests + `dbt source freshness` + Alembic migrations
- [x] 10. dbt source freshness + pg_dump backup in the scheduled DAG (**done
  2026-08-14** — Airflow `dota_medallion_pipeline` runs
  `load_bronze >> dbt_build >> [dbt_source_freshness, pg_dump_backup]`; the
  Dagster job mirrors it via `source_freshness` + `db_backed_up` assets)

## Medallion Plan (Bronze → Silver → Gold)

The overall goal: show the full data flow from source to dashboard
(ingestion -> PostgreSQL medallion -> dbt/SQL transforms -> Power BI) as a
junior data engineer portfolio project, fully reproducible so a reviewer can
`git clone` + `docker compose up`.

```
OpenDota API -> raw JSON (data/) -> PostgreSQL bronze -> dbt silver/gold -> Power BI
```

Decisions agreed (see project history):
- **PostgreSQL** as the single warehouse (Dockerized, `postgres:16`).
- **Bronze**: raw payloads stored as `jsonb`, one row per source record, plus a
  `loaded_at` stamp. No cleaning at ingestion.
- **Loader**: a Python script reads the existing `data/**/*.json` files and
  upserts them into bronze (idempotent, re-runnable). No re-ingest of the API
  for this step.
- **Silver/Gold**: `dbt-core` (with `postgres` adapter) transforms bronze into a
  normalized silver layer and analytical gold marts for Power BI. Versioned SQL
  models, tests, generated docs.
- **Orchestrator**: deferred. For now dbt runs directly; a scheduler
  (Airflow/Dagster/Prefect) is a documented follow-up so bronze_load -> dbt
  build become a thin DAG.
- **Packaging**: everything in `docker-compose.yml` + a git repo so a reviewer
  can replicate the whole stack locally.

### Bronze layer (done)

Raw JSON loaded into PostgreSQL via `scripts/load_bronze.py`. One table per
source, storing the untouched API payload as `jsonb` plus a natural key and
`loaded_at`:

| Table            | Natural key / PK  | Rows (current) |
|------------------|-------------------|----------------|
| `bronze.matches` | `match_id bigint` | 4,299          |
| `bronze.leagues` | `leagueid int`    | 10,036         |
| `bronze.players` | `account_id int`  | 5,093          |
| `bronze.teams`   | `team_id int`     | 21,884         |
| `bronze.hero_stats` | `id int`       | 127            |
| `bronze.constants`  | `resource text` | 24            |

### Silver layer (done)

Built with `dbt-core` (`transform/` project, dbt-postgres adapter).

- **Views** (small, stable lookups): `stg_leagues`, `stg_teams`, `stg_players`,
  `stg_heroes`, `stg_hero_stats`, `stg_constants` (all 24 static resources)
- **Incremental tables** (granular, growing facts): `stg_matches`,
  `stg_match_players` (per match + player), `stg_picks_bans` (per match +
  draft order), `stg_teamfights` (per match + teamfight, raw players jsonb)

Verified row counts:

| Model | Rows |
|-------|------|
| `silver.stg_matches` | 4,299 |
| `silver.stg_match_players` | 42,755 |
| `silver.stg_picks_bans` | 88,804 |
| `silver.stg_teamfights` | 16,944 |
| `silver.stg_leagues` | 10,036 |
| `silver.stg_teams` | 21,884 |
| `silver.stg_players` | 5,093 |
| `silver.stg_heroes` | 127 |
| `silver.stg_hero_stats` | 127 |
| `silver.stg_constants` | 24 |

Materialization strategy: **views** for small/stable dims, **incremental
tables** for granular/growing facts. New data appends on each `dbt run`;
`dbt run --full-refresh` is the repair tool (only when logic/source changed).
Nulls in source (e.g. missing team ids) are preserved with `has_*_team`
presence flags. Indexes on join keys of the four large tables.
21 data tests pass. See `docs/data_model.md` for the full mapping.

### Gold layer (done)

Analytical marts for Power BI - a clean **star schema** in the `gold` schema,
built from silver by dbt. Every Power BI relationship pitfall found in silver
is fixed here:

- `dim_hero` adds an **Unknown hero (`hero_id = 0`)** so OpenDota's `hero_id = 0`
  placeholder joins cleanly; hero stats are merged into the hero dimension.
- `dim_player` covers **all match participants** (pro players + non-pros), so
  every `account_id` resolves.
- `dim_team` adds **Unknown teams** for ids that appear only in matches.
- `stg_constants` is **flattened** into real decode dimensions:
  `dim_game_mode`, `dim_lobby_type`, `dim_region`.
- `dim_team` connects through a **team-side bridge** `fact_team_matches`
  (one row per match + side) instead of two links to `fact_matches` - so a
  team's radiant and dire matches are both queryable with one active
  relationship (no `USERELATIONSHIP`, no inactive relationships).
- `dim_date` is a full calendar dimension (day / week / month / quarter / year
  attributes) joined via `fact_matches.start_date`.
- `dim_hero_role` is a bridge table so heroes can be filtered by role.
- `fact_teamfight_players` breaks teamfights down to hero level (the raw
  `players` jsonb is positionally ordered by slot, so hero/player resolve).
- Facts carry derived helpers (`duration_min`, `start_min`, etc.) for readable
  time values.
- All facts link cleanly to matches; joins are enforced by dbt relationship
  tests (referential integrity), so Power BI never hits validation errors.

| Model | Rows | Grain | PK |
|-------|------|-------|----|
| `gold.dim_hero`        | 128    | one row per hero (+ Unknown)      | `hero_id` |
| `gold.dim_hero_role`   | 491    | one row per (hero, role) bridge   | `(hero_id, role)` |
| `gold.dim_player`      | 5,945  | one row per player (pro + participants) | `account_id` |
| `gold.dim_team`        | 21,888 | one row per team (+ Unknown)      | `team_id` |
| `gold.dim_league`      | 10,036 | one row per league                | `leagueid` |
| `gold.dim_game_mode`   | 26     | one row per game mode code        | `game_mode_id` |
| `gold.dim_lobby_type`  | 16     | one row per lobby type code       | `lobby_type_id` |
| `gold.dim_region`      | 22     | one row per region code           | `region_id` |
| `gold.dim_date`        | 18,628 | one row per day (2000-01-01 -> 2050-12-31) | `date` |
| `gold.fact_matches`        | 4,299  | one row per match                 | `match_id` |
| `gold.fact_team_matches`   | 8,492  | one row per (match, side) bridge  | `(match_id, side)` |
| `gold.fact_match_players`  | 42,755 | one row per (match, player)       | `(match_id, player_slot)` |
| `gold.fact_picks_bans`     | 88,804 | one row per (match, draft order)  | `(match_id, order_no)` |
| `gold.fact_teamfights`     | 16,944 | one row per (match, teamfight)    | `(match_id, teamfight_id)` |
| `gold.fact_teamfight_players` | 169,440 | one row per (match, teamfight, player) | `(match_id, teamfight_id, player_slot)` |
| `gold.fact_teamfight_ability_uses` | 483,509 | one row per (match, teamfight, player, ability) | `(match_id, teamfight_id, player_slot, ability_name)` |
| `gold.fact_teamfight_item_uses` | 402,934 | one row per (match, teamfight, player, item) | `(match_id, teamfight_id, player_slot, item_name)` |
| `gold.fact_teamfight_kills` | 68,305 | one row per (match, teamfight, killer, victim hero) | `(match_id, teamfight_id, player_slot, victim_hero_id)` |

Materialization: **tables** for dims and facts (Power BI imports these directly).
The full relationship mapping for Power BI (cardinality + cross-filter) is in
`docs/data_model.md` and `docs/power_bi_setup.md`.

### How to run

```powershell
# 0. Create a virtualenv and install pinned deps (Python 3.12+ recommended)
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt        # runtime
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt    # dev/CI (tests, lint, alembic)

# 1. Start the database (Docker Desktop must be running)
docker compose up -d

# 2. (One-time) load raw JSON into bronze
.\.venv\Scripts\python.exe scripts\load_bronze.py --data-dir sample_data   # committed demo set
# ...or the live scrape:  scripts\load_bronze.py --data-dir data

# 3. Run dbt (silver + gold transforms + tests). --profiles-dir . points at
#    the committed profiles.yml (repo root).
.\.venv\Scripts\dbt.exe build --profiles-dir . --project-dir transform
# Full rebuild of a model if logic/source changed:
.\.venv\Scripts\dbt.exe run --profiles-dir . --project-dir transform --full-refresh --select stg_matches
# Build only the gold layer:
.\.venv\Scripts\dbt.exe build --profiles-dir . --project-dir transform --select gold

# 4. Source freshness check (warns if bronze.matches is stale)
.\.venv\Scripts\dbt.exe source freshness --profiles-dir . --project-dir transform

# 5. View the docs site
.\.venv\Scripts\dbt.exe docs serve --profiles-dir . --project-dir transform
```

**One-command pipeline** (used by the orchestrators):

```powershell
.\.venv\Scripts\python.exe scripts\run_pipeline.py --data-dir sample_data
```

### Reproducibility (sample dataset)

The full scrape (`data/`) is ~5.5 GB and gitignored. For a reviewer to run the
whole stack without re-scraping the API, a curated **~200 match** sample plus the
**complete reference files** (leagues/teams/proPlayers/heroStats/constants) is
committed under `sample_data/` (~106 MB).

- Curated by `scripts/make_sample.py` to cover every report page: both win
  sides + draws, per-minute `gold_t`/`xp_t`, ability upgrades (talents),
  item purchases, wards, runes, damage types, teamfights, picks/bans, missing
  team ids, and `hero_id = 0` placeholders — spread across ~20 leagues and
  15 patches.
- Regenerate with `python scripts/make_sample.py --matches 200` (reads the live
  `data/` scrape, writes `sample_data/`).
- The `sample_data/MANIFEST.json` records the selection + coverage report.

### Orchestration (Dagster and Airflow)

Both orchestrators wrap the **same** `scripts/run_pipeline.py` (no duplicated
logic) and run **one at a time** via docker-compose profiles:

```powershell
docker compose --profile dagster up -d    # UI at http://localhost:3000
docker compose --profile airflow up -d    # UI at http://localhost:8080 (admin/admin)
```

- Dagster: `orchestration/dagster/definitions.py` — two assets
  (`bronze_loaded` -> `dbt_built`) + a daily schedule.
- Airflow: `orchestration/airflow/dags/dota_pipeline_dag.py` — two
  `BashOperator` tasks (`load_bronze` >> `dbt_build`) on a daily schedule.
- Local (no containers): `python -m dagster dev -m definitions` from
  `orchestration/dagster/`, or drop the DAG into a running Airflow's `dags/`.

### CI/CD

`.github/workflows/ci.yml` runs on every push/PR:

1. **lint** — `ruff check .` + `sqlfluff lint transform/models`.
2. **unit-test** — `pytest` (tests/).
3. **dbt-build** — spins up a Postgres service, loads `sample_data/` into
   bronze, runs `dbt build` (all silver/gold + tests), then `dbt source freshness`.

### Bronze schema migrations (Alembic)

`db/init/*.sql` still bootstraps the schema on a fresh Docker volume. For
versioned schema changes on an existing database, use Alembic:

```powershell
.\.venv\Scripts\alembic -c db\alembic.ini upgrade head    # apply migrations
.\.venv\Scripts\alembic -c db\alembic.ini downgrade -1     # roll back one
.\.venv\Scripts\alembic -c db\alembic.ini revision --autogenerate -m "..."  # new migration
```

### Logging

Pipeline-critical Python (`load_bronze.py`, `run_pipeline.py`) logs structured
**JSON** to stderr via `data/dota_common.py::configure_logging`. The interactive
scrapers keep human-readable console output (appropriate for CLI tools).

### Future steps (separate PRs / sessions)
- Wire `dbt source freshness` into the scheduled DAG (config already in `sources.yml`).
- Optionally switch the Airflow DAG to the dbt-cosmos provider for a first-class
  dbt integration (currently BashOperator calls `run_pipeline.py`).
- Optional: PySpark if the dataset grows large (time-series: chat, kills_log,
  gold_t, xp_t).

## Session checkpoint

**Last session ended:** Bronze + silver + **gold** layers complete and verified
(135/135 dbt tests pass, zero orphaned join keys across all gold facts).
Gold = 18 tables (9 dims + 9 facts), including three child facts that flatten
the nested teamfight maps from `fact_teamfight_players`:

- `fact_teamfight_ability_uses` (483,509 rows) - one row per (match, teamfight, player, ability)
- `fact_teamfight_item_uses` (402,934 rows) - one row per (match, teamfight, player, item)
- `fact_teamfight_kills` (68,305 rows) - one row per (match, teamfight, killer, victim hero)

**Where to resume:** Power BI dashboard on `gold` - connect to
`localhost:5432` (db `dota`, user `postgres`), load the 18 `gold.*` tables and
create the **27 relationships** in Model view per `docs/power_bi_setup.md`.
Then optionally wire the orchestrator (bronze_load -> dbt build).

**Status update (2026-08-03):** all 27 relationships are now created and
validating in Power BI. The blocker was an import type mismatch - key/ID
columns imported with inconsistent numeric types, so Power BI rejected them.
Fix (confirmed working): set all key columns to **Text** in Power Query
(`match_id`, `teamfight_id`, `player_slot`, `hero_id`, `victim_hero_id`,
`account_id`, `team_id`, `leagueid`, `game_mode_id`, `lobby_type_id`,
`region_id`, `radiant_team_id`, `dire_team_id`), keep measures numeric and
dates as dates. Full details in `docs/power_bi_setup.md` §5.

**Status update (2026-08-04):** the type fix is now applied **at the schema
level** instead of in Power Query. Every silver/gold key/ID column above is
`text` natively in PostgreSQL (measures stay numeric, dates stay dates), so a
fresh import just works - no Power Query type conversion needed. Rebuilt with
`dbt build --full-refresh`. Full details in `docs/data_model.md` and
`docs/power_bi_setup.md` §5.

**Status update (2026-08-04, Power BI live):** the Power BI report now runs
against the gold layer. All **27 relationships** connect, cross-filtering
works, and the last blocker was fixed: DirectQuery failed with error 10682
("Local evaluation of Table.Join or Table.NestedJoin ... is not supported")
whenever a visual included a **jsonb** column (root cause: jsonb breaks query
folding in DirectQuery). Fix applied **at the source, at the silver stage**:
every jsonb column is now `text` natively (`->>` extraction instead of `->`),
gold inherits text, and downstream SQL parses back with `::jsonb` where
needed. Verified: **zero jsonb columns left in `gold`**, 100/100 dbt tests
pass, row counts unchanged. Converted columns: `stg_teamfights.players`,
`stg_heroes.roles`, `fact_teamfight_players.{ability_uses, item_uses,
ability_targets, killed, deaths_pos}` (+ their gold pass-throughs). Full
details in `docs/power_bi_setup.md` §8. Note: the model-side
`Table.RemoveColumns` exclusion of `fact_teamfights.players` from earlier is
no longer strictly needed (the column is text now) but is harmless to keep.

**Status update (2026-08-05):** added `gold.fact_team_matches`, a **team-side
bridge fact** (8,492 rows = one row per match + side), so `dim_team` now
connects through a single active path. The old dual `radiant_team_id` /
`dire_team_id` links to `dim_team` (one inactive + `USERELATIONSHIP`) are gone -
both sides of a match are queryable at once, split by the `side` column
('Radiant' / 'Dire'). Power BI relationships are still **27**: the two team
links on `fact_matches` were replaced by `fact_matches.match_id ->
fact_team_matches.match_id` (1:Many) + `fact_team_matches.team_id ->
dim_team.team_id` (Many:1). Gold = **18 tables** (9 dims + 9 facts). 135/135
dbt tests pass. Full details in `docs/data_model.md` and
`docs/power_bi_setup.md` §4.

**Status update (2026-08-05, +dataset):** added `team_win` to
`fact_match_players` (silver + gold) - the player's team won, derived from the
match's `radiant_win` and the player's `team_number` (null only for the 2 draw
matches). This makes hero/player **win rate computable from the matches
themselves** (HeroWins / HeroPicks DAX), instead of the static
`dim_hero[pub_win_rate]` column that ignored all slicers. Power BI: set cross
filter = **Both** on `fact_matches ↔ fact_match_players` and
`fact_matches ↔ fact_team_matches` so hero/player/team slicers reach the hub and
filter the whole report. Row counts unchanged (42,755).

**Status update (2026-08-05, +completeness):** verified every match in the DB
against OpenDota's `/leagues/{id}/matchIds` for all 16 configured leagues - the
13 The Internationals (2012-2025) match the API exactly (TI2024 has 1 match,
`7928919925`, that the API lists but 404s on fetch). 67 matches scraped via
`/proMatches` after the last load were backfilled: re-ran `load_bronze.py`
(idempotent) + `dbt build`. Bronze now holds all 4,299 downloaded files
(4,128 TI + 171 proMatches-scraped 2026 matches across leagues 19917, 20009,
20026, 20030, 19944). All row counts in this README updated to reflect it.

**Status update (2026-08-05, report done):** the Power BI report is now
functional on all 6 pages. This session fixed: (1) two broken stacked bars
switched to `barChart`; (2) a visual-level blank-player-name filter on the
top-picks bar; (3) the **tableEx table crash** — `Cannot read properties of
undefined (reading 'queryName')` in the new table visual — caused by stray
`"active": false` / `"isDefaultSort"` artifacts in the 4 `tableEx` visual files,
normalized to Power BI's own serialization; (4) the **Role slicer** doing nothing
on Hero Meta — fixed by setting `crossFilteringBehavior: bothDirections` on
`dim_hero_role ↔ dim_hero`. The leaderboards deliberately use **measures** (not
precomputed columns) because columns ignore the Year/League slicers. Gold dims
were extended with precomputed `match_*` columns but they are **not imported**
by the model. Full ledger in `docs/report_status.md`.

**Feature pass (2026-08-05, same day):** added the data foundations for the next
set of report features — `dim_patch` (real patch versions + a Patch slicer on the
Matches page, patch chart now decoded/sorted), `fact_hero_matchups` (hero-vs-hero,
106,721 rows), `fact_team_h2h` (team head-to-head, 4,220 rows), plus draft
measures (`Pick Rate` / `Ban Rate`). Team/Player leaderboards now exclude
"Unknown" teams / null player names. New tables + 7 relationships are wired into
the semantic model (TMDL). Full spec: `docs/report_improvements.md`.

**Round 2 (2026-08-05):** shipped **two new pages** — **Economy** (7 stat cards,
farm/last-hit leaders, support impact, first-items table via new `dim_item`,
lobby-type donut, GPM/XPM trend) and **Draft** (top picks/bans, picks-vs-bans,
picks by phase, side tendencies, hero matchups + team H2H tables) — plus 3
Combat visuals (fight damage/healing, fight phases, buybacks) and 4 Overview
visuals (match-closeness donut, early-FB rate, leaver games, score differential).
Data layer: `dim_item` (596 rows, decodes `item_0..6`), `score_bucket`,
`fight_phase`, `matchup_label` columns, ~20 new measures, +1 relationship (35
total). 133/133 dbt tests; 90/90 report JSON files parse. Full ledger:
`docs/report_status.md` §5c.

**Round 3 (2026-08-05, validation + About page):** fixed the load errors the
new pages surfaced in Desktop — (1) stripped UTF-8 BOMs from the 7 Economy
visual.json files (Power BI requires BOM-less UTF-8), (2) renamed the new
`Avg Score Differential` measure to `Avg Score Differential (match)` (name
collided with an existing `fact_team_matches` measure), (3) rewrote that
measure with `AVERAGEX(...)` because `AVERAGE(ABS(...))` isn't pushed by
DirectQuery. Added a **new About & Glossary page** (`736e1272`, 1280×1000):
11 textboxes covering what the report does, a Dota-term glossary, and a
per-page description of every visual. **Gotcha:** textbox visuals must live in
`visuals/<guid>/visual.json` folders — a flat `visuals/<guid>.json` file is
silently ignored (page appears empty). 102/102 report JSON files parse, 0 BOMs.
Full ledger: `docs/report_status.md` §5d.

**Round 8/9 (2026-08-08, Match Detail polish + savepoint):** Round 8 trimmed
the Match Detail player tables and side-scoped the Radiant/Dire hero slicers;
**Round 9** (see `docs/report_status.md` §5j) made the hero slicers list **only
the heroes in the currently selected match** via a new `Hero in Current Match`
measure on `gold dim_hero` plus a visual-level Advanced filter on both slicers —
**verified working in Power BI Desktop**. No dbt/relationship changes. Full
`pg_dump` taken as the savepoint: `backups/gold4_20260808_191856.dump`. The
report is committed; full ledger in `docs/report_status.md`.

**Round 10 (2026-08-08, Match Breakdown page, §5k):** new dedicated page with
per-match hero-kill counts (split Radiant/Dire), rune pickups by hero (incl.
bounty, via `dim_rune`), support contribution (wards placed / dewards), and
damage dealt/taken breakdowns (split Radiant/Dire with target/source-category
slicers + building/hero KPI cards). New gold facts: `fact_match_player_kills`,
`fact_match_player_runes`, `fact_match_player_damage`,
`fact_match_player_damage_taken`; `fact_match_players` gains 6 support columns
(wards derived from `obs_log`/`sen_log`); `dim_player` now resolves participant
names from `personaname`. Model is now **35 tables, 83 relationships**. dbt
build + tests pass; 145 JSON files parse clean. Needs its first Desktop render
pass.

**Round 11 (2026-08-08, Match Detail player-table stat columns, §5l):** both
Match Detail player tables (Radiant/Dire) extended with 18 columns: GPM, XPM,
damage to heroes/buildings, damage received by type (physical/magical/pure via
new `fact_match_player_damage_taken_type`), last hits, denies, heal, pick
sequence, enemy-heroes-killed, support gold, and ward/sentry/dust/smoke/gem
purchase counts — all denormalized on `fact_match_players`. Model is now **36
tables, 71 relationships**. dbt build + 29 tests pass; 146 JSON files parse
clean.

**Round 11b (2026-08-08, pick sequence + ban data, §5m):** `pick_sequence` fixed
to rank among picks only (**1-10**, was the raw 1-20 draft order). Added
`ban_sequence` (rank among bans) to `fact_match_players`. Fixed a data bug in
`stg_picks_bans` — the draft `team` side was never captured (now exposed as
`team_number`/`active_team`). Match Detail player tables renamed to **'Radiant -
Match Details'** / **'Dire - Match Details'**; Draft page gained a **'Ban
frequency by hero'** table (ban count / ban rate / avg ban position).

**Round 11c (2026-08-08, talents in skill tables, §5n):** `fact_match_player_skills`
gains an **`is_talent`** flag and **cleaned talent labels** (the unresolved
`+{s:…}` value templates are stripped, e.g. `+{s:bonus_illusion_duration}s
Reflection Duration` → `Reflection Duration`; `attribute_bonus` →
`Attribute Bonus`). Both skill-levelling tables on Match Detail now show the
**is_talent** column. ~3% of talents still show raw `special_bonus_unique_*`
keys (no `dname` in the source constants).

**Round 11d (2026-08-08, cyclic-refresh fix, §5o):** data refresh reported a
"cyclic reference during evaluation" across `dim_hero_role` / `fact_matches` /
`fact_teamfight_kills` / `dim_hero`. Removed the unused
`fact_match_player_damage_taken_type` table from the Power BI model (visuals
use the denormalized `fact_match_players.damage_taken_*` columns instead) and
removed the unused `Ban Sequence` RANKX measure on `fact_picks_bans`. Model is
now **35 tables, 68 relationships** (3 bidirectional). The silver
`stg_match_player_damage_taken_type` stage still feeds `fact_match_players`.

**Round 12 (2026-08-08, Progression page, §5p):** new **Progression** page with
per-minute line charts (X = minute) driven by a shared minute slicer + match
dropdown: **Team XP & Net Worth** (new `fact_match_team_minute`), **Player Net
Worth** and **Player Level** (`fact_match_player_minute`), **Player Item
Purchases** (`fact_match_player_item_purchases`). Added the missing
`fact_match_player_minute.minute → dim_match_minute` relationship. Player
damage was skipped (no per-minute damage in OpenDota). Model is now **36 tables,
71 relationships**.

**Round 13 (2026-08-09, normalization + page enhancements, §5q):** dimensions
normalized (league/team uppercase; game-mode/lobby prefix-stripped+uppercase;
`primary_attr` friendly labels Agility/Universal/Intelligence/Strength;
`player_type` → Pro / Match Participant; `fact_team_h2h` denormalized team
names). Hero Meta: + Patch slicer, hero win/ban rate per patch charts (top-20 /
top-15). Players: + appearances by league. Teams: + League slicer, win-rate-by-
league table (by side). Matches/Economy: duration & GPM/XPM trends now **by
patch**. Draft: fixed `Avg Ban Position` (VALUE cast), + Dire Hero Win Rate
column, + hero win-rate-by-side table, reworked Team-vs-Team head-to-head with
W–L records.

**Round 13b (2026-08-09, folding fixes, §5q):** fixed DirectQuery
query-folding errors on the Draft page — `Dire Hero Win Rate` is now a
self-contained `DIVIDE` (was `1 - [Radiant Hero Win Rate]`, which wouldn't
fold), and a new **precomputed `fact_hero_side`** table powers the **split
"Hero win rate – Radiant" / "Hero win rate – Dire"** tables (cross-table
`COUNTROWS` grouping doesn't fold).

**Round 13c (2026-08-09, §5q):** fixed the remaining Draft folding errors —
added numeric `order_no_int` to `fact_picks_bans` (so `Avg Ban Position` is a
foldable `AVERAGE`, not an `AVERAGEX(VALUE())` iterator), and added a
**precomputed `fact_hero_matchup_stats`** table (per-matchup games + radiant /
dire win rates) for the "Most common hero matchups" table. Model is now **38
tables, 72 relationships**.

**Round 14 (2026-08-12, §5r):** **Combat page gained a Match ID slicer**
(`6e9cce4f`, dropdown on `gold fact_matches.match_id`, x=650 — filters the
combat facts via the existing `fact_teamfights` / `fact_teamfight_players` →
`fact_matches` links). No dbt/model changes. Fresh `pg_dump` taken as the
savepoint: `backups/gold5_20260812_162008.dump` (337 MB, rounds 4–14). The
report renders correctly in Power BI Desktop across all pages.

**Round 15 (2026-08-14, §5s):** **Hero Meta page gained the matchup visual** —
a searchable Hero dropdown slicer drives a **Top opponents** table
(`opponent_name` + `Hero Matchup Games` + `Hero Matchup Win Rate` from
`fact_hero_matchups_hero`, which gained `hero_name`/`opponent_name` display
columns; page height 1000 → 1280). **Search enabled on all high-cardinality
slicers** (`selfFilterEnabled = true`). **Orchestrator hardening**: the DAG
now runs `dbt source freshness` + a `pg_dump` backup after the build. Fresh
dump: `backups/gold_20260814_025223.dump` (337 MB).

**Round 16 (2026-08-16/17, §5t):** **database optimization + Grand Report
page.** Pruned **7 unused gold tables** from the model (and dropped them from
dbt + the DB, plus the stale `gold.fact_team_h2h_new` experiment table):
`fact_match_player_kills`, `fact_match_timeline`, `fact_match_timeline_events`,
`fact_team_compositions`, `fact_teamfight_item_uses`, `fact_teamfight_kills`,
`dim_match_minute` (`fact_match_player_damage_taken_type` was already out of
the model since Round 11d). Model is now **31 tables, 52 relationships (3
bidirectional)**; dbt builds 32 gold models. Index hardening (fixed the
double-schema-prefix bug, added `match_id`/`patch`/`start_date` indexes on
`fact_matches`, removed leftover silver index hooks) + `on-run-end: analyze`.
**New Grand Report page** (144 visuals, built by `scripts/build_grand_page.py`)
is the report landing page; verified green: 227/227 gold build steps, 33/33
pytest, 474 field references resolve. Fresh dump:
`backups/gold_20260817_161207.dump` (304.7 MB).

**Known notes for the next session:**
- Connect Power BI to the **gold** schema (not silver) - it's the presentation
  layer with all relationship fixes. Delete any auto-created relationships on
  import before adding yours.
- **Report is render-verified (2026-08-12).** All pages — including Economy,
  Draft, Match Breakdown, Progression, Match Detail, and the Combat Match ID
  slicer — render in Power BI Desktop. The remaining work is non-report:
  the orchestrator (bronze_load -> dbt build), the matchup matrix, and search
  slicers (see `docs/report_status.md` §8).
- **PBIP gotchas (all hit + fixed):** (1) files must be **UTF-8
  without BOM**; (2) measure names are unique model-wide (rename before
  colliding); (3) avoid non-column aggregates like `AVERAGE(ABS(...))` in
  DirectQuery — use `AVERAGEX`/`SUMX`; (4) every visual, including textboxes,
  must live in `visuals/<guid>/visual.json` folders.
- `fact_teamfight_players` keeps the raw per-player maps (`ability_uses`,
  `item_uses`, `killed`, `ability_targets`, `deaths_pos`) alongside the child
  tables - now stored as **text** (jsonb cast to text) to keep DirectQuery
  folding working. Redundant (~36 MB) but harmless at this scale. `deaths_pos`
  is kept for a future death-location heatmap (would need its own child
  table); `ability_targets` is always empty but kept.
- `fact_teamfights` keeps the raw `players` payload as **text** (jsonb cast to
  text) because OpenDota teamfight player entries have no hero/account id (see
  `docs/data_model.md`).
- **Backups live in `backups/` (gitignored); newest is**
  `gold_20260817_161207.dump` (304.7 MB, taken 2026-08-17 at the Round 16
  savepoint via `scripts/run_pipeline.py --only-backup --backup-docker` —
  includes all gold tables). Older dumps: `gold_20260814_025223.dump`
  (Round 15), `gold5_20260812_162008.dump` (rounds 4–14),
  `gold4_20260808_191856.dump` (290 MB, rounds 4–9) and
  `gold3_20260802_223003.dump` (194.4 MB, predates `fact_team_matches`,
  `dim_patch`, `fact_hero_matchups`, `fact_team_h2h`, `dim_item` and all
  per-minute facts). Restore with `pg_restore -U postgres -d dota backups/<file>.dump`.
- dbt profile is now **committed** at `profiles.yml` (repo root), overridden via
  env vars; invoke dbt with `--profiles-dir .`. The dbt project is `transform/`.

**Status update (2026-08-13, engineering hardening):** this session focused on
closing the gaps between a "script collection" and a production pipeline:

- **Reproducibility** — removed the hardcoded absolute path from
  `data/dota_common.py` (now derived from `__file__`); pinned `requirements.txt`
  + added `requirements-dev.txt` and `requirements.lock`; committed a portable
  `profiles.yml`; added `scripts/make_sample.py` and generated a curated
  **200-match sample dataset** under `sample_data/` (~106 MB, full reference
  files included) so `git clone` + `docker compose up` runs end-to-end.
- **Orchestration** — added a shared `scripts/run_pipeline.py` entrypoint and
  **two** orchestrators: Dagster (`orchestration/dagster/`) and Airflow
  (`orchestration/airflow/`), selectable via docker-compose profiles.
- **CI/CD** — `.github/workflows/ci.yml` (ruff + sqlfluff lint, pytest,
  full `dbt build` against sample data on a Postgres service), plus `ruff.toml`
  and `.sqlfluff` configs.
- **Data quality** — added `dbt source freshness` on `bronze.matches`
  (`transform/models/sources.yml`) and Alembic migrations for the bronze schema
  (`db/migrations/`).
- **Logging** — structured JSON logging for `load_bronze.py` / `run_pipeline.py`
  via `data/dota_common.py::configure_logging`.
- 13 pytest unit tests added (throttle/retry/backoff + loader upsert logic).
