# Dota 2 Data Model - Silver Layer

Complete reference for the `silver` schema of the Dota 2 medallion architecture.
All models read from raw `bronze.*` JSONB and are built by dbt (`transform/`).
This document is verified against the live database schema (`\d silver.*`).

## Quick reference

| Model | Materialized | Grain | PK / unique key | Rows |
|-------|--------------|-------|-----------------|------|
| `stg_matches`       | table (incremental) | one row per match          | `match_id`                | 4,232  |
| `stg_match_players` | table (incremental) | one row per (match, player)| `(match_id, player_slot)` | 42,085 |
| `stg_picks_bans`    | table (incremental) | one row per (match, order) | `(match_id, order_no)`    | 87,220 |
| `stg_teamfights`    | table (incremental) | one row per (match, fight) | `(match_id, teamfight_id)`| 16,543 |
| `stg_leagues`       | view                | one row per league         | `leagueid`                | 10,025 |
| `stg_teams`         | view                | one row per team           | `team_id`                 | 21,869 |
| `stg_players`       | view                | one row per pro player     | `account_id`              | 5,084  |
| `stg_heroes`        | view                | one row per hero           | `hero_id`                 | 127    |
| `stg_hero_stats`    | view                | one row per hero           | `hero_id`                 | 127    |
| `stg_constants`     | view                | one row per resource       | `resource`                | 24     |

## Relationship diagram (with cardinality)

```
stg_leagues (leagueid) 1 <---- many  stg_matches (match_id)
                                          |        |
                        stg_teams (team_id) <---- many  radiant_team_id
                        stg_teams (team_id) <---- many  dire_team_id
                                          |
        one |                             |
   stg_matches (match_id) -------> many  stg_match_players (match_id)
                                          |        |
                                          |  many->1 account_id -> stg_players
                                          |  many->1 hero_id    -> stg_heroes
                                          |
        one |                             |
   stg_matches -------> many  stg_picks_bans (match_id) --many->1-> stg_heroes
                                          |
        one |                             |
   stg_matches -------> many  stg_teamfights (match_id)

stg_hero_stats (hero_id) 1 <---- 1  stg_heroes (hero_id)
```

Cardinality legend: `1` = one, `many` = many (child rows). The "one" side is
always the dimension/lookup table; the "many" side is the fact table.

### Join keys, cardinalities, and flow (Power BI relationships)

Cardinality is written from the perspective of the first (left) table.

| # | From (table) | To (table) | Join key | Cardinality | Direction / flow |
|---|--------------|------------|----------|-------------|------------------|
| 1 | `stg_matches` | `stg_leagues` | `leagueid` = `leagueid` | many-to-one | matches flow up to league (1 league has many matches) |
| 2 | `stg_matches` | `stg_teams` | `radiant_team_id` = `team_id` | many-to-one | radiant team dim (1 team appears in many matches) |
| 3 | `stg_matches` | `stg_teams` | `dire_team_id` = `team_id` | many-to-one | dire team dim (use USERELATIONSHIP) |
| 4 | `stg_matches` | `stg_match_players` | `match_id` = `match_id` | one-to-many | 1 match -> up to 10 players |
| 5 | `stg_matches` | `stg_picks_bans` | `match_id` = `match_id` | one-to-many | 1 match -> many picks/bans |
| 6 | `stg_matches` | `stg_teamfights` | `match_id` = `match_id` | one-to-many | 1 match -> many teamfights |
| 7 | `stg_match_players` | `stg_players` | `account_id` = `account_id` | many-to-one | player dim (1 player plays many matches) |
| 8 | `stg_match_players` | `stg_heroes` | `hero_id` = `hero_id` | many-to-one | hero dim (1 hero used in many matches) |
| 9 | `stg_picks_bans` | `stg_heroes` | `hero_id` = `hero_id` | many-to-one | hero dim for draft analysis |
| 10 | `stg_hero_stats` | `stg_heroes` | `hero_id` = `hero_id` | one-to-one | hero aggregate lookup |

### Data flow

Layer-by-layer flow from source files to silver (arrow = relationship "one -> many"):

