# Report Improvements — Detailed Implementation Spec

Companion to `report_status.md`. This is the working spec for the improvement
list agreed 2026-08-05: for every idea it gives the goal, the exact data it
needs, how to implement it (SQL / DAX / JSON), where it lands in the report,
effort, risk, and dependencies.

Status per item is tracked with checkboxes. Items marked **[DONE]** are already
implemented.

---

## Tier 1 — Build the data first (unlocks most other items)

These are dbt gold-layer models + semantic-model wiring. They don't change any
existing visual and are additive, so they are low-risk and unblock everything
in Tier 2/3.

### 1.1 `dim_patch` — patch filter & ordering **[DONE]**

- **Goal**: a real patch dimension so the Matches page can filter by patch
  (currently `patch` is a raw OpenDota numeric id with no decode and no
  sortable order).
- **Data**: `bronze.constants` resource `patch` (id/date/name array) + distinct
  `fact_matches.patch` values for anything not in constants.
- **Model** `transform/models/gold/dim_patch.sql`:
  - `patch_id` (text, matches `fact_matches.patch`), `patch_name` (e.g. `7.34`),
    `patch_date`, `sort_order` (use the constant `id`, which is chronological).
  - Include an `Unknown` row for any match patch with no decode.
- **Tests**: `patch_id` not_null/unique; relationship from `fact_matches.patch`.
- **Semantic model**: new table `gold dim_patch` + relationship
  `fact_matches.patch ↔ dim_patch.patch_id` (single, active).
- **Report use**: Patch slicer on Matches page; "Matches by patch" chart can be
  sorted by `sort_order` instead of the raw id.

### 1.2 `fact_hero_matchups` — hero-vs-hero analysis **[DONE]**

- **Goal**: "hero A vs hero B" matchup matrix. Two `hero_id` values per
  observation can't be done live in DirectQuery, so it must be a precomputed
  fact.
- **Data**: `fact_matches` × `fact_match_players` twice (radiant players × dire
  players).
- **Model** `transform/models/gold/fact_hero_matchups.sql`:
  - One row per (match, radiant hero, dire hero) = 25 rows per match.
  - Columns: `match_id`, `radiant_hero_id`, `dire_hero_id`, `radiant_win`.
  - Exclude `hero_id = '0'` (Unknown) on both sides so the fact stays clean.
  - Indexes on `match_id`, `radiant_hero_id`, `dire_hero_id`.
- **Tests**: relationships for both hero ids → `dim_hero`, match_id → fact_matches.
- **Semantic model**: new table + measures (`Matchup Count`, `Radiant Hero
  Wins`, `Radiant Hero Win Rate`). Relationships: `radiant_hero_id → dim_hero`
  (active), `dire_hero_id → dim_hero` (**inactive**, mirror of
  `victim_hero_id`), `match_id → fact_matches`.
- **Report use**: matrix rows = hero (active path), columns = hero (via
  `USERELATIONSHIP`), value = win rate of the row-hero. See §3.3 for the DAX.
- **Volume**: 4,299 matches × 25 ≈ 107k rows — trivial for DirectQuery.

### 1.3 `fact_team_h2h` — team head-to-head **[DONE]**

- **Goal**: "Team X vs Team Y all-time record".
- **Data**: `fact_matches` where `has_radiant_team` and `has_dire_team` (4,222).
- **Model** `transform/models/gold/fact_team_h2h.sql`:
  - One row per match, canonical pair ordering (`team_a_id < team_b_id` so each
    pair appears once).
  - Columns: `match_id`, `team_a_id`, `team_b_id`, `team_a_win`,
    `team_a_score`, `team_b_score`.
  - `team_a_win` = `radiant_win` when radiant is the A side, else `not radiant_win`.
  - Indexes on `match_id`, `team_a_id`, `team_b_id`.
- **Tests**: relationships for both team ids → `dim_team`, match_id → fact_matches.
- **Semantic model**: new table + measures (`H2H Games`, `Team A Wins`,
  `Team A Win Rate`). Relationships: `team_a_id → dim_team` (active),
  `team_b_id → dim_team` (**inactive**), `match_id → fact_matches`.
