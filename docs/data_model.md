# Dota 2 Data Model - Silver Layer

Complete reference for the `silver` schema of the Dota 2 medallion architecture.
All models read from raw `bronze.*` JSONB and are built by dbt (`transform/`).
This document is verified against the live database schema (`\d silver.*`).

## Quick reference

| Model | Materialized | Grain | PK / unique key | Rows |
|-------|--------------|-------|-----------------|------|
| `stg_matches`       | table (incremental) | one row per match          | `match_id`                | 4,299  |
| `stg_match_players` | table (incremental) | one row per (match, player)| `(match_id, player_slot)` | 42,755 |
| `stg_picks_bans`    | table (incremental) | one row per (match, order) | `(match_id, order_no)`    | 88,804 |
| `stg_teamfights`    | table (incremental) | one row per (match, fight) | `(match_id, teamfight_id)`| 16,944 |
| `stg_leagues`       | view                | one row per league         | `leagueid`                | 10,036 |
| `stg_teams`         | view                | one row per team           | `team_id`                 | 21,884 |
| `stg_players`       | view                | one row per pro player     | `account_id`              | 5,093  |
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
bronze.matches     -----------> stg_matches       (4,299)   ---------> stg_leagues  (10,036)
    4,299                        |       |         |
     |                           |       +--------> stg_teams  (21,884)  via radiant/dire_team_id
     | (players[])               |
     |                           +--many--> stg_match_players (42,755) --> stg_players (5,093)
     |                           |                      |
     |                           |                      +--> stg_heroes (127)
     | (picks_bans[])            |
     +--many--> stg_picks_bans (88,804) ---------------> stg_heroes (127)
     | (teamfights[])            |
     +--many--> stg_teamfights (16,944)  (players kept as text, no hero link)

bronze.hero_stats  -----------> stg_hero_stats (127)   --------------> stg_heroes (127)
bronze.constants   -----------> stg_heroes (127)   /  stg_constants (24)
bronze.leagues     -----------> stg_leagues (10,036)
bronze.teams       -----------> stg_teams   (21,884)
bronze.players     -----------> stg_players (5,093)
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
| `team_win`    | boolean | player's team won: team_number 0 = radiant_win, 1 = NOT radiant_win; null for draw matches (2 matches, 20 rows) |
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
- `dim_hero` / `dim_player` / `dim_team` additionally carry **precomputed
  `match_*` aggregate columns** (`match_picks`, `match_win_rate`,
  `match_avg_kda`, `match_avg_gpm`, ...) computed from the gold facts at build
  time. They are **static snapshots that ignore slicers**, so the report does
  not import them — leaderboards use measures instead. See
  `git history (branch archive/report-status-history)` §4 / §7.

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

Per-minute progression facts (Rounds 6/7, Match Detail page):

