# DOTA 2 Data Pipeline

A raw-fetch pipeline for the [OpenDota API](https://docs.opendota.com/) that stores untouched JSON payloads on disk, ready for a later load into a PostgreSQL medallion architecture (bronze / silver / gold) and Power BI.

**Goal:** show the full data flow from source to dashboard (ingestion -> PostgreSQL -> dbt/SQL transforms -> Power BI) as a junior data engineer portfolio project.

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
        |  (roadmap) orchestrator
        v
      Power BI
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
- [ ] 5. Orchestrator (e.g. Apache Airflow) for scheduled runs
- [ ] 6. Power BI dashboard on top of the gold layer

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
# 1. Start the database (Docker Desktop must be running)
docker compose up -d

# 2. (One-time) load raw JSON into bronze
.\.venv\Scripts\python.exe scripts\load_bronze.py

# 3. Run dbt (silver + gold transforms + tests)
.\.venv\Scripts\dbt.exe build --project-dir transform
# Full rebuild of a model if logic/source changed:
.\.venv\Scripts\dbt.exe run --project-dir transform --full-refresh --select stg_matches
# Build only the gold layer:
.\.venv\Scripts\dbt.exe build --project-dir transform --select gold

# 4. View the docs site
.\.venv\Scripts\dbt.exe docs serve --project-dir transform
```

### Future steps (separate PRs / sessions)
- Orchestrator (Airflow/Dagster/Prefect) DAG wiring bronze_load -> dbt build.
- Power BI dashboard on `gold` (relationship mapping ready in `docs/`).
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

**Known notes for the next session:**
- Connect Power BI to the **gold** schema (not silver) - it's the presentation
  layer with all relationship fixes. Delete any auto-created relationships on
  import before adding yours.
- `fact_teamfight_players` keeps the raw per-player maps (`ability_uses`,
  `item_uses`, `killed`, `ability_targets`, `deaths_pos`) alongside the child
  tables - now stored as **text** (jsonb cast to text) to keep DirectQuery
  folding working. Redundant (~36 MB) but harmless at this scale. `deaths_pos`
  is kept for a future death-location heatmap (would need its own child
  table); `ability_targets` is always empty but kept.
- `fact_teamfights` keeps the raw `players` payload as **text** (jsonb cast to
  text) because OpenDota teamfight player entries have no hero/account id (see
  `docs/data_model.md`).
- **Next step:** build out the Power BI dashboard on top of the gold layer
  (measures, visuals, pages). Orchestrator (bronze_load -> dbt build) is the
  remaining pipeline item.
- Backups live in `backups/` (gitignored); newest is
  `gold3_20260802_223003.dump` (194.4 MB, includes all 17 gold tables - i.e.
  **before** `fact_team_matches`; re-back up after the bridge rebuild if
  needed). Restore with `pg_restore -U postgres -d dota backups/<file>.dump`.
- dbt profile is at `~/.dbt/profiles.yml` (not in the repo); project is
  `transform/`.