- **Report use**: same matrix pattern as 1.2.

### 1.4 Fact-scoped measures for draft analytics **[DONE]**

- Add measures to `gold fact_picks_bans` so a draft page can show pick/ban
  rates: `Matches Drafted = DISTINCTCOUNT(match_id)`,
  `Pick Rate = DIVIDE([Draft Picks], [Matches Drafted])`,
  `Ban Rate = DIVIDE([Draft Bans], [Matches Drafted])`.

---

## Tier 2 — New pages / big features

### 2.1 Draft page (new) **[DONE]**

- **What**: picks/bans analytics. `fact_picks_bans` has 88,804 rows (every
  pick + ban with order, side, hero) and is the most underused table.
- **Visuals**:
  - Top 20 picks by hero (barChart, `dim_hero` + `[Draft Picks]`).
  - Top 20 bans by hero (barChart, `[Draft Bans]`).
  - Pick vs ban bar (clusteredBarChart, `dim_hero` + both measures).
  - Pick/ban by draft phase — needs `order_no` bucketed (`phase` = early/mid/
    late). Can be done with a DAX measure or a precomputed column in
    `fact_picks_bans` (precompute in dbt for consistency).
  - Radiant vs Dire draft tendencies: side + is_pick matrix.
- **Shipped 2026-08-05** as page `655dabd0` (1280×900): top picks / top bans /
  picks-vs-bans bars, **picks by draft phase** via `First/Mid/Late Picks`
  measures on `order_no` (no dbt column needed — order is text `'0'..'23'`,
  bucketed 0-7 / 8-15 / 16-23), draft activity by side, hero matchups table
  (`matchup_label`), team H2H table.

### 2.2 Hero matchup matrix (Hero Meta page)

- **What**: matrix of hero A (rows) vs hero B (columns) with A's win rate.
- **Data**: `fact_hero_matchups` (1.2).
- **DAX** (both relationships active/inactive on `dim_hero`):
  ```
  'Matchup Win Rate (A)' =
    DIVIDE(
      CALCULATE(
        COUNTROWS('gold fact_hero_matchups'),
        USERELATIONSHIP('gold fact_hero_matchups'[dire_hero_id], 'gold dim_hero'[hero_id])
      ),
      CALCULATE(
        COUNTROWS('gold fact_hero_matchups'),
        USERELATIONSHIP('gold fact_hero_matchups'[dire_hero_id], 'gold dim_hero'[hero_id])
      )
    )
  ```
  (The `USERELATIONSHIP` must activate the *column* path; the row hero flows
  through the active `radiant_hero_id` link.)
- **Alternative (simpler, recommended first)**: a "top opponents" table — pick
  a hero via slicer, list the 10 most common opposing heroes with matchup win
  rate. This only needs the active `radiant_hero_id` relationship and one
  measure: `Opponent Win Rate = DIVIDE(COUNTROWS(..., radiant_win),
  COUNTROWS(...))` with the dire hero as row category.
- **Effort**: low (table) to medium (matrix).

### 2.3 Team head-to-head (Teams page)

- Same pattern as 2.2 using `fact_team_h2h` (1.3). Start with "top rivals"
  table: pick a team via slicer, list most common opponents with record.
- **Effort**: low.

### 2.4 Player detail drill-through (Players page)

- **What**: click a player → per-hero record, KDA/GPM trend, role mix,
  side performance.
- **Implementation**: a drill-through page (page whose `page.json` has
  `isDrillthrough: true`) with a target field = `dim_player.account_id`.
  All visuals on it are clones of existing ones filtered to the drill target.
- **Effort**: medium (needs a new page folder + drillthrough config in
  `report.json` page settings). Drill-through pages are finicky to hand-edit;
  recommend building this one in PBI Desktop, then re-checking the JSON.

### 2.5 Economy / farming deep-dive (new or on Players) **[DONE]**

- `fact_match_players` has gpm/xpm/last_hits/denies/net_worth. Add a page or a
  section: GPM/XPM by hero, net-worth leaders, denies leaderboard, camps
  stacked / neutral kills.