```
BRONZE (raw jsonb)              SILVER (dbt)                          DIMENSIONS (lookups)
-------------------             -------------------------             -----------------------
bronze.matches     -----------> stg_matches       (4,232)   ---------> stg_leagues  (10,025)
    4,232                        |       |         |
     |                           |       +--------> stg_teams  (21,869)  via radiant/dire_team_id
     | (players[])               |
     |                           +--many--> stg_match_players (42,085) --> stg_players (5,084)
     |                           |                      |
     |                           |                      +--> stg_heroes (127)
     | (picks_bans[])            |
     +--many--> stg_picks_bans (87,220) ---------------> stg_heroes (127)
     | (teamfights[])            |
     +--many--> stg_teamfights (16,543)  (players kept as text, no hero link)

bronze.hero_stats  -----------> stg_hero_stats (127)   --------------> stg_heroes (127)
bronze.constants   -----------> stg_heroes (127)   /  stg_constants (24)
bronze.leagues     -----------> stg_leagues (10,025)
bronze.teams       -----------> stg_teams   (21,869)
bronze.players     -----------> stg_players (5,084)
```

Reading the flow:

1. Match data originates from `bronze.matches` and fans out (one-to-many) into
   the four fact tables: `stg_matches`, `stg_match_players`, `stg_picks_bans`,
   `stg_teamfights`.
2. Each fact table joins to dimension lookups on its foreign keys
   (league/team/player/hero).
3. Dimensional lookups are the "filter" tables; facts are the "measure" tables.
   This is the classic star-schema shape Power BI expects.

### Notes / nuances

- `stg_matches` has TWO relationships to `stg_teams` (radiant side + dire side).
  In Power BI only one can be active; make the other one inactive and use
  `USERELATIONSHIP` when needed.
- A player's side within a match is `stg_match_players.team_number`
  (0 = radiant, 1 = dire). `stg_players.team_id` is only the player's *current*
  pro team snapshot - do not use it to infer match sides.
- Silver keeps join keys typed and indexed but does NOT enforce hard FK
  constraints (bronze JSONB makes no referential-integrity guarantee).
  FKs are enforced in the gold layer.
- `stg_teamfights` links to heroes only indirectly: OpenDota teamfight player
  entries carry no hero/account id (only ability names and deltas), so the
  model keeps the raw `players` payload (as **text** - jsonb cast to text in
  silver, because jsonb columns break Power BI DirectQuery folding) and cannot
  join per-fight rows to heroes.

---

## Fact tables (incremental, growing)

### stg_matches
One row per match. Core match-level fact.

| Column | Type | Notes |
|--------|------|-------|
| `match_id`         | text    | PK; key columns are text to match Power BI types |
| `radiant_win`      | boolean | true = radiant won, false = dire won |
| `winner`           | text    | `'radiant'` / `'dire'` / `'draw'` (derived) |
| `duration_sec`     | integer | match length in seconds |
| `game_mode`        | text    | code; see constants `game_mode` |
| `lobby_type`       | text    | code; see constants `lobby_type` |
| `region`           | text    | code; see constants `region` |
| `patch`            | text    | patch number (e.g. 60) |
| `start_time`       | timestamptz | match start (epoch converted) |
| `radiant_score`    | integer | radiant kills total |
| `dire_score`       | integer | dire kills total |
| `radiant_team_id`  | text    | nullable; FK to stg_teams |
| `dire_team_id`     | text    | nullable; FK to stg_teams |
| `has_radiant_team` | boolean | radiant_team_id is not null |
| `has_dire_team`    | boolean | dire_team_id is not null |
| `leagueid`         | text    | FK to stg_leagues |
| `first_blood_time` | integer | seconds into match |
| `human_players`    | integer | 10 for a full pro match |
| `pre_game_duration`| integer | hero-select window in seconds |
| `replay_salt`      | text    | replay identifier |
| `version`          | text    | engine/version code |
| `loaded_at`        | timestamptz | bronze load time |

### stg_match_players
One row per (match, player). Player performance detail.

