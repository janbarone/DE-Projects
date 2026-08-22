# History — full session / round log

> The detailed round-by-round changelog, moved here from `README.md` to keep
> that file a quick, human overview. New detailed entries go here (the short
> version lives in `docs/journal.md` → Log).

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
by the model. Full ledger in `git history (branch archive/report-status-history)`.

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
`git history (branch archive/report-status-history)` §5c.

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
Full ledger: `git history (branch archive/report-status-history)` §5d.

**Round 8/9 (2026-08-08, Match Detail polish + savepoint):** Round 8 trimmed
the Match Detail player tables and side-scoped the Radiant/Dire hero slicers;
**Round 9** (see `git history (branch archive/report-status-history)` §5j) made the hero slicers list **only
the heroes in the currently selected match** via a new `Hero in Current Match`
measure on `gold dim_hero` plus a visual-level Advanced filter on both slicers —
**verified working in Power BI Desktop**. No dbt/relationship changes. Full
`pg_dump` taken as the savepoint: `backups/gold4_20260808_191856.dump`. The
report is committed; full ledger in `git history (branch archive/report-status-history)`.

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
was the report landing page; **removed 2026-08-17** (page + builder script
deleted; the MAIN page `0d0feaf1eede4bf5f3bc` is the landing page now).
Verified green at the time: 227/227 gold build steps, 33/33 pytest, 474 field
references resolve. Fresh dump: `backups/gold_20260817_161207.dump` (304.7 MB).

**Round 17/18 (2026-08-17):** the **Grand Report page and its builder**
(`scripts/build_grand_page.py`) were deleted; the new **MAIN** page
(`0d0feaf1eede4bf5f3bc`) is the landing page. **Image columns are now
available in the model** (`dataCategory: ImageUrl`, no visuals wired yet):
`dim_hero.img`, `dim_item.img`, `dim_player.avatar_medium`,
`dim_team.logo_url`, `fact_match_player_skills.ability_img`, and
`fact_match_player_item_purchases.img`. pytest 21/21.

**Round 19 (2026-08-17/18):** **Match detail fixes.** (1) Fixed the tableEx
render crash (`Cannot read properties of undefined (reading 'queryName')`) on
"Dire - skill levelling over time" (`c3c4766012d0ee51351b`) — stray
`"active": false`/`isDefaultSort` entries in its projections removed. (2) **Team
Radiant/Dire tables** (`5f11b68f81ccbfc15225`/`e19afae52e062a202fb0`) showed
*both* teams because they pulled `logo_url` from `dim_team` with no
fact_matches↔dim_team relationship; precomputed `radiant_team_logo` /
`dire_team_logo` columns were added to `gold.fact_matches` (correlated subquery
pattern) and both tables were rewired (4117/4111 logos present). Model stays at
31 tables; lineage tags re-checked unique.

**Round 20 (2026-08-18):** **MAIN draft-sequence table + hero pick/ban lists.**
New gold model **`gold.fact_draft_sequence`** — one row per (match, slot 1–5)
with each team's pick + ban hero (localized name + image URL) and per-slot
sequences (**continuous 1–10 across both teams** in global draft order; 20,490
rows = 4,098 matches × 5, covering every match with draft data; matches with
incomplete drafts leave the missing slots blank; 201 matches have no draft
data at all; image columns `dataCategory: ImageUrl`); new
relationship `fact_draft_sequence.match_id → fact_matches.match_id`. **MAIN**
page gained the **"Match Draft Sequence"** 8-column table (Dire Hero, Pick
Seq, Dire Hero Ban, Ban Seq, Radiant Hero, Radiant Pick Seq, Radiant Hero Ban,
Radiant Ban Seq) scoped to the selected match. **Players page** gained
"Heroes picked/banned by players" and **Teams page** gained "Heroes
picked/banned by teams" — hero icon + name + `Draft Picks`/`Draft Bans`
measures, sorted descending, no top-N limit. Model is now **32 tables, 53
relationships**; pytest 21/21, 184 report JSON files 0 bad.


**Known notes for the next session:**
- Connect Power BI to the **gold** schema (not silver) - it's the presentation
  layer with all relationship fixes. Delete any auto-created relationships on
  import before adding yours.
- **Report is render-verified (2026-08-12).** All pages — including Economy,
  Draft, Match Breakdown, Progression, Match Detail, and the Combat Match ID
  slicer — render in Power BI Desktop. The remaining work is non-report:
  the orchestrator (bronze_load -> dbt build), the matchup matrix, and search
  slicers (see `git history (branch archive/report-status-history)` §8).
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