- **Shipped 2026-08-05** as page `a535cc39` (1280×900): 7 stat cards (GPM,
  XPM, Net Worth, Last Hits, Denies, Stuns, Healing), top farm / last-hit
  leader bars, support impact by hero (healing + camps stacked), most common
  first items (via new `dim_item` decode), lobby-type donut, GPM/XPM trend.
  Rank donut dropped (no rank data).

### 2.6 About & Glossary page (new) **[DONE]**

- A documentation page: what the report is, what to expect, how to use it,
  a Dota-term glossary, and per-page descriptions of every visual.
- **Shipped 2026-08-05** as page `736e1272` (1280×1000). 11 textbox visuals
  built with the documented PBIP textbox format (`visualType: "textbox"`,
  `objects.general[].properties.paragraphs[]` / `textRuns`, visualContainer
  schema 2.4.0). **Gotcha:** textbox visuals must live in
  `visuals/<guid>/visual.json` folders like every other visual — a flat
  `visuals/<guid>.json` file is silently ignored by PBIR (page appears empty).

---

## Tier 3 — Detail adds on existing pages (no schema work)

### 3.1 Game-mode / lobby / region / league slicers everywhere

- `dim_game_mode`, `dim_lobby_type`, `dim_region`, `dim_league` exist and are
  already linked bidirectionally through `fact_matches`. Add slicers to pages
  that lack them (clone the role-slicer JSON, swap entity/property).
- **Effort**: very low. Each is a copy of `f1a4c6bd` (role slicer) with the
  `SourceRef.Entity` + `Property` + `queryRef`/`nativeQueryRef` changed.

### 3.2 Date-range slicer instead of year-only

- Replace the year list slicer with `dim_date.date` "Between" slicer (basic
  slicer JSON with `filterType: Basic`, `filter` set to a date range). Enables
  month-level ranges.

### 3.3 Top-opponents / top-rivals tables **[DONE]**

- See 2.2/2.3 "alternative" tables. Lowest-risk way to surface the matchup and
  H2H data.
- **Shipped 2026-08-05**: Draft page has the hero matchups table (via a
  precomputed `matchup_label` column — no `USERELATIONSHIP` needed) and the
  team head-to-head table.

### 3.4 First-blood / objectives analysis **[DONE]**