| Column | Type | Notes |
|--------|------|-------|
| `match_id`    | text    | FK to stg_matches |
| `player_slot` | text    | 0-127; part of unique key |
| `account_id`  | text    | FK to stg_players |
| `hero_id`     | text    | FK to stg_heroes |
| `team_number` | text    | 0 = radiant, 1 = dire |
| `kills`       | integer | |
| `deaths`      | integer | |
| `assists`     | integer | |
| `kda`         | numeric | `(kills+assists)/nullif(deaths,0)`; if 0 deaths, kills+assists |
| `gold`        | integer | gold at end |
| `gold_spent`  | integer | |
| `net_worth`   | integer | |
| `gold_per_min`| integer | |
| `xp_per_min`  | integer | |
| `hero_damage` | integer | damage dealt to heroes |
| `hero_healing`| integer | |
| `tower_damage`| integer | |
| `tower_kills` | integer | |
| `stuns`       | numeric | total stun duration (seconds) |
| `last_hits`   | integer | |
| `denies`      | integer | |
| `camps_stacked`| integer | |
| `creeps_stacked`| integer | |
| `neutral_kills`| integer | |
| `rune_pickups` | integer | |
| `level`       | text    | hero level at end |
| `item_0`..`item_5` | text | item ids; see constants `items` |
| `item_neutral`| text    | neutral item id |
| `backpack_0`..`backpack_3` | text | backpack item ids |
| `leaver_status`| text   | 0 = normal |
| `randomed`    | boolean | hero was randomed |
| `firstblood_claimed` | integer | 1 if claimed first blood |
| `buyback_count`| integer | |
| `loaded_at`   | timestamptz | |

### stg_picks_bans
One row per (match, draft order). Captures picks and bans.

| Column | Type | Notes |
|--------|------|-------|
| `match_id`    | text    | FK to stg_matches |
| `order_no`    | text    | draft order within the match (unique with match_id) |
| `hero_id`     | text    | FK to stg_heroes |
| `is_pick`     | boolean | true = picked, false = banned |
| `active_team` | text    | 0/1 = radiant/dire; 2/3 = pick phase teams |
| `player_slot` | text    | nullable; who made the pick |
| `loaded_at`   | timestamptz | |

### stg_teamfights
One row per (match, teamfight). Fight-level data; player detail kept as text
(jsonb cast to text at this layer - see section on DirectQuery/10682).

| Column | Type | Notes |
|--------|------|-------|
| `match_id`     | text    | FK to stg_matches |
| `teamfight_id` | text    | fight ordinal within the match |
| `start_time`   | integer | fight start (sec into match) |
| `end_time`     | integer | fight end (sec into match) |
| `last_death`   | integer | time of last death in the fight |
| `deaths`       | integer | total deaths in the fight |
| `duration_sec` | integer | `end_time - start_time` |
| `players`      | text   | raw per-fight player entries as text (no hero id available) |
| `loaded_at`    | timestamptz | |

---

## Dimension tables (views, small / stable)

### stg_leagues

| Column | Type |
|--------|------|
| `leagueid`    | text (PK) |
| `league_name` | text |
| `tier`        | text (e.g. professional, amateur, excluded) |
| `ticket`      | text |
| `banner`      | text |

### stg_teams

| Column | Type |
|--------|------|
| `team_id`   | text (PK) |
| `team_name` | text |
| `team_tag`  | text (e.g. TALON) |
| `rating`    | numeric |
| `wins`      | integer |
| `losses`    | integer |
| `logo_url`  | text |

### stg_players

| Column | Type |
|--------|------|
| `account_id`  | text (PK) |
| `player_name` | text |
| `rank_tier`   | text (nullable) |
| `team_id`     | text (current pro team snapshot) |

### stg_heroes

| Column | Type |
|--------|------|
| `hero_id`        | text (PK) |
| `hero_name`      | text (e.g. npc_dota_hero_antimage) |
| `localized_name` | text (e.g. Anti-Mage) |
| `primary_attr`   | text (`str`, `agi`, `int`, `all`) |
| `attack_type`    | text (`Melee` / `Ranged`) |
| `roles`          | jsonb (role tags) |
| `img`            | text (icon path) |

### stg_hero_stats

