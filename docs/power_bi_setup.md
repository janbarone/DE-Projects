# Power BI Setup - Gold Layer Mapping

How to map the `gold` tables in Power BI (Model view → Manage relationships),
with cardinalities and cross-filter direction. **Connect to `gold`, not silver** -
it is the presentation layer and every join below is verified by dbt
relationship tests, so Power BI will not hit validation errors.

## 1. Connect

Power BI Desktop → **Get data → PostgreSQL database**

- Server: `localhost`
- Port: `5432`
- Database: `dota`
- User / password: `postgres` / `postgres` (from `.env`)
- Advanced: load all 17 `gold.*` tables (9 dims + 8 facts).

If a relationship fails to validate, first check Power BI **auto-created**
relationships on import (tables share key column names) and **delete the
auto-created ones** before creating yours.

## 2. Create the relationships (27 total)

Power BI → **Model view → Manage relationships → New**. For each relationship:

- **Cardinality:** many-to-one (\*:1) by default; the ones marked (1:\*) are one-to-many.
- **Cross filter direction:** all Single. Default flows **Many→1**; the (1:\*) links flow **1→Many**.
- Tick **"Make this relationship active"** only for the active ones below.

### `fact_matches` → dimensions (many-to-one, *:1)

| From column | To table | To column | Active |
|-------------|----------|-----------|--------|
| `leagueid` | `dim_league` | `leagueid` | yes |
| `radiant_team_id` | `dim_team` | `team_id` | yes |
| `dire_team_id` | `dim_team` | `team_id` | **no (inactive)** |
| `game_mode_id` | `dim_game_mode` | `game_mode_id` | yes |
| `lobby_type_id` | `dim_lobby_type` | `lobby_type_id` | yes |
| `region_id` | `dim_region` | `region_id` | yes |
| `start_date` | `dim_date` | `date` | yes |

### `fact_matches` → child facts (one-to-many, 1:*)

| From column | To table | To column | Active |
|-------------|----------|-----------|--------|
| `match_id` | `fact_match_players` | `match_id` | yes |
| `match_id` | `fact_picks_bans` | `match_id` | yes |
| `match_id` | `fact_teamfights` | `match_id` | yes |

### `fact_match_players` → dimensions (many-to-one, *:1)

| From column | To table | To column | Active |
|-------------|----------|-----------|--------|
| `account_id` | `dim_player` | `account_id` | yes |
| `hero_id` | `dim_hero` | `hero_id` | yes |

### `fact_picks_bans` → dimension (many-to-one, *:1)

| From column | To table | To column | Active |
|-------------|----------|-----------|--------|
| `hero_id` | `dim_hero` | `hero_id` | yes |

### `dim_hero` → bridge (one-to-many, 1:*)

| From column | To table | To column | Active |
|-------------|----------|-----------|--------|
| `hero_id` | `dim_hero_role` | `hero_id` | yes |

### `fact_teamfight_players` → (many-to-one, *:1)

| From column | To table | To column | Active |
|-------------|----------|-----------|--------|
| `match_id` | `fact_matches` | `match_id` | yes |
| `hero_id` | `dim_hero` | `hero_id` | yes |
| `account_id` | `dim_player` | `account_id` | yes |

### `fact_teamfight_ability_uses` → (many-to-one, *:1)

| From column | To table | To column | Active |
|-------------|----------|-----------|--------|
| `match_id` | `fact_matches` | `match_id` | yes |
| `hero_id` | `dim_hero` | `hero_id` | yes |
| `account_id` | `dim_player` | `account_id` | yes |

### `fact_teamfight_item_uses` → (many-to-one, *:1)

| From column | To table | To column | Active |
|-------------|----------|-----------|--------|
| `match_id` | `fact_matches` | `match_id` | yes |
| `hero_id` | `dim_hero` | `hero_id` | yes |
| `account_id` | `dim_player` | `account_id` | yes |

### `fact_teamfight_kills` → (many-to-one, *:1)

| From column | To table | To column | Active |
|-------------|----------|-----------|--------|
| `match_id` | `fact_matches` | `match_id` | yes |
| `hero_id` | `dim_hero` | `hero_id` (killer) | yes |
| `account_id` | `dim_player` | `account_id` | yes |
| `victim_hero_id` | `dim_hero` | `hero_id` (victim) | yes |