```
fact_matches 1 --> many  fact_match_player_minute (match_id)  -- many->1 dim_hero / dim_player
fact_matches 1 --> many  fact_match_player_skills    (match_id)  -- many->1 dim_hero / dim_player
fact_matches 1 --> many  fact_match_player_item_purchases (match_id) -- many->1 dim_hero / dim_player
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

#### `dim_patch` / `dim_item` → decode (many-to-one, *:1) *(rounds 1–2)*

| From column | To table | To column | Active |
|-------------|----------|-----------|--------|
| `patch` (fact_matches) | `dim_patch` | `patch_id` | yes |
| `item_0` (fact_match_players) | `dim_item` | `item_id` | yes |

#### `fact_hero_matchups` / `fact_hero_matchups_hero` → (many-to-one, *:1) *(round 1)*

`fact_hero_matchups`: `match_id` → `fact_matches`, `radiant_hero_id` → `dim_hero`
(active), `dire_hero_id` → `dim_hero` (second hero link — same
`USERELATIONSHIP` caveat as `victim_hero_id`).
`fact_hero_matchups_hero` (one row per hero side): `match_id` → `fact_matches`,
`hero_id` → `dim_hero` (active), `opponent_id` → `dim_hero` (second link).

#### `fact_team_h2h` → (many-to-one, *:1) *(round 1)*

| From column | To table | To column | Active |
|-------------|----------|-----------|--------|
| `match_id` | `fact_matches` | `match_id` | yes |
| `team_a_id` | `dim_team` | `team_id` | yes |
| `team_b_id` | `dim_team` | `team_id` | second team link (inactive) |

#### `fact_match_player_minute` → (many-to-one, *:1) *(round 6)*

| From column | To table | To column | Active |
|-------------|----------|-----------|--------|
| `match_id` | `fact_matches` | `match_id` | yes |
| `hero_id` | `dim_hero` | `hero_id` | yes |
| `account_id` | `dim_player` | `account_id` | yes |

#### `fact_match_player_skills` → (many-to-one, *:1) *(rounds 6–7)*

| From column | To table | To column | Active |
|-------------|----------|-----------|--------|
| `match_id` | `fact_matches` | `match_id` | yes |
| `hero_id` | `dim_hero` | `hero_id` | yes |
| `account_id` | `dim_player` | `account_id` | yes |

#### `fact_match_player_item_purchases` → (many-to-one, *:1) *(round 7)*

| From column | To table | To column | Active |
|-------------|----------|-----------|--------|
| `match_id` | `fact_matches` | `match_id` | yes |
| `hero_id` | `dim_hero` | `hero_id` | yes |
| `account_id` | `dim_player` | `account_id` | yes |

Note (2026-08-08): the three `match_id` links above are **single-direction**
(the default). A `bothDirections` variant was tried so the Match Detail
**match_id slicer** could sit on the many side
(`fact_match_player_item_purchases.match_id`), but that made Power BI Desktop
fail with `PFE_XL_USERELATIONSHIP_AMBIGUOUS_PATH` (ambiguous paths between
`fact_match_players` and `dim_match_minute` via the skills and item_purchases
minute links). The bidirectional additions were **reverted**; instead the slicer
was re-bound to `fact_matches.match_id` (the hub) so single-direction filtering
reaches every fact table.

**Round 9 (2026-08-08):** hero-slicer scoping to the selected match is solved
without any relationship change — a `Hero in Current Match` measure on
`dim_hero` (CALCULATE over `fact_match_players`) plus a visual-level Advanced
filter on both hero slicers. The model keeps **53 relationships, 3
bidirectional**. See `git history (branch archive/report-status-history)` §5j.

#### `fact_match_player_runes` → (many-to-one, *:1) *(round 10)*

| From column | To table | To column | Active |
|-------------|----------|-----------|--------|
| `match_id` | `fact_matches` | `match_id` | yes |
| `hero_id` | `dim_hero` | `hero_id` | yes |
| `account_id` | `dim_player` | `account_id` | yes |
| `rune_key` | `dim_rune` | `rune_key` | yes |

#### `fact_match_player_damage` → (many-to-one, *:1) *(round 10)*

| From column | To table | To column | Active |
|-------------|----------|-----------|--------|
| `match_id` | `fact_matches` | `match_id` | yes |
| `hero_id` | `dim_hero` | `hero_id` | yes |
| `account_id` | `dim_player` | `account_id` | yes |

#### `fact_match_player_damage_taken` → (many-to-one, *:1) *(round 10)*

| From column | To table | To column | Active |
|-------------|----------|-----------|--------|
| `match_id` | `fact_matches` | `match_id` | yes |
| `hero_id` | `dim_hero` | `hero_id` | yes |
| `account_id` | `dim_player` | `account_id` | yes |

**Round 10/11 (2026-08-08):** `fact_match_players` also carries denormalized
per-player columns for the Match Detail tables: `pick_sequence`, `enemy_heroes_killed`,
`damage_taken_physical/magical/pure`, `ward_observer_bought`, `ward_sentry_bought`,
`dust_bought`, `smoke_bought`, `gem_bought`, `support_gold`. The standalone
`fact_match_player_damage_taken_type` gold table (round 11) was **removed from
the Power BI model in Round 11d** (§5o) and **dropped from dbt + the DB in
Round 16** — the visuals use the denormalized `fact_match_players.damage_taken_*`
columns instead.

**Round 12 (2026-08-08):** new `fact_match_team_minute` (per match, side, minute:
team gold/xp summed from `fact_match_player_minute`).

**Round 13 (2026-08-09):** dims normalized (league/team uppercase; game-mode/
lobby prefix-stripped + uppercase; `primary_attr` friendly labels; `player_type`
→ Pro / Match Participant); `fact_team_h2h` gains denormalized
`team_a_name`/`team_b_name` (the `team_b_id` link is inactive); new precomputed
tables `fact_hero_side` (per hero+side picks/wins/win rate) and
`fact_hero_matchup_stats` (per `matchup_label` games + radiant/dire win rates)
for Draft-page tables that must fold under DirectQuery; `order_no_int` on
`fact_picks_bans` so `Avg Ban Position` folds. At that point the model was
**38 tables, 72 relationships (3 bidirectional)**.

**Round 16 (2026-08-16/17):** seven unused gold tables pruned from the Power BI
model and dropped from dbt + the DB (verified zero references in `.pbip`):
`fact_match_player_kills`, `fact_match_timeline`, `fact_match_timeline_events`,
`fact_team_compositions`, `fact_teamfight_item_uses`, `fact_teamfight_kills`,
`dim_match_minute`. The stale `gold.fact_team_h2h_new` experiment table was also
dropped from the DB. Model is now **31 tables, 52 relationships (3
bidirectional)**; dbt builds 32 gold models (the extra one, `fact_phase_momentum`,
was never imported into Power BI). See `git history (branch archive/report-status-history)` §5t.

### Gold table inventory

| Model | Rows | Grain | PK |
|-------|------|-------|----|
| `dim_hero`        | 128 | one row per hero (+ Unknown)  | `hero_id` |
| `dim_hero_role`   | 491 | one row per (hero, role) bridge | `(hero_id, role)` |
| `dim_player`      | 5,945 | one row per player (pro + participants) | `account_id` |
| `dim_team`        | 21,888 | one row per team (+ Unknown) | `team_id` |
| `dim_league`      | 10,036 | one row per league | `leagueid` |
| `dim_game_mode`   | 26 | one row per game mode code | `game_mode_id` |
| `dim_lobby_type`  | 16 | one row per lobby type code | `lobby_type_id` |
| `dim_region`      | 22 | one row per region code | `region_id` |
| `dim_date`        | 18,628 | one row per day (2000-01-01 -> 2050-12-31) | `date` |
| `fact_matches`        | 4,299 | one row per match | `match_id` |
| `fact_match_players`  | 42,755 | one row per (match, player) | `(match_id, player_slot)` |
| `fact_picks_bans`     | 88,804 | one row per (match, draft order) | `(match_id, order_no)` |
| `fact_draft_sequence` | ~20,490 | one row per (match, draft slot) — wide pick/ban pivot; slot count derived dynamically (grows with bans-per-team) | `(match_id, slot)` |
| `fact_teamfights`     | 16,944 | one row per (match, teamfight) | `(match_id, teamfight_id)` |
| `fact_team_matches`   | 8,492  | one row per (match, side) bridge | `(match_id, side)` |
| `fact_teamfight_players` | 169,440 | one row per (match, teamfight, player) | `(match_id, teamfight_id, player_slot)` |
| `fact_teamfight_ability_uses` | 483,509 | one row per (match, teamfight, player, ability) | `(match_id, teamfight_id, player_slot, ability_name)` |
| `dim_patch` | 61 | one row per patch version (decodes `fact_matches.patch`) | `patch_id` |
| `dim_item` | 596 | one row per item (decodes `item_0..6` ids) | `item_id` |
| `fact_hero_matchups` | 106,721 | one row per (match, radiant hero, dire hero) | `(match_id, radiant_hero_id, dire_hero_id)` |
| `fact_hero_matchups_hero` | 213,390 | one row per (match, hero, opponent) side | `(match_id, hero_id, opponent_id)` |
| `fact_team_h2h` | 4,220 | one row per (match, team_a, team_b) | `(match_id, team_a_id, team_b_id)` |
| `fact_phase_momentum` | 13,030 | one row per (match, team, fight phase) | `(match_id, team_number, fight_phase)` |
| `fact_match_player_minute` | 1,253,200 | one row per (match, player, minute) — level/gold/xp progression | `(match_id, player_slot, minute)` |
| `fact_match_player_skills` | 535,432 | one row per (match, player, skill upgrade) | `(match_id, player_slot, upgrade_index)` |
| `fact_match_player_item_purchases` | 1,526,552 | one row per item purchase event | `(match_id, player_slot, purchase_index)` |
| `dim_rune` | 10 | one row per rune type id (0-9) — decodes `fact_match_player_runes.rune_key` | `rune_key` |
| `fact_match_player_runes` | 79,044 | one row per (match, player, rune type) from the aggregate `runes` map — `rune_count` per type | `(match_id, player_slot, rune_key)` |
| `fact_match_player_damage` | 1,351,389 | one row per (match, player, target) from `damage` object — target categorized Hero/Building/Creep/Neutral/Ward/Other | `(match_id, player_slot, target_key)` |
| `fact_match_player_damage_taken` | 936,459 | one row per (match, player, source) from `damage_taken` (raw, pre-mitigation) | `(match_id, player_slot, source_key)` |
| `fact_match_team_minute` | 250,640 | one row per (match, side, minute) — team gold/xp summed from `fact_match_player_minute` | `(match_id, side, minute)` |
| `fact_hero_side` | 255 | one row per (hero, side) — precomputed picks/wins/win rate for foldable Draft tables | `(hero_id, side)` |
| `fact_hero_matchup_stats` | 14,462 | one row per matchup label — precomputed games + radiant/dire win rates | `matchup_label` |

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
has (2 of 4,299 matches are recorded draws with `radiant_win` null; 29 matches
have no team on either side).

#### fact_match_players / fact_picks_bans / fact_teamfights

Same columns as the matching `stg_*` tables (see silver reference above).
`hero_id = 0` in `fact_match_players` resolves to the Unknown hero row in
`dim_hero`.

`fact_match_players` carries `team_win` (inherited from silver) so a hero's or
player's win rate can be computed from the fact alone (no cross-table DAX):

```dax
HeroPicks   = COUNTROWS(fact_match_players)
HeroWins    = CALCULATE(COUNTROWS(fact_match_players), fact_match_players[team_win])
HeroWinRate = DIVIDE([HeroWins], [HeroPicks])
```

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

#### fact_teamfight_ability_uses

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

Note: `fact_teamfight_ability_uses` is the only remaining teamfight child fact —
`fact_teamfight_item_uses` and `fact_teamfight_kills` were **pruned in Round 16**
(no visuals used them; §5t). The parent `fact_teamfight_players` still carries
the `item_uses` / `killed` maps as text.

#### dim_patch (patch decode) *(round 1)*

| Column | Type | Notes |
|--------|------|-------|
| `patch_id` | text | OpenDota numeric patch id (joins `fact_matches.patch`) |
| `patch_name` | text | e.g. `7.37` |
| `patch_date` | date | patch release date |
| `sort_order` | integer | chronological ordering for the chart axis |

#### dim_item (item decode) *(round 2)*

| Column | Type | Notes |
|--------|------|-------|
| `item_id` | text | numeric id as stored in `fact_match_players.item_0..6` |
| `item_internal_name` | text | e.g. `item_blink` |
| `item_name` | text | display name; coalesces to internal name for recipes / `ability_base` |

#### fact_hero_matchups / fact_hero_matchups_hero / fact_team_h2h *(round 1)*

- `fact_hero_matchups`: `match_id`, `radiant_hero_id`, `dire_hero_id`,
  `matchup_label` (`"Radiant vs Dire"` display text so the matchups table needs
  no `USERELATIONSHIP`), `radiant_win`. Excludes draw matches (`radiant_win`
  null).
- `fact_hero_matchups_hero`: same matchups unfolded per hero side — `match_id`,
  `hero_id`, `opponent_id`, `matchup_label`, `hero_win`.
- `fact_team_h2h`: `match_id`, `team_a_id`, `team_b_id`, `team_a_win`,
  `team_a_score`, `team_b_score`.

#### fact_phase_momentum *(rounds 4–5)*

Per (match, team, fight phase): `fight_phase` (`pre-game`/`early (0-20m)`/`mid
(20-40m)`/`late (40m+)`), `phase_ord`, `gold_delta`, `xp_delta`, `deaths`,
`fights`, `radiant_win`, `duration_min`, `team_win`. (Built by dbt but **not
imported into Power BI** — `fact_match_timeline`, `fact_match_timeline_events`,
and `fact_team_compositions` were pruned in Round 16, §5t.)

#### fact_match_player_minute (per-minute progression) *(round 6)*

One row per (match, player, minute). Flattens the raw per-player `times` /
`gold_t` / `xp_t` / `lh_t` / `dn_t` arrays (one sample per minute) via
`stg_match_player_minute`; `level` is derived from cumulative `xp` against the
`xp_level` constant thresholds.

| Column | Type | Notes |
|--------|------|-------|
| `match_id` | text | FK to fact_matches |
| `player_slot` | text | |
| `account_id` | text | FK to dim_player |
| `hero_id` | text | FK to dim_hero |
| `side` | text | `Radiant` / `Dire` |
| `minute` | integer | `time_sec / 60` |
| `time_sec` | numeric | seconds elapsed into the match |
| `gold` | integer | cumulative gold earned |
| `xp` | integer | cumulative XP |
| `level` | integer | derived from XP thresholds |
| `last_hits` / `denies` | integer | |
| `player_name` / `hero_localized_name` | text | denormalized |

Only players with **all 5 arrays** present (3,060 of 4,299 matches). No
`dim_match_minute` link.

#### fact_match_player_skills (skill levelling) *(rounds 6–7)*

One row per (match, player, upgrade). Flattens `ability_upgrades_arr`; `minute`
is **approximate** — the first minute the player's derived level reached
`upgrade_index + 1` (no timestamps exist in the source).

| Column | Type | Notes |
|--------|------|-------|
| `match_id` | text | FK to fact_matches |
| `player_slot` | text | |
| `account_id` | text | FK to dim_player |
| `hero_id` | text | FK to dim_hero |
| `side` | text | |
| `upgrade_index` | bigint | learning order (0 = first) |
| `ability_id` | text | raw id |
| `ability_internal_name` | text | decoded via constants `ability_ids` |
| `ability_name` | text | display name via `abilities`; **talents (round 11c)** have the `+{s:…}` value template stripped → e.g. `Reflection Duration`, and `attribute_bonus`/`special_bonus_attributes` → `Attribute Bonus` |
| `is_talent` | boolean | true when the upgrade is a talent-tree pick (`special_bonus*` or `attribute_bonus`) |
| `minute` | integer | approximate learn minute (no dimension) |
| `learn_level` | bigint | player level at upgrade (`upgrade_index + 1`) |
| `player_name` / `hero_localized_name` | text | denormalized |

239 of 3,164 skill matches have no per-minute data in the raw payload, so their
rows fall to minute 0 (pre-existing source limitation).

#### fact_match_player_item_purchases (itemization) *(round 7)*

One row per purchase event (minute, player, hero, item). Flattens the per-player
`purchase_log` array (`{"key": <item_internal_name>, "time": <seconds>}`);
negative times (pre-game starting items) clamp to minute 0.

| Column | Type | Notes |
|--------|------|-------|
| `match_id` | text | FK to fact_matches |
| `player_slot` | text | |
| `account_id` | text | FK to dim_player |
| `hero_id` | text | FK to dim_hero |
| `side` | text | |
| `purchase_index` | bigint | ordinal within the player's purchase_log |
| `item_internal_name` | text | source key |
| `time_sec` | integer | raw seconds (negative = pre-game) |
| `minute` | integer | clamped to 0 (no dimension) |
| `item_name` | text | display name via `dim_item.item_internal_name` (unmatched keep internal name) |
| `player_name` / `hero_localized_name` | text | denormalized |

3,285 matches with purchase data. (Round 8 used this to restrict the Match
Detail match dropdown; Round 9 reverted that — the slicer now binds to
`fact_matches.match_id` and lists **all 4,299 matches**, with hero slicers
scoped to the selected match via the `Hero in Current Match` measure + visual
filter. See §5j.)

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
  DirectQuery query folding (error 10682 - see [`docs/power_bi_setup.md`](power_bi_setup.md) §8).
  Parsing back with `::jsonb` happens in downstream SQL where needed.
- **Gold (presentation):** shaped *for the BI tool*. Star schema, dims/facts,
  decode tables, and **detail / bridge tables** materialized specifically so
  Power BI can slice and pivot without parsing JSON.

This is why nested maps (e.g. `ability_uses` in `stg_teamfights`) are flattened
into child facts (`fact_teamfight_ability_uses` — and formerly
`fact_teamfight_item_uses` / `fact_teamfight_kills`, pruned Round 16) at
**gold**, not silver: silver owns the canonical record
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

Indexes are created by **dbt post_hooks in each model** (named
`gold_<table>_<col>_idx`, dropped + recreated on rebuild). **Silver tables have
no DB-level indexes** (except PKs) — Round 15/16 removed them; the silver stage
is scanned once per full build, so extra indexes only slowed writes.

Gold fact tables (current as of Round 16; see each model's post_hook):

- `fact_matches`: match_id, leagueid, patch, start_date, game_mode_id,
  lobby_type_id, region_id, radiant_team_id, dire_team_id (9 indexes — the
  column-level ones support the Dashboard/Overview slicers)
- `fact_team_matches`: match_id, team_id, side
- `fact_match_players`: match_id, account_id, hero_id
- `fact_picks_bans`: match_id, hero_id
- `fact_teamfights`: match_id
- `fact_teamfight_players`: match_id, hero_id, account_id
- `fact_hero_matchups`: match_id, radiant_hero_id, dire_hero_id;
  `fact_hero_matchups_hero`: match_id, hero_id, opponent_id;
  `fact_team_h2h`: match_id, team_a_id, team_b_id;
  `fact_hero_side`: hero_id, side; `fact_hero_matchup_stats`: matchup_label
- `fact_match_player_minute` / `_skills` / `_item_purchases` / `_runes` /
  `_damage` / `_damage_taken`: match_id, account_id, hero_id
- `fact_match_team_minute`: match_id
- `fact_phase_momentum`: match_id, team_number, fight_phase