| Column | Type | Notes |
|--------|------|-------|
| `hero_id`      | text (PK) |
| `pro_pick`     | integer | pro-game picks |
| `pro_win`      | integer | pro-game wins |
| `pro_ban`      | integer | pro-game bans |
| `pub_pick`     | integer | public-game picks |
| `pub_win`      | integer | public-game wins |
| `pub_win_rate` | numeric | derived `100 * pub_win / pub_pick` (%) |

### stg_constants
All 24 static resources in one lookup view.

| Column | Type |
|--------|------|
| `resource`         | text (PK), e.g. heroes, items, game_mode, region, patch |
| `resource_payload` | jsonb (full resource) |
| `payload_type`     | text (`object` / `array`) |
| `loaded_at`        | timestamptz |

---

## Gold layer (star schema for Power BI)

The `gold` schema is the **presentation layer** Power BI connects to. It is a
clean star schema built from silver, with all Power BI relationship pitfalls
fixed:

- `dim_hero` includes an **Unknown hero (`hero_id = 0`)** so every `hero_id` in
  the facts resolves (fixes OpenDota's `hero_id = 0` placeholder that broke the
  silver hero join).
- `dim_player` covers **all match participants** (pro players with metadata +
  non-pro participants as `match_participant`) so every `account_id` resolves.
- `dim_team` adds **Unknown teams** for ids that appear only in matches.
- `fact_team_matches` is a **team-side bridge** (one row per match + side) that
  replaces the dual `radiant_team_id` / `dire_team_id` links to `dim_team`, so
  team filters work with one active relationship and no `USERELATIONSHIP`.
- `stg_constants` is **flattened** into real decode dims:
  `dim_game_mode`, `dim_lobby_type`, `dim_region`.
- `stg_hero_stats` is **merged into `dim_hero`** (no separate orphan table).
- Facts connect cleanly: `fact_teamfights` and `fact_picks_bans` both link to
  `fact_matches` on `match_id`; `fact_match_players` links to matches, players,
  and heroes.
- All joins are proven by dbt **relationship tests** (referential integrity).

### Gold relationship diagram (with cardinality)

```
                      dim_league (leagueid) 1
                            |
                            +--many--> fact_matches (match_id) ---------+
                     dim_team (team_id) <--many-- fact_team_matches.team_id |
                     dim_game_mode <--many-- game_mode_id                  |
                     dim_lobby_type <--many-- lobby_type_id                |
                        dim_region <--many-- region_id                     |
                            |                                              |
            one |           |                                              |
       fact_matches ------> many  fact_match_players (match_id)            |
                            |        |   many->1 account_id -> dim_player  |
                            |        |   many->1 hero_id    -> dim_hero    |
            one |           |                                              |
       fact_matches ------> many  fact_picks_bans (match_id)               |
                            |        |   many->1 hero_id -> dim_hero       |
            one |           |                                              |
       fact_matches ------> many  fact_teamfights (match_id)               |
            one |           |                                              |
       fact_matches ------> many  fact_team_matches (match_id)             |
                                     |   many->1 team_id -> dim_team       |
```

### Gold relationship table (for Power BI Model view)

All **many-to-one (\*:1)**, cross-filter **Single (Many→1)** unless marked (1:\*).

#### `fact_matches` → dimensions (many-to-one, *:1)

| From column | To table | To column | Active |
|-------------|----------|-----------|--------|
| `leagueid` | `dim_league` | `leagueid` | yes |
| `game_mode_id` | `dim_game_mode` | `game_mode_id` | yes |
| `lobby_type_id` | `dim_lobby_type` | `lobby_type_id` | yes |
| `region_id` | `dim_region` | `region_id` | yes |
| `start_date` | `dim_date` | `date` | yes |

#### `fact_matches` → child facts (one-to-many, 1:*)

| From column | To table | To column | Active |
|-------------|----------|-----------|--------|
| `match_id` | `fact_match_players` | `match_id` | yes |
| `match_id` | `fact_picks_bans` | `match_id` | yes |
| `match_id` | `fact_teamfights` | `match_id` | yes |
| `match_id` | `fact_team_matches` | `match_id` | yes |