**Round 21 (2026-08-21, dynamic draft + hardening):** the draft-sequence model
no longer assumes 5 bans/team. `fact_draft_sequence` now derives its slot count
from the data (`max(team_seq)` from `stg_picks_bans`), so the newest matches
with 7 bans/team (14 total) flow through without code changes; dropped the
`slot` `accepted_values` and the `seq_in_range` `> 10` cap (the macro now only
asserts positive integers). Loosened other brittle `accepted_values` lists
(`primary_attr`, damage `target_category`/`source_category`, `score_bucket`) so
future rule changes don't fail tests. Wired `--refresh-constants` /
`--only-constants` into `run_pipeline.py` (+ `_fetch_constants.py --data-dir`)
and added a `refresh_constants` / `constants_refreshed` step to Airflow and
Dagster, so dims stay current when a patch adds heroes/items (keeps
referential-integrity tests green). Swapped the Airflow `dbt_build`
BashOperator for a dbt-cosmos `DbtBuildOperator` (native `dbt build`, single
task).

**Round 22 (2026-08-21, league priority):** the main scraper's phase 1 now
drains leagues in priority order — the explicit The International list first,
then premium, then professional (previously premium → professional only). The
hardcoded `DEFAULT_LEAGUES` was renamed `TI_LEAGUE_IDS` and is now shared with
`_fetch_matches.py`, where `all_league_ids()` prepends it and de-dupes the tier
passes. Motivation: OpenDota labels TIs inconsistently (old ones = professional,
newer = premium), so tier order alone buried TI2012–2017 in the 2,472-league
professional bucket.

**Round 23 (2026-08-21, phase-2 quota efficiency):** the `/proMatches` tail no
longer burns the daily quota on an empty feed. Phase 2 now backs off
exponentially between polls (30s → 60s → … → capped at 10 min), stops at the
`DAY_STOP_AT` safety margin like phase 1 (was running to 0 remaining), and
quits after `MAX_EMPTY_POLLS` consecutive empty polls instead of polling
forever.

**Round 24 (2026-08-21, TI auto-discovery):** The International leagues are now
discovered by name instead of a hand-maintained id list. `discover_ti_league_ids()`
matches `^The International (\d{4})$` against the /leagues data (sorted
chronologically by year), plus a tiny `EXTRA_TI_LEAGUE_IDS` list for the names
the regex misses ("The International 10" = 11625, and the generic 16899
catch-all). This auto-excludes the qualifiers/open-qualifiers/practice/fake
"International" leagues, and new TIs (e.g. 2027+) are picked up with zero manual
changes. `all_league_ids()` and the `_fetch_league_matches.py` helper both use it.

**Round 25 (2026-08-21/22, CI green + launchers):** got GitHub Actions CI
working end-to-end. The lint job was fixed by installing
`sqlfluff-templater-dbt` (sqlfluff 3.x moved the dbt templater out of core),
adding a Postgres service (the templater compiles against a live DB), aligning
keyword capitalisation to `lower` (the models are lowercase), and relaxing the
layout/aliasing/reference style rules to match the existing hand-formatted
models. The dbt-build job was fixed by setting `PGPASSWORD` for the `psql` init
step. All three jobs now pass (lint + pytest + full dbt build on sample_data).
Also consolidated the repo on `main` (deleted the stale `master`, set `main` as
the GitHub default branch) and added `shortcuts/` launchers —
`DOTA_Pipeline_Launcher.bat` (double-click menu) and `dota_pipeline_launcher.py`
— covering the 9 routine operations (incremental, full refresh, scrape,
constants, full pipeline, tests, backup, docker, Power BI). A full
`--full-refresh` rebuild then completed green (54 min, 315 PASS / 0 ERR),
confirming the dynamic draft-slot and loosened-tests changes end to end.

**Round 26 (2026-08-22, OOM root cause fixed):** Postgres was OOM-killed
(signal 9) during silver incremental builds once bronze grew to ~29.5k matches.
Root cause: the incremental `NOT IN (select match_id from <this>)` anti-join
materialized every duplicate match_id (e.g. 1.35M rows for
stg_match_player_damage instead of ~4.3k distinct), exhausting the Docker VM.
Fixed with `select distinct match_id` in all 12 silver incrementals, plus a
`new_matches` CTE that pre-filters to unloaded matches before the JSONB lateral
expansion. Memory dropped from OOM-at-9.7GB to ~1-2 GiB/query, so `--threads 4`
is now safe (~21% memory, ~400% CPU). Also added load_bronze progress
(skip-already-loaded + every-500-files) and run_pipeline step timing.