**Exceptions to the default *:1 many-to-one:** the three `fact_matches` → child-fact
links and `dim_hero` → `dim_hero_role` are **one-to-many (1:*)**. All others are
many-to-one.

## 3. Cross-filter direction guidance

- All relationships are **Single**, filter flowing **Many→1** (and **1→Many** on
  the one-to-many links): selecting a league / team / player / hero / game mode /
  lobby / region filters the fact tables, but facts never filter the dimensions.
  In the model the arrow points from the dimension toward the fact table.
- The `dire_team_id` relationship is **inactive** — it carries no cross-filter;
  it only evaluates when called explicitly in DAX (see below).

## 4. Critical rule - the two team relationships

`fact_matches` connects to `dim_team` **twice** (radiant + dire side). Power BI
allows only **one active** relationship between two tables:

1. **`radiant_team_id` → active** — drives team filters/slicers
   (e.g. "team = Team Liquid" returns their radiant matches).
2. **`dire_team_id` → inactive** — evaluated only via `USERELATIONSHIP`:

```dax
DireMatches =
CALCULATE(
    COUNTROWS(fact_matches),
    USERELATIONSHIP(fact_matches[dire_team_id], dim_team[team_id])
)
```

To count all matches a team appeared in (either side):

```dax
TotalTeamMatches =
[radiant team measure] + [dire team measure]  // one active, one USERELATIONSHIP
```

## 5. If Power BI refuses a relationship (duplicate values / type mismatch)

Two known causes:

- **Duplicate values**: the gold keys are unique on the dimension side, so this
  should not happen. If it does: delete any Power BI **auto-created**
  relationship between the pair first (they share `match_id` / `hero_id` /
  `account_id` column names), then create yours.
- **"Unable to validate" on many pairs** (confirmed 2026-08-03): same-named
  key columns across tables import with inconsistent numeric types (e.g.
  `hero_id` decimal on one side, whole number on the other), so Power BI
  rejects the relationship.

**Resolved at the schema level (2026-08-04):** every gold key/ID column is now
**Text** natively in PostgreSQL — converted in the **silver** layer and inherited
by gold. This covers `match_id`, `teamfight_id`, `player_slot`, `hero_id`,
`victim_hero_id`, `account_id`, `team_id`, `leagueid`, `game_mode_id`,
`lobby_type_id`, `region_id`, `radiant_team_id`, `dire_team_id`. Measures stay
numeric, dates stay dates, booleans stay booleans. The Power Query "set keys to
Text" workaround from 2026-08-03 is **no longer required** — just re-import the
17 `gold.*` tables and all 27 relationships connect without error. After a
rebuild, re-import in Power BI (File → Refresh / re-run Get Data) rather than
relying on cached schemas.

## 6. Star-schema shape / data flow

```
                  dim_league (dim)
                       |
dim_player (dim) --+   |
dim_hero   (dim) --+--- fact_matches (fact/hub) ---- fact_match_players (fact)
                   |        |                         fact_picks_bans   (fact)
                   |        +------------------------- fact_teamfights  (fact)
dim_team (dim) ----+  (radiant active, dire inactive)
dim_game_mode (dim) --+
dim_lobby_type (dim) -+
dim_region (dim) -----+
```

- Dimensions (filter tables): `dim_league`, `dim_team`, `dim_player`,
  `dim_hero`, `dim_hero_role`, `dim_game_mode`, `dim_lobby_type`, `dim_region`, `dim_date`
- Fact tables (measure tables): `fact_matches`, `fact_match_players`,
  `fact_picks_bans`, `fact_teamfights`, `fact_teamfight_players`,
  `fact_teamfight_ability_uses`, `fact_teamfight_item_uses`, `fact_teamfight_kills`

Notes:
- `dim_hero_role` is a bridge for role filtering: select a role → filters heroes
  (via `dim_hero` 1 → many `dim_hero_role`).
- `fact_teamfight_players` links teamfights down to hero/player level (the
  players array is positionally ordered by slot, so hero/player resolve).
- `fact_teamfights` links only to `fact_matches` (teamfight-level rows
  themselves carry no hero id; use `fact_teamfight_players` for hero-level).