#### `fact_team_matches` → `dim_team` (bridge, many-to-one, *:1)

| From column | To table | To column | Active |
|-------------|----------|-----------|--------|
| `team_id` | `dim_team` | `team_id` | yes |

Team note: `fact_team_matches` is the **single** link between the fact layer and
`dim_team` (one row per match + side). It replaces the old dual
`radiant_team_id` / `dire_team_id` links to `dim_team`, so **no inactive
relationship or `USERELATIONSHIP` is needed** - both sides of a match are
queryable at the same time, split by the `side` column.

#### `fact_match_players` → dimensions (many-to-one, *:1)

| From column | To table | To column | Active |
|-------------|----------|-----------|--------|
| `account_id` | `dim_player` | `account_id` | yes |
| `hero_id` | `dim_hero` | `hero_id` | yes |

#### `fact_picks_bans` → dimension (many-to-one, *:1)

| From column | To table | To column | Active |
|-------------|----------|-----------|--------|
| `hero_id` | `dim_hero` | `hero_id` | yes |

#### `dim_hero` → bridge (one-to-many, 1:*)

| From column | To table | To column | Active |
|-------------|----------|-----------|--------|
| `hero_id` | `dim_hero_role` | `hero_id` | yes |

#### `fact_teamfight_players` → (many-to-one, *:1)

| From column | To table | To column | Active |
|-------------|----------|-----------|--------|
| `match_id` | `fact_matches` | `match_id` | yes |
| `hero_id` | `dim_hero` | `hero_id` | yes |
| `account_id` | `dim_player` | `account_id` | yes |

#### `fact_teamfight_ability_uses` → (many-to-one, *:1)

| From column | To table | To column | Active |
|-------------|----------|-----------|--------|
| `match_id` | `fact_matches` | `match_id` | yes |
| `hero_id` | `dim_hero` | `hero_id` | yes |
| `account_id` | `dim_player` | `account_id` | yes |

#### `fact_teamfight_item_uses` → (many-to-one, *:1)

| From column | To table | To column | Active |
|-------------|----------|-----------|--------|
| `match_id` | `fact_matches` | `match_id` | yes |
| `hero_id` | `dim_hero` | `hero_id` | yes |
| `account_id` | `dim_player` | `account_id` | yes |

#### `fact_teamfight_kills` → (many-to-one, *:1)

| From column | To table | To column | Active |
|-------------|----------|-----------|--------|
| `match_id` | `fact_matches` | `match_id` | yes |
| `hero_id` | `dim_hero` | `hero_id` (killer) | yes |
| `account_id` | `dim_player` | `account_id` | yes |
| `victim_hero_id` | `dim_hero` | `hero_id` (victim) | yes |

### Gold table inventory

| Model | Rows | Grain | PK |
|-------|------|-------|----|
| `dim_hero`        | 128 | one row per hero (+ Unknown)  | `hero_id` |
| `dim_hero_role`   | 460 | one row per (hero, role) bridge | `(hero_id, role)` |
| `dim_player`      | 5,930 | one row per player (pro + participants) | `account_id` |
| `dim_team`        | 21,873 | one row per team (+ Unknown) | `team_id` |
| `dim_league`      | 10,025 | one row per league | `leagueid` |
| `dim_game_mode`   | 26 | one row per game mode code | `game_mode_id` |
| `dim_lobby_type`  | 16 | one row per lobby type code | `lobby_type_id` |
| `dim_region`      | 22 | one row per region code | `region_id` |
| `dim_date`        | 18,628 | one row per day (2000-01-01 -> 2050-12-31) | `date` |
| `fact_matches`        | 4,232 | one row per match | `match_id` |
| `fact_match_players`  | 42,085 | one row per (match, player) | `(match_id, player_slot)` |
| `fact_picks_bans`     | 87,220 | one row per (match, draft order) | `(match_id, order_no)` |
| `fact_teamfights`     | 16,543 | one row per (match, teamfight) | `(match_id, teamfight_id)` |
| `fact_team_matches`   | 8,358  | one row per (match, side) bridge | `(match_id, side)` |
| `fact_teamfight_players` | 165,430 | one row per (match, teamfight, player) | `(match_id, teamfight_id, player_slot)` |
| `fact_teamfight_ability_uses` | 470,512 | one row per (match, teamfight, player, ability) | `(match_id, teamfight_id, player_slot, ability_name)` |
| `fact_teamfight_item_uses` | 392,088 | one row per (match, teamfight, player, item) | `(match_id, teamfight_id, player_slot, item_name)` |
| `fact_teamfight_kills` | 66,749 | one row per (match, teamfight, killer, victim hero) | `(match_id, teamfight_id, player_slot, victim_hero_id)` |