- `fact_matches.first_blood_time` exists. "First blood before 10 min → win
  rate": measure `FB before 10min win rate = CALCULATE(DIVIDE(COUNTROWS(
  fact_matches), ...), first_blood_time < 600)`. Stomp/close-game buckets via
  `radiant_score`-`dire_score` diff.
- **Shipped 2026-08-05**: Overview gained a **match-closeness donut**
  (`fact_matches.score_bucket` column: close/moderate/blowout/rout) plus cards
  for `Early First Blood Rate`, `Leaver Games` and `Avg Score Differential`.
- **Effort**: low.

### 3.5 Role-scoped hero stats (Hero Meta)

- `dim_hero.roles` is a text array on the dimension; `dim_hero_role` bridge
  exists (fixed in Fix 4). Use the Role slicer already on the page — it
  already filters the hero stats table. Just make sure the Hero stats table
  shows `hero_localized_name`, `match_*` measures and that the role slicer is
  adjacent.

### 3.6 Hero images & team logos in tables

- `dim_hero.img` and `dim_team.logo_url` are URL strings. Classic `table`
  visuals can render image URLs via a data-driven image column. In DirectQuery
  this works but each URL row adds a network round-trip. Keep to the top-N
  tables. **Test in Desktop before trusting the JSON** — image binding is not
  representable in the same way as text in the visual JSON.
- **Effort**: low-medium; recommend Desktop for this one.

---

## Tier 4 — UX & polish

### 4.1 Exclude "Unknown" teams/players by default

- The Team leaderboard lists thousands of "Unknown" rows; Players lists
  `player_name = null` rows. Add a **page-level filter** (page.json `filters`
  array) or clone the visual-level Advanced filter used on `a44d5e76`
  (`Not → Comparison(team_name, Literal "Unknown")`).
- **Effort**: low. High visual payoff.

### 4.2 Rich tooltips

- `report.json` settings already have `useEnhancedTooltips: true`. Add a
  `tooltipConfig` to selected visuals pointing at a tooltip page. Hand-editing
  tooltip pages is risky; do in Desktop.

### 4.3 Conditional formatting (leaderboards)

- Data-bars / color-scale on `Team Win Rate`, `Avg Score Differential`, hero
  win-rate columns. In JSON this is the `formatting` object of a visual — needs
  careful reference to a working example (grab one from Desktop first).
- **Effort**: medium.

### 4.4 Searchable slicers

- The slicer `search` property is undocumented (known issue §3.4). Do in
  Desktop: Slicer → format → "Search" on. Desktop will serialize it; then we
  can replicate.

### 4.5 Reset-all + page navigation buttons

- Add an "All pages" page with a button per page, or a nav-bar. Buttons are
  bookmarks/actions in JSON — high risk to hand-edit. Recommend Desktop, then
  verify JSON.

### 4.6 "Never summarize" hardening **[DONE]**

- Set `summarizeBy: none` on every key/ID column and on boolean flags
  (`radiant_win`, `team_win`, `is_pick`) so Power BI never tries to SUM an id
  or an average a boolean. Audited the model tables (2026-08-05); remaining
  numeric measure columns are already `summarizeBy: sum` and intentional.

---

## Tier 5 — Correctness / schema follow-ups

### 5.1 Wire `victim_hero_id` properly

- Currently inactive (known issue §3.7). With `fact_hero_matchups` (1.2)
  existing, most victim-analysis can be done on that fact instead. If
  teamfight-kill victim analysis is still wanted, add `USERELATIONSHIP`-based
  measures over `fact_teamfight_kills` mirroring §2.2.

### 5.2 Re-backup the database

- Newest dump (`gold3_20260802_223003.dump`) predates `fact_team_matches`.
  Take a fresh dump after the Tier 1 models land. Command (README §Backups):
  `pg_dump -U postgres -d dota -Fc -f backups/<name>.dump` (then re-dump after
  each dbt build).

### 5.3 Orchestrator

- bronze_load → dbt build → (optional) pg_dump. A simple `run.ps1` that runs
  the two steps and snapshots the dump. Out of report scope but cheap.

### 5.4 Decide the fate of the precomputed `match_*` columns

- They exist in gold (report_status §7) but are unimported. Option A: leave
  (current). Option B: delete from dbt models to reduce gold-table width and
  build time. Recommend Option A until an "all-time" table is actually wanted,
  then expose selectively.

---

## Effort / dependency map

| Item | Depends on | Effort | Risk |
|---|---|---|---|
| 1.1 dim_patch | — | S | None (additive) |
| 1.2 hero matchups | — | S | None |
| 1.3 team h2h | — | S | None |
| 1.4 draft measures | 1.1 n/a | S | None |
| 2.1 Draft page | 1.4 | M | Med (many visuals) | **DONE** |
| 2.2 Matchup matrix/table | 1.2 | S–M | Low (table) / Med (matrix) | table done |
| 2.3 Team H2H | 1.3 | S | Low | table done |
| 2.4 Player drill | — | M | High (drillthrough JSON) | |
| 2.5 Economy page | — | S | Low | **DONE** |
| 2.6 About & Glossary | — | S | Low (textbox layout gotcha) | **DONE** |
| 3.1 slicers | — | S | Low | |
| 3.2 date range | — | S | Low | |
| 3.3 top rivals | 1.2/1.3 | S | Low | **DONE** |
| 3.4 objectives | — | S | Low | **DONE** |
| 3.5 role stats | — | S | None |
| 3.6 images/logos | — | M | Med (Desktop) |
| 4.1 Unknown filters | — | S | Low |
| 4.2–4.5 tooltips/nav | — | M | High (Desktop) |
| 4.6 summarizeBy | — | S | None |
| 5.1 victim analysis | 1.2 | S–M | Low |
| 5.2 re-backup | 1.1–1.3 | S | None |
| 5.3 orchestrator | — | S | None |

Legend: S = small (< 1h), M = medium (1–3h), L = large (> 3h). Risk = risk of
breaking the pbip JSON / model by hand-editing.