- `fact_teamfight_ability_uses` / `fact_teamfight_item_uses` /
  `fact_teamfight_kills` are child facts that flatten the per-player maps from
  `fact_teamfight_players` (ability_name/uses, item_name/uses, victim hero/kills).
  They link to `fact_matches`, `dim_hero`, and `dim_player` directly (not to
  `fact_teamfight_players`, whose key is composite) — so slicing a hero filters
  kills where that hero is killer (via `hero_id`) or victim (via `victim_hero_id`),
  or ability/item uses.

## 7. Useful starter measures

```dax
TotalMatches   = COUNTROWS(fact_matches)
TotalPicks     = COUNTROWS(fact_picks_bans)
TotalPlayers   = COUNTROWS(fact_match_players)
RadiantWinRate = DIVIDE(
                     CALCULATE(COUNTROWS(fact_matches), fact_matches[radiant_win]),
                     COUNTROWS(fact_matches)
                 )
AvgDuration    = AVERAGE(fact_matches[duration_sec])
```

Full column reference, types, and nuance notes: see `docs/data_model.md`.

## 8. DirectQuery + jsonb columns → error 10682 (fixed 2026-08-04)

**Symptom:** cross-filtering `fact_teamfights` from `fact_matches` (click a
`match_id` value) failed on the teamfights visual with:

```
Error fetching data for this visual
OLE DB or ODBC error: [Expression.Error] Local evaluation of Table.Join or
Table.NestedJoin with key equality comparers is not supported
```

(Microsoft.Data.Mashup.ErrorCode = 10682)

**Why it happened (root cause):** in DirectQuery mode Power BI may never
evaluate a join locally — every query must be pushed down to PostgreSQL as
native SQL (query folding). The `fact_teamfights.players` column is **jsonb**
in PostgreSQL, and it was the only column in the whole model with **no
`sourceProviderType`** in the model metadata. The moment a visual's column set
included that column, the PostgreSQL connector could no longer fold the query
(the join included) to SQL, so Power BI attempted to evaluate the join in the
mashup engine instead — which DirectQuery forbids → 10682.

Why only the visual with `match_id` + `players` failed: every cross-filter
query between the two tables already performs the join on `match_id`, and that
join folds fine on its own. The failure appeared only when the query also had
to carry the jsonb `players` column. Visuals using any other `fact_teamfights`
columns worked — which is why the relationship itself was never the problem.

**The fix — two layers:**

1. **Model fix (applied first, 2026-08-04):** remove jsonb columns from the
   DirectQuery model — delete the column definition *and* exclude it in the
   partition M query with a `Table.RemoveColumns` step (folds to a `SELECT`
   without the column), so native SQL never references jsonb:

   ```m
   let
       Source = PostgreSQL.Database("localhost", "dota"),
       gold_fact_teamfights = Source{[Schema="gold",Item="fact_teamfights"]}[Data],
       #"Removed Columns" = Table.RemoveColumns(gold_fact_teamfights,{"players"})
   in
       #"Removed Columns"
   ```

2. **Schema fix at the source (applied 2026-08-04):** every jsonb column in
   silver/gold is now **text** natively in PostgreSQL — cast at the **silver**
   stage (`->>` extraction instead of `->`), so gold inherits text and no
   model-side exclusions are needed. Downstream gold models that parse the
   payloads cast back with `::jsonb` internally (e.g. `jsonb_each_text(...::jsonb)`,
   `jsonb_array_elements(...::jsonb)`) — parsing happens in SQL, only the
   stored/published type is text.

   Columns converted (silver + gold, verified zero jsonb in `gold`):
   - `stg_teamfights.players` → `fact_teamfights.players`
   - `stg_heroes.roles` → `dim_hero.roles`
   - `fact_teamfight_players.ability_targets`, `ability_uses`, `deaths_pos`,
     `item_uses`, `killed`

**Rule going forward:** never bring jsonb columns into a DirectQuery model
(import mode tolerates them; DirectQuery breaks folding). Any new jsonb column
must be cast to **text at the silver stage** (or earlier) before it reaches
gold. Bronze stays raw jsonb by design — it is not connected to Power BI.