### Gold column reference

#### dim_hero (identity + hero_stats merged + Unknown row)

| Column | Type | Notes |
|--------|------|-------|
| `hero_id` | text (PK) | includes `'0'` = Unknown |
| `hero_name` | text | e.g. `npc_dota_hero_antimage` |
| `hero_localized_name` | text | e.g. `Anti-Mage`; `'Unknown'` for id 0 |
| `primary_attr` | text | `str` / `agi` / `int` / `all` |
| `attack_type` | text | `Melee` / `Ranged` |
| `roles` | text | role tags (jsonb cast to text) |
| `img` | text | icon path |
| `pro_pick` / `pro_win` / `pro_ban` | integer | from hero_stats |
| `pub_pick` / `pub_win` | integer | from hero_stats |
| `pub_win_rate` | numeric | `100 * pub_win / pub_pick` (%) |

All gold key/ID columns are **text** (inherited from silver) so Power BI
relationships import without type mismatches.

#### dim_hero_role (bridge)

| Column | Type | Notes |
|--------|------|-------|
| `hero_id` | text | FK to dim_hero |
| `role` | text | one of Carry / Support / Nuker / Disabler / Durable / Escape / Initiator / Pusher |

Filters heroes by role: `dim_hero` 1 → many `dim_hero_role`. The raw
`dim_hero.roles` (text) is kept for detail; use this table for role slicers.

#### dim_player

| Column | Type | Notes |
|--------|------|-------|
| `account_id` | text (PK) | every account in the facts covered |
| `player_name` | text | nullable for non-pro participants |
| `rank_tier` | text | nullable |
| `team_id` | text | current pro team snapshot (nullable) |
| `player_type` | text | `pro` or `match_participant` |

#### dim_team

| Column | Type | Notes |
|--------|------|-------|
| `team_id` | text (PK) | includes Unknown teams |
| `team_name` | text | `'Unknown'` for id-only teams |
| `team_tag` / `rating` / `wins` / `losses` / `logo_url` | - | nullable for Unknown |

#### dim_game_mode / dim_lobby_type / dim_region (flattened constants)

| Column | Type | Notes |
|--------|------|-------|
| `game_mode_id` / `lobby_type_id` / `region_id` | text (PK) | the code stored in facts |
| `game_mode_name` / `lobby_type_name` / `region_name` | text | human label |
| `is_balanced` | boolean | game_mode / lobby_type only |

#### dim_date (calendar dimension)

One row per day from 2000-01-01 to 2050-12-31 (covers the full match history
plus a wide margin for any time-based analysis).
Joins to `fact_matches.start_date`.

| Column | Type | Notes |
|--------|------|-------|
| `date` | date (PK) | calendar day |
| `day_of_month` | integer | 1-31 |
| `day_of_week` | integer | 0 = Sunday ... 6 = Saturday |
| `day_of_week_name` | text | e.g. `Monday` |
| `day_of_week_short_name` | text | e.g. `Mon` |
| `iso_day_of_week` | integer | 1 = Monday ... 7 = Sunday (ISO) |
| `is_weekend` | boolean | Sat/Sun |
| `day_of_year` | integer | 1-366 |
| `week_of_year` | integer | ISO-8601 week number |
| `iso_week_of_year` | integer | same as week_of_year (PG week is ISO) |
| `week_start_date` | date | Monday of that week |
| `month` | integer | 1-12 |
| `month_name` | text | e.g. `January` |
| `month_short_name` | text | e.g. `Jan` |
| `year_month` | text | e.g. `2024-01` (sortable) |
| `quarter` | integer | 1-4 |
| `quarter_name` | text | e.g. `Q1` |
| `year_quarter` | text | e.g. `2024-Q1` |
| `year` | integer | e.g. 2024 |
| `year_month_name` | text | e.g. `2024-Jan` |
| `is_leap_year` | boolean | |

#### fact_matches

Same columns as `stg_matches`, with keys renamed to make the star explicit:
`game_mode` → `game_mode_id`, `lobby_type` → `lobby_type_id`, `region` →
`region_id`, plus a `start_date` (date cast of `start_time`) that joins to
`dim_date`. `leagueid`, `radiant_team_id`, `dire_team_id` stay as-is.

Duration helpers added: `duration_min` (`duration_sec / 60`) and `duration_hour`
(`duration_sec / 3600`). The raw `duration_sec` is kept for precision.

`radiant_team_id` / `dire_team_id` are still present for reference but are **no
longer connected to `dim_team` in Power BI** - team analytics go through the
`fact_team_matches` bridge instead.

#### fact_team_matches (team-side bridge fact)

One row per (match, side). The **only** path from the fact layer to `dim_team`,
so a team's matches on both the radiant and the dire side resolve through one
active relationship. Built by unpivoting `stg_matches.radiant_team_id` and
`dire_team_id` into two rows (`Radiant` / `Dire`).

| Column | Type | Notes |
|--------|------|-------|
| `match_id` | text | FK to fact_matches (composite grain with `side`) |
| `side` | text | `'Radiant'` or `'Dire'` |
| `team_id` | text | FK to dim_team |
| `radiant_win` | boolean | copy of the match's `radiant_win` |
| `team_win` | boolean | this team won: radiant side = `radiant_win`, dire side = `NOT radiant_win`; null for draw matches |
| `team_score` | integer | kills by this team (`radiant_score` / `dire_score`) |
| `opponent_score` | integer | kills by the opposing team |

Only rows whose side has a team are emitted (`has_radiant_team` / `has_dire_team`),
so a match appears once, twice, or not at all depending on how many team ids it
has (2 of 4,232 matches are recorded draws with `radiant_win` null; 29 matches
have no team on either side).

#### fact_match_players / fact_picks_bans / fact_teamfights

Same columns as the matching `stg_*` tables (see silver reference above).
`hero_id = 0` in `fact_match_players` resolves to the Unknown hero row in
`dim_hero`.

`fact_teamfights` also exposes minutes variants: `start_min`, `end_min`,
`last_death_min` (the raw `start_time` / `end_time` / `last_death` are seconds
elapsed into the match, not wall-clock times) and `duration_min` alongside
`duration_sec`.

#### fact_teamfight_players (granular teamfight breakdown)

One row per (match, teamfight, player). Derived from the `players` jsonb array
(parsed in SQL via `::jsonb` cast; the stored column is text), which OpenDota
always provides as **exactly 10 entries ordered by player slot**
(indices 1-5 = radiant slots 0-4, indices 6-10 = dire slots 128-132). That
positional guarantee lets us join to `fact_match_players` and `dim_hero`.

| Column | Type | Notes |
|--------|------|-------|
| `match_id` | text | FK to fact_matches |
| `teamfight_id` | text | FK to fact_teamfights |
| `teamfight_start` / `teamfight_end` | integer | copied from fact_teamfights |
| `player_slot` | text | recovered from array position |
| `hero_id` | text | FK to dim_hero (via fact_match_players) |
| `account_id` | text | FK to dim_player (via fact_match_players) |
| `damage` / `healing` | integer | dealt in the fight |
| `deaths` / `buybacks` | integer | |
| `xp_start` / `xp_end` / `xp_delta` | integer | |
| `gold_delta` | integer | |
| `ability_uses` / `item_uses` / `ability_targets` / `killed` / `deaths_pos` | text | nested per-ability/per-item maps as text (jsonb cast to text; parsed back with `::jsonb` in the child facts) |

#### fact_teamfight_ability_uses / fact_teamfight_item_uses / fact_teamfight_kills

Child facts that flatten the per-player maps from `fact_teamfight_players` into
long format (one row per map entry), so Power BI can slice/pivot them without
`jsonb` parsing. They keep the FK columns (`match_id`, `player_slot`, `hero_id`,
`account_id`) and link **directly** to `fact_matches`, `dim_hero`, and
`dim_player` (not to `fact_teamfight_players`, whose key is composite and not
Power BI friendly).

| Column (shared) | Type | Notes |
|-----------------|------|-------|
| `match_id` | text | FK to fact_matches |
| `teamfight_id` | text | |
| `player_slot` | text | |
| `hero_id` | text | FK to dim_hero (killer hero) |
| `account_id` | text | FK to dim_player |

| Table | Extra columns | Notes |
|-------|---------------|-------|
| `fact_teamfight_ability_uses` | `ability_name` (text), `uses` (int) | flattened from `ability_uses` |
| `fact_teamfight_item_uses` | `item_name` (text), `uses` (int) | flattened from `item_uses` |
| `fact_teamfight_kills` | `victim_hero_name` (text), `victim_hero_id` (text), `kills` (int) | flattened from `killed`; `victim_hero_name` is an `npc_dota_hero_*` value joining to `dim_hero.hero_name`, so `victim_hero_id` resolves to the victim hero row |

Note: `killed` is a map of **victim hero name -> kill count** for that killer in
that fight. 51,130 of 165,430 teamfight-player rows have at least one entry;
rows with an empty map simply produce no rows here.

---

## Layer philosophy (where transformations belong)

Medallion architecture is a **data-flow pattern**, not a strict rule about
whether data must be flat or nested at each stage. What matters is each layer's
responsibility:

- **Bronze (raw):** untouched JSON as pulled from the API. Never transformed.
- **Silver (cleaned / canonical):** the single source of truth. Typed, validated,
  deduplicated, conformed (shared ids, consistent naming). It is **not** required
  to be BI-shaped - keeping nested payloads here is fine and normal, as long as
  the data is clean. Silver is a faithful, queryable copy of what happened.
  **One exception:** any nested payload that will travel to gold must be stored
  as **text** (jsonb cast to text), because jsonb columns break Power BI
  DirectQuery query folding (error 10682 - see `docs/power_bi_setup.md` §8).
  Parsing back with `::jsonb` happens in downstream SQL where needed.
- **Gold (presentation):** shaped *for the BI tool*. Star schema, dims/facts,
  decode tables, and **detail / bridge tables** materialized specifically so
  Power BI can slice and pivot without parsing JSON.

This is why nested maps (e.g. `ability_uses` in `stg_teamfights`) are flattened
into child facts (`fact_teamfight_ability_uses`, `fact_teamfight_item_uses`,
`fact_teamfight_kills`) at **gold**, not silver: silver owns the canonical record
(one row per teamfight with its maps intact, stored as text), and gold owns the
consumer-friendly long-format shapes. Flattening in silver is also a valid
choice - both are correct as long as bronze stays raw and all transform logic
lives in versioned, testable dbt models rather than in the BI tool or ad-hoc
SQL.

## Naming conventions

- All lower-case snake_case columns.
- `stg_` prefix for silver models; `dim_` / `fact_` prefixes for gold models.
- `_per_min` / `_rate` suffixes for computed metrics.
- Booleans use `has_*` prefix for presence flags.
- text columns carrying names use `<entity>_name` (e.g. `team_name`, `hero_name`).
- Gold foreign keys are named after the code they carry (`game_mode_id`, etc.).

## Indexes

Silver incremental tables:

- `stg_matches`: leagueid, radiant_team_id, dire_team_id
- `stg_match_players`: match_id, account_id, hero_id
- `stg_picks_bans`: match_id, hero_id
- `stg_teamfights`: match_id

Gold fact tables:

- `fact_matches`: leagueid, game_mode_id, lobby_type_id, region_id, radiant_team_id, dire_team_id
- `fact_team_matches`: match_id, team_id, side
- `fact_match_players`: match_id, account_id, hero_id
- `fact_picks_bans`: match_id, hero_id
- `fact_teamfights`: match_id
- `fact_teamfight_players`: match_id, hero_id, account_id
