# Power BI Report — Status, Change Log & Known Issues

Status as of **2026-08-08**. This file is the running ledger for the report at
`.pbip/dota pipeline.Report` (PBIR format) and its semantic model at
`.pbip/dota pipeline.SemanticModel` (TMDL).

> **SAVEPOINT (2026-08-08):** Round 9 (§5j) is complete and **verified in Power
> BI Desktop**. The hero slicers on Match Detail now scope to the selected
> match via a measure + visual-level filter (Option 2). Everything below is
> committed and backed up — `backups/gold4_20260808_191856.dump` (see §5j).

- Model mode: **DirectQuery** → PostgreSQL `localhost:5432` / db `dota`, **gold** schema.
- PBIR version: `2.0.0`; visualContainer schema: **2.11.0** (report was imported at
  visual `1.8.95`, upgraded by Power BI Desktop re-saves); theme `CY24SU10`.
- Rule: **Power BI Desktop must be closed** while the JSON/TMDL files are edited,
  otherwise it overwrites the files on save.

---

## ▶ RESUME HERE — next session (what's left)

All rounds (1–9) are built and JSON/TMDL-validated (131 JSON files, 0 bad; model
= 30 tables, 53 relationships; Match Detail page validator 0 issues). Round 8
(§5h/§5i) and Round 9 (§5j) have both been opened in Power BI Desktop — the
Round 9 hero-slicer scoping is **verified working**. The Match Detail render
pass from the earlier RESUME block was completed as part of Round 8/9 user
testing.

Safe resume checklist:

1. Start Docker Desktop (PostgreSQL `postgres:16`, `localhost:5432`, db `dota`)
   — DirectQuery source. Keep Power BI Desktop **closed** while editing files.
2. Open `.pbip/dota pipeline.Report` in Power BI Desktop. On the **Match
   Detail** page expect: a **Radiant Hero** slicer over the left column and a
   **Dire Hero** slicer over the right column, each filtering **only its own
   side** (Radiant → Radiant players / itemization / skills; Dire → Dire
   players / itemization / skills); each hero slicer lists **only the heroes
   that appear in the currently selected match** (via the `Hero in Current
   Match` measure + visual-level filter, §5j); match dropdown bound to
   `fact_matches` (lists **all 4,299 matches** — the previous 3,285-match
   restriction was dropped when the slicer was re-bound, see §5i); player
   tables showing only player / hero / level / kills / deaths / assists / net
   worth (no team_win, GPM, XPM); the 4 per-minute progression tables
   (Itemization y=445, Skill levelling y=645) filtered by the match + side hero
   slicers; **no Play Axis**.
3. Confirm the model imported cleanly: 30 tables, 53 relationships (**3
   bidirectional** — see §5j for why the earlier skills-link change was not
   kept).
4. If a visual errors, note its GUID from its `visual.json`; do **not** let
   Desktop re-save over the hand-edited files without diffing first (§3.9).
5. A fresh `pg_dump` was taken at the Round 9 savepoint
   (`backups/gold4_20260808_191856.dump`, §5j); re-dump after any future
   round that changes the DB.

Full detail: §5g (Round 6), §5h (Round 7), §5i (Round 8), §5j (Round 9), and the
gold schema in `docs/data_model.md`.

---

## 1. Pages & visuals at a glance

| Page (id) | Key visuals |
|---|---|
| **Overview** (`50256b7314243dac109b`) | 9 cards, donut (win rate by side), region column chart, top-leagues bar, matches-per-month line, slicers |
| **Matches** (`136f0b59-59f9-4d46-9815-2c2c5c552ab2`) | total-kills-by-month, avg-duration line, matches-by-game-mode, matches-by-patch (**decoded names**, chronological), first-blood-time line, slicers (incl. **Patch** via `dim_patch`) |
| **Hero Meta** (`5995aa2f-890e-4dd1-bbfb-56148396a2b6`) | role slicer, year slicer, top heroes by win rate / picks (bars), **Hero stats table (tableEx `a408a2f7`)**, Picks vs Bans (barChart `fce86b13`) |
| **Players** (`cb9a7fde-3c5d-4449-9186-0175d103dd67`) | top players by KDA / picks (bars), player appearances by month, **Player leaderboard (tableEx `6516df28`, null names excluded)**, top-picks bar has blank-name exclusion (`a44d5e76`) |
| **Teams** (`baedb79c-f6fe-4143-a748-0c78bfe55ff9`) | appearances-by-side (barChart `17130a8d`), team win rate over time, top teams by appearances / win rate (bars), **Team leaderboard (tableEx `a33fb46e`, "Unknown" teams excluded)** |
| **Combat** (`56eca095-57e2-46f9-98ab-f5b23aed77d9`) | **Most killed heroes (tableEx `1f0e8ee1`)**, top abilities / items in teamfights (bars), avg fights per match, cards, slicers; **bottom-left block (2026-08-05):** avg damage & healing per fight, teamfights by game phase, buybacks in teamfights |
| **Economy** (`a535cc39-aabf-4e7d-aedb-4bdba9e40445`) | **NEW (2026-08-05, 1280×900)** — 7 stat cards (GPM/XPM/Net Worth/LH/Denies/Stuns/Healing), top farm leaders, top last-hit leaders, support impact by hero (healing + camps), most common first items (tableEx `58aeb46e`), matches by lobby type donut, GPM/XPM trend line |
| **Draft** (`655dabd0-cc4b-492e-a84d-f8e7a134a24d`) | **NEW (2026-08-05, 1280×900)** — top picks / top bans / picks-vs-bans bars, picks by draft phase (First/Mid/Late), draft activity by side, most common hero matchups (tableEx `c23c3aa8`), team head-to-head records (tableEx `173c2a3f`) |
| **About & Glossary** (`736e1272-e6f1-4d3e-9c53-21721b6d03c6`) | **NEW (2026-08-05, 1280×1000)** — 11 textboxes: what the report is / what to expect / how to use it, a Dota term glossary, and one description box per page listing every visual and what it shows |
| **Match Detail** (`9d4f2e1a-8b3c-47d5-a6f7-8c9d0e1f2a3b`) | **NEW (2026-08-06)** — dropdown slicer on `match_id`, 3 cards (Winner / Duration / Total Kills), Radiant + Dire player tables (player, hero, team result, KDA, GPM/XPM, net worth, top skills, 6 items). See §5e. **Round 6:** independent Radiant/Dire hero + kind slicers + two Play Axis visuals — **report layer complete (2026-08-08)**, see §5g. **Round 7 (2026-08-08):** timeline tables replaced by 4 per-minute progression tables (Radiant/Dire **itemization over time** + Radiant/Dire **skill levelling over time**), `kind` column + kind slicers removed, match slicer restricted to matches with progression data (3,285), hero slicers now reach the progression tables, Play Axis re-wired to a shared `dim_match_minute` so scrubbing drives the progression tables — see §5h. **Round 8 (2026-08-08):** Play Axis removed; hero slicers titled & side-scoped (Radiant → Radiant tables only, Dire → Dire tables only); player tables trimmed to player / hero / level / K / D / A / net worth (team_win, GPM, XPM dropped); progression tables filter via match + side hero slicers — see §5i. **Round 9 (2026-08-08, §5j):** hero slicers now scope to the selected match via the `Hero in Current Match` measure + visual-level filter (**verified in Desktop**). |

131 report JSON files, all parse cleanly (validated 2026-08-08).

---

## 2. What works (verified)

- All **6 original pages** render; all 4 original `tableEx` tables display (see
  §5 fix 3). **Economy + Draft are new (2026-08-05)** — JSON-validated and
  bounds-checked but not yet opened in Desktop.
- **Role slicer on Hero Meta filters the whole page** — heroes, tables, charts
  (see §5 fix 4).
- **Year / league / region / game-mode / lobby slicers** cross-filter the report
  (the two `fact_matches ↔ fact*` links are bidirectional; slicers attached to
  leaf facts reach the hub).
- Hero / player / team **win rates computed from the matches themselves**
  (`fact_match_players[team_win]`), so they respond to all slicers.
- Leaderboard tables use **measures** (filter-responsive), not static columns.
- Top-picks bar excludes blank player names via a visual-level Advanced filter.
- Team / Player leaderboards exclude "Unknown" teams / null player names
  (2026-08-05).
- Matches page has a **Patch slicer** (`dim_patch`) and the patch chart shows
  decoded version names in chronological order (2026-08-05).
- **New Economy and Draft pages** (1280×900) with farm/support/items data and
  draft/picks-bans/matchup/H2H data respectively (2026-08-05). See §5c.
- **New About & Glossary page** (1280×1000, 11 textboxes) documenting the report,
  the Dota terms used, and every visual per page (2026-08-05). See §5d.
- **Match Detail hero slicers scope to the selected match** — Radiant/Dire
  hero slicers list only the match's heroes via the `Hero in Current Match`
  measure + visual-level filter (Round 9, §5j; **verified in Desktop**).
- All **53 relationships** validate (types are text at the schema level): 35
  through §5c, plus the round 4/5 timeline / matchup / composition links and the
  round 6/7 per-minute fact links (§5g/§5h).

---

## 3. Known issues & limitations

1. **DirectQuery calculated columns are intra-row only.** They cannot aggregate
   across tables (`CALCULATE`/`SUM`/`AVERAGE` over related facts are not
   supported). Any "column" that needs per-entity aggregates must be precomputed
   in the **dbt gold layer** or stay a measure. This is why the leaderboards use
   measures (see §4).
2. **Precomputed gold columns are NOT filter-responsive.** Columns such as
   `match_picks` / `match_win_rate` are all-time snapshots — a Year/League slicer
   changes *which rows are listed* but never re-aggregates the values. Use them
   only for fixed "all-time" tables, never for slicer-reactive ones.
3. **`tableEx` (the new table/matrix visual) is fragile in DirectQuery.** See
   §5 fix 3 for the exact crash and the normalization that fixed it. If a table
   regresses, the safe fallback is the classic `table` visual.
4. **Slicer `search` property remains undocumented** — no reference found for the
   JSON property that enables the search box on a slicer. Low priority.
5. **`dim_team` has 21,888 rows, mostly "Unknown" teams** (team ids seen in
   matches but not in `/teams`). The Team leaderboard now filters these out
   (2026-08-05); other team visuals (slicers, charts) may still show them.
6. **`dim_player` contains match-only participants with `player_name = null`**
   (no OpenDota name). Players visuals rely on blank-exclusion filters — the
   leaderboard table now has one (2026-08-05), the top-picks bar already did.
7. **`victim_hero_id → dim_hero` is an inactive relationship** in the model
   (only one active link per pair). Slicing a hero on kill events only filters
   kills where the hero is the *killer*; victim-side analysis would need
   `USERELATIONSHIP` or a second relationship trick. The new
   `fact_hero_matchups` covers most matchup use-cases instead (its `dire_hero_id`
   link is also inactive, same caveat applies).
8. **Staleness.** The gold layer is a dbt build; new matches appear only after
   `dbt run` and a report refresh. No scheduler yet.
9. **Report files are hand-edited** (visual.json / TMDL). PBI Desktop re-saves
   can rewrite/upgrade them (it upgraded 2.2.0 → 2.11.0 schemas), so re-check the
   diff after opening/saving in Desktop.
10. **New "second-dimension" links are inactive by design.** `dire_hero_id`,
    `team_b_id` (and `victim_hero_id`) each need `USERELATIONSHIP` in a measure
    to filter — DirectQuery supports only one active relationship per pair.
11. **Backups are stale → refreshed at the Round 9 savepoint.** The newest dump
    is now **`gold4_20260808_191856.dump`** (290 MB, taken 2026-08-08 after all
    rounds 4–9, §5j). The older `gold3_20260802_223003.dump` predates everything
    added since rounds 4–7: `dim_patch`, `dim_item`, `fact_hero_matchups`,
    `fact_team_h2h`, `fact_match_timeline(_events)`, `fact_phase_momentum`,
    `fact_team_compositions`, and the per-minute facts
    (`fact_match_player_minute`, `fact_match_player_skills`,
    `fact_match_player_item_purchases`, `dim_match_minute`). Re-dump after any
    future round that changes the DB.
12. **No rank data.** `dim_player.rank_tier` is empty for every player (the
    source matches/players never carry rank), so a rank-distribution visual is
    impossible. The Economy page uses a lobby-type donut instead.
13. **`fact_teamfights` has 40 `pre-game` fights** with negative `start_time`
    (OpenDota artifact). They show in the fight-phase chart as `pre-game`;
    harmless but visible.

---

## 4. Design constraints that shape the report

- **Everything is DirectQuery.** No import, no calculated columns with
  aggregates, no jsonb columns in the model (jsonb breaks query folding → error
  10682, fixed 2026-08-04 at the silver stage).
- **Aggregations live in measures** (over the fact tables) **or as precomputed
  dbt columns** (fixed snapshots). Measures are preferred for anything that must
  respect slicers.
- **Never read `bronze` JSON from a gold model** — always go through an
  **incremental silver** staging model (keyed on `match_id`) so the expensive
  `jsonb_array_elements` unnest runs once per newly loaded match, not on every
  rebuild. This is the project's established pattern (`stg_matches`,
  `stg_match_players`, and the new `stg_match_player_minute` /
  `stg_match_player_skills`) and is what keeps rebuilds fast as matches grow.
- **Avoid correlated subqueries against large tables in dbt models.** A per-row
  `SELECT ... WHERE level >= k` scan against a 1.25M-row CTE is O(N×M) and hung
  the skills build for 10+ min. Rewrote it to pure hash joins (grouped
  per-level table + `row_number()` for the fallback) — seconds instead.
- **dbt prints no mid-query progress** (only at step completion), and Postgres
  exposes no row-level progress for a plain `SELECT`/`CREATE TABLE AS`. Long
  builds look frozen; verify liveness with `pg_stat_activity` (see §5g), not by
  killing the process.
- **Team dimension** is reached only through the `fact_team_matches` bridge
  (one row per match + side) — single active path, no `USERELATIONSHIP`.
- Key/ID columns are **text** everywhere in gold so relationships validate.

---

## 5. Change log — 2026-08-05 (report fixes)

### Fix 1 — two broken stacked bars → `barChart`
Symptom: two "stacked" bar visuals would not render (Hero Meta "Picks vs Bans
by hero" `fce86b13`, Teams "Appearances by side" `17130a8d`).
Fix: set `"visualType": "barChart"`. Verified rendering.

### Fix 2 — Players top-picks bar showed blank rows
Symptom: "Top players by picks" (`a44d5e76`) listed rows with no player name.
Fix: added a visual-level `filterConfig` Advanced filter
`Not → Comparison(player_name, Literal "null")`, `howCreated: User`. Verified.

### Fix 3 — tableEx tables crashed rendering (the big one)
Symptom: Power BI Desktop frown on every table visual:
```
JavaScript:TypeError: Cannot read properties of undefined (reading 'queryName')
at TableExColumnHierarchyNavigator.getColumnIndexFromQueryName
```
Root cause: the 4 `tableEx` visual files carried `"active": false` on every
**measure** projection plus `"isDefaultSort": true` — artifacts that Power BI
Desktop never writes for `tableEx`. An `active: false` projection is excluded
from the query result while the renderer still tries to bind it, so the column
lookup returned `undefined` and the visual crashed.
Fix: normalized all 4 files (`a408a2f7`, `6516df28`, `a33fb46e`, `1f0e8ee1`) to
the known-good serialization — removed the `active` flags and `isDefaultSort`,
kept all fields, measures and sorts. Verified rendering. Reference used: a real
working `tableEx` export (same 2.11.0 schema).

### Fix 4 — Role slicer did not filter anything (Hero Meta)
Symptom: selecting a Role had no effect anywhere on the page.
Root cause: `dim_hero_role ↔ dim_hero` is many-to-one and defaulted to
single-direction filtering (from `dim_hero` down to `dim_hero_role`), so a
filter on the bridge never reached `dim_hero` (and therefore nothing downstream).
Fix: `crossFilteringBehavior: bothDirections` on relationship
`87c19c42-382e-a62c-a2d4-ee6c1efd9cdc` in `relationships.tmdl`. Verified.

### Fix 5 — (not applied) precomputed columns stay out of the model
`dim_hero` / `dim_player` / `dim_team` were extended in dbt with precomputed
aggregate columns (`match_picks`, `match_win_rate`, `match_avg_*`, ...) to
potentially back the leaderboards with columns. After review this was **not**
wired into the report because the columns ignore slicers (Year/League would show
all-time numbers). The columns exist in the gold tables and dbt models but are
**not imported** by the semantic model (DirectQuery only imports declared
columns). They remain available if an all-time table is ever wanted. See §7.

### 5b. Feature pass — 2026-08-05 (draft/patch/matchup/H2H data)

This session added **data-layer foundations** + **report polish**. Full spec:
`docs/report_improvements.md`.

- **dbt (new gold models, all tested green):**
  - `dim_patch` (61 rows) — decodes OpenDota's numeric `patch` ids to real
    versions (`7.34`, `7.37`, ...), with `patch_date` and `sort_order`.
  - `fact_hero_matchups` (106,721 rows) — one row per (match, radiant hero,
    dire hero); enables hero-vs-hero matchup analysis.
  - `fact_team_h2h` (4,220 rows) — canonical team-pair fact with `team_a_win`,
    scores; enables team head-to-head records.
  - Both new facts exclude `radiant_win = null` (2 draw matches).
- **Semantic model (TMDL):** added tables `gold dim_patch`,
  `gold fact_hero_matchups`, `gold fact_team_h2h` with measures (`Matchup
  Count` / `Radiant Hero Win Rate`, `H2H Games` / `Team A Win Rate`) and 7 new
  relationships. The "second" hero/team link on each new fact is **inactive**
  (only one active link per pair allowed) — same pattern as `victim_hero_id`.
  Added draft measures to `gold fact_picks_bans`: `Matches Drafted`,
  `Pick Rate`, `Ban Rate`.
- **Report:**
  - Team leaderboard now filters out `team_name = 'Unknown'`.
  - Player leaderboard now filters out `player_name = null`.
  - New **Patch slicer** on the Matches page (`dim_patch.patch_name`).
  - "Matches by patch" chart now shows decoded patch names, sorted by
    `sort_order` (chronological) instead of raw ids.
- `summarizeBy: none` hardening was already complete on ID/boolean columns;
  score columns intentionally stay `summarizeBy: sum`.

**Not done this session (per spec):** rich tooltips, conditional formatting,
searchable slicers, draft page, matchup matrix visuals — deferred to Desktop
where the JSON is less risky (see `docs/report_improvements.md`).

### 5c. Round 2 — Economy + Draft pages, Combat/Overview enrichments (2026-08-05)

Full spec: `docs/report_improvements.md` (§2.1, §2.5, §3.4). Scope agreed with
the user: **two new pages + enrichments**, pure-measure / proven visual types
only, no Desktop jobs this round.

- **dbt (all green, 133 tests):**
  - `dim_item` (596 rows) — decodes `item_0..6` ids to display names via the
    `item_ids` + `items` constants. `item_name` coalesces to the internal name
    for recipes / `ability_base`. Relationship from `fact_match_players.item_0`.
  - `fact_matches.score_bucket` — closeness buckets (`close`/`moderate`/
    `blowout`/`rout`) from the kill differential.
  - `fact_teamfights.fight_phase` — `pre-game`/`early (0-20m)`/`mid (20-40m)`/
    `late (40m+)` from `start_time`.
  - `fact_hero_matchups.matchup_label` — `"Radiant vs Dire"` display column so
    the matchups table needs no `USERELATIONSHIP`.
- **Semantic model (TMDL):** new table `gold dim_item` + 1 relationship (35
  total). ~20 new measures across `fact_match_players` (Avg Net Worth / Last
  Hits / Denies / Stuns / Healing / Camps Stacked / Rune Pickups / Buybacks,
  Total First Bloods, Total Randoms, Leaver Picks), `fact_teamfight_players`
  (Avg Fight Damage/Healing, Total Fight Buybacks, Avg Gold/XP Swing),
  `fact_matches` (Avg Score Differential, Close Game Rate, Rout Rate, Early
  First Blood Rate, Leaver Games, Human Player Matches), `fact_picks_bans`
  (First/Mid/Late Picks). Added `score_bucket`, `fight_phase`, `matchup_label`
  columns to the model.
- **New page Economy** (`a535cc39`, 1280×900): 7 stat cards, farm/last-hit
  leader bars, support impact by hero, first-items table, lobby-type donut,
  GPM/XPM trend. (Rank donut was dropped — `dim_player.rank_tier` is empty
  everywhere in the source data.)
- **New page Draft** (`655dabd0`, 1280×900): top picks/bans, picks-vs-bans,
  picks by phase, side tendencies, hero matchups table, team H2H table.
- **Combat** gained 3 visuals in the free bottom-left block; **Overview** gained
  the match-closeness donut + Early FB / Leaver / Score-diff cards in the free
  bottom strip.
- All 90 report JSON files parse; all 64 unique visual query refs validated
  against the model; no visual overlaps; all new pages fit their canvases.

**Deferred (per agreed scope):** death-location heatmap (needs `deaths_pos` dbt
child), hero images / team logos + scatter (Desktop), team roster view, rank
distribution (no rank data exists).

### 5d. Round 3 — About & Glossary page + Desktop validation fixes (2026-08-05)

Scope agreed with the user: **a documentation page** describing the report, plus
fixing the two load/validation problems Desktop surfaced after Round 2.

- **Load fix 1 — UTF-8 BOM.** The 7 new Economy-page `visual.json` files were
  written with a UTF-8 BOM; Power BI requires BOM-less UTF-8. Stripped the BOM
  from all 7 (and verified zero BOMs project-wide). Symptom: Frown error
  "Only text with UTF8 encoding without BOM is supported".
- **Load fix 2 — duplicate measure.** The new `Avg Score Differential` in
  `fact_matches` collided with the existing `fact_team_matches` measure of the
  same name. Renamed the new one to **`Avg Score Differential (match)`** in
  TMDL and updated the Overview card's queryRef/Property/nativeQueryRef.
- **Broken Overview card.** "Avg Score Differential (match)" (right of Leaver
  Games) returned nothing — `AVERAGE(ABS(col1 - col2))` is a non-column
  aggregate that DirectQuery can't push. Rewrote with `AVERAGEX(...)` (the
  same iterator pattern the working `Total Match Kills` uses).
- **New page About & Glossary** (`736e1272`, 1280×1000, last in page order):
  11 textboxes — title; "what this report is / what to expect / how to use";
  a Dota glossary (Radiant/Dire, KDA, GPM/XPM, net worth, stuns, camps
  stacked, buybacks, teamfight/fight-phase, draft-phase, score buckets,
  matchups, lobby types, leavers); and 8 per-page boxes listing each visual
  and what it explains. Built with the documented PBIP textbox format
  (`visualType: "textbox"`, `objects.general[].properties.paragraphs[]`,
  `textRuns[].value/textStyle`, schema 2.4.0).
- **Layout gotcha fixed:** first version wrote visuals as flat
  `visuals/<guid>.json` files, which PBIR ignores (page looked empty). Moved
  them to the required `visuals/<guid>/visual.json` folders — same convention
  as every other page. 11/11 verified: name = folder, paragraphs present,
  no BOM, no overlaps, all inside the 1280×1000 canvas.

**Not yet Desktop-verified:** Economy/Draft rendering, the Overview card fix,
and the new About page text layout (Desktop must remain closed during edits;
visual correctness is by construction until the user re-opens).

### 5e. Round 4 — Match Detail page (2026-08-06)

A **Match Detail** drill page was built as the 10th page (`9d4f2e1a`, 1280×900,
last in page order). It lets the user pick a match and see everything about it:

- **Header:** dropdown slicer on `fact_match_players.match_id`, plus 3 cards on
  `fact_matches` — `Match Winner`, `Avg Match Duration (min)`, `Total Match
  Kills`.
- **Player tables (Radiant / Dire):** one `table` per side (classic table, the
  safe fallback per §3.3), each filtered by a visual-level Advanced filter on
  `fact_match_players.side`. Columns: **player name** (`dim_player.player_name`
  — added 2026-08-06), hero (`dim_hero.hero_localized_name`), **team_win**
  (replaced the static all-time `hero_win_rate` column, see below), level, K/D/A,
  GPM, XPM, net worth, top-3 skills, and the 6 item names.
- **Fight timeline (Radiant / Dire):** one `table` per side on
  `fact_match_timeline` filtered by `side`, sorted by `start_min` ascending —
  minute, gold swing, **XP swing (added 2026-08-06)**, deaths, top items and
  abilities used per teamfight.

**Fixes applied 2026-08-06 (all validated, 0 broken refs):**

1. **Player name was missing** — tables showed heroes but not who played them.
   Added `gold dim_player.player_name` via the existing
   `fact_match_players.account_id → dim_player` relationship.
2. **`hero_win_rate` was the static all-time snapshot** (see §3.2) — on a
   match-detail table it is not match-filtered and misleads. Replaced with the
   per-match boolean `fact_match_players.team_win`.
3. **Timeline showed gold but not XP** — added `xp_delta` (the column existed
   in the model but was not projected).
4. **Cards were 50px tall with titles** (cramped) — bumped to 70px and shifted
   the player tables down (y 65→85); timeline tables moved to y 400 with height
   480 so all 8 visuals still fit inside the 1280×900 canvas with no overlaps.
5. **Titles** updated to reflect the new columns
   ("Radiant/Dire - players, heroes, items & skills",
   "Radiant/Dire - gold/XP swing, items & skills over time").

**Relationships required by the page (all verified active/correct):**
`fact_match_players.match_id ↔ fact_matches` (bidirectional, so the slicer
reaches the cards + timeline), `fact_match_players.hero_id → dim_hero`,
`fact_match_players.account_id → dim_player`,
`fact_match_timeline.match_id → fact_matches` (single direction, filtered by the
match slicer via fact_matches).

**Not done / follow-ups:** no About-page box yet for this page (the About &
Glossary page still documents 9 pages); backfill is pending `dbt build` +
Desktop render pass (the gold `fact_match_timeline` table must be built and the
report re-opened to verify).

### 5f. Round 5 — Teams KPI, Economy/Draft slicers, About updates, Match Detail timeline (2026-08-07)

Requested fixes across several pages, all validated (parse + field refs +
bounds/overlap check, 0 issues on all 10 pages):

1. **Teams — win-rate KPI split by side.** New `clusteredColumnChart`
   (`b1d4e6f8`) on the Teams page: Category = `gold fact_team_matches.side`,
   Y = `Team Win Rate` measure. Shows Radiant vs Dire simultaneously and is
   cross-filtered by the team slicer. Teams page height grew 720 → 900 to make
   room (KPI at y=715, under the existing visuals which end at y=705).
2. **Economy — slicers.** Added 6 dropdown slicers (`aaaa0101`–`aaaa0106`):
   year, league, region, game mode, lobby type, patch. Page reflowed: cards
   h=95 @y=15, bars @y=197, bottom visuals @y=462 h=220, line @y=697 h=203.
3. **Draft — slicers.** Added the same 6 dropdown slicers (`aaaa0201`–`aaaa0206`)
   in the free top strip (@y=15), no reflow needed. Fixed a pre-existing overlap
   (table `173c2a3f` y 585→675) so all 13 visuals fit the 1280×1200 canvas.
4. **About & Glossary — Match Detail documented.** Added a third row of cards
   (page 736e1272 height 1000→1245): **Match Detail** card, **About** card, and a
   **"Match Detail terms"** glossary box (items, abilities, gold/XP delta,
   deaths). The glossary box in row 1 was already full, so new terms live in the
   new third-row box instead of being crammed in.
5. **Match Detail timeline rebuilt from `fact_match_timeline_events`.**
   - Root cause of the blank timeline: only ~3055/4299 matches have teamfight
     data in OpenDota (~29% legitimately empty); the old `fact_match_timeline`
     visual surfaced this as a blank table.
   - New gold model `fact_match_timeline_events.sql`: one row per
     (match, teamfight, player, item/ability use) — 885,599 rows. Items decoded
     to `dim_item.item_internal_name`; abilities keep internal names. Columns:
     match_id, teamfight_id, start_min, side, player_slot, account_id, hero_id,
     player_name, hero_localized_name, kind, name, uses, gold_delta, xp_delta,
     deaths. dbt build 208/208, 13/13 tests pass.
   - Timeline visuals 010/011 re-pointed at the new table with columns
     (start_min, player_name, hero_localized_name, kind, name, uses, gold_delta,
     xp_delta, deaths), sorted by start_min ASC.
   - Player tables 006/007 trimmed: removed `top_skills` + `item_0..5_name`
     (17 → 10 projections) — this data now comes from the timeline visuals.
6. **Post-edit fix:** the new slicer files were initially written with an empty
   `$schema` key (PowerShell expanded `$schema` when the generator ran as an
   inline here-string). Rewrote all 12 slicer JSONs via a Python file to restore
   `"$schema"`. Lesson: generate PBIR JSON via `.py` scripts, not PowerShell
   here-strings (also `ConvertFrom-Json` chokes on the empty key).

### 5g. Round 6 — Match Detail progression visuals (per-minute facts) — DONE (2026-08-08)

Feature (agreed with user): on the Match Detail page add **(a)** independent
Radiant/Dire hero slicers, **(b)** independent Radiant/Dire `kind` slicers, and
**(c)** two "drag-time-button" progression visuals (one per side) at the bottom
showing per-minute hero level / gold / skill progression vs time, driven by the
**Play Axis** AppSource custom visual (user's explicit pick, not a native
scrubber) and backed by new dbt per-minute fact tables.

**Research completed (both unknown PBIR shapes resolved):**

1. **`page.json` `visualInteractions`** (to make each Play Axis + slicer filter
   only its own side / stop cross-side filtering): shape is
   `"visualInteractions": [{"source": "<visual_name>", "target": "<visual_name>", "type": "NoFilter"}]`
   — one entry per (source, target) pair; `"type": "Filter"` also valid. Lives in
   each page's `page.json` next to `name`/`displayName`/`displayOption`.
2. **PBIR registration of a public (AppSource) custom visual:** `report.json`
   gets a top-level `"publicCustomVisuals": ["PBI_CV_16948668_E17D_454B_8664_2F2C470EA8C1"]`
   (GUID array) and the visual's `visualType` is that **same GUID**. No
   `resourcePackages` entry / bundled code needed — Desktop auto-resolves
   AppSource visuals by GUID. **Use the published GUID (no `_DEV` suffix)**;
   the PlayAxis `pbiviz.json` guid is `PBI_CV_16948668_E17D_454B_8664_2F2C470EA8C1_DEV`
   (dev-only). Play Axis name `playAxis`, displayName `Play Axis`, version 1.1.9,
   by Margarida Prozil. Its `capabilities.json`: a single `category` Grouping
   role (it plays one value, e.g. `minute`, and cross-filters other visuals);
   objects: `transitionSettings` (autoStart/loop/cumulative/timeInterval),
   `colorSelector`, `captionSettings`.

**Data-layer work (dbt) — the main body of this session:**

- **New silver models (incremental on `match_id`, so the expensive jsonb unnest
  only runs for newly loaded matches — fixes the "re-parse everything each
  build" scaling anti-pattern, matching the existing `stg_matches` /
  `stg_match_players` pattern):**
  - `stg_match_player_minute` — one row per (match, player, minute):
    match_id, player_slot, account_id, hero_id, side, time_sec, minute, gold,
    xp, last_hits, denies. Flattens the raw `times`/`gold_t`/`xp_t`/`lh_t`/`dn_t`
    arrays (same ordinality, one sample per minute; `times` holds seconds,
    `time_sec/60 = minute`). Only players with all 5 arrays.
  - `stg_match_player_skills` — one row per (match, player, upgrade_index):
    match_id, player_slot, account_id, hero_id, side, upgrade_index, ability_id.
    Flattens `ability_upgrades_arr` (flat ordered array, element index ==
    learning order, ids are numeric strings; no timestamps).
- **New gold models (materialized table, read silver — no bronze scan):**
  - `fact_match_player_minute` — silver + level derived from cumulative `xp`
    via the `xp_level` constant thresholds
    (`count(*) over thresholds <= xp`), + player_name/hero_localized_name
    denormalized from dim_player/dim_hero.
  - `fact_match_player_skills` — silver + ability ids decoded through
    constants `ability_ids` (id→internal name) then `abilities` (→dname, so
    talents render as "+40 Damage"); `minute` approximated as the first minute
    the player's derived level reached `upgrade_index + 1` (hash joins on a
    grouped per-level table — **no correlated subqueries**).
- **schema.yml** updated in both `silver/` and `gold/` (not_null, unique,
  relationships to dim_player/dim_hero/fact_matches, accepted_values side).
- **Verification of the data itself (read-only):**
  - `gold.fact_match_player_minute` (pre-backfill measurement) = **1,253,200
    rows, 3,060 distinct matches** — the rebuilt version (round 7) matches this
    count, now sourced from silver.
  - Skills estimate: ~31,600 players with the array × ~17 avg upgrades ≈
    **~535,000 rows**; all 152 sampled ability ids decode cleanly.
  - Level derivation verified: current-patch (v22) matches derive
    `level == reported level` for all 10 players; 2018-era (v21) matches
    under-report the final level (old XP curve) — upgrade order/names stay
    correct, minute is approximate.
  - `gold_t` = cumulative gold earned (gold_per_min × minutes ✓).

**Outcome (2026-08-08) — everything below is built & verified:**
- ✅ The one-time backfill ran to completion: `silver.stg_match_player_minute`
  (1,253,200 rows / **3,060 matches**), `silver.stg_match_player_skills`,
  `gold.fact_match_player_minute` (rebuilt **against silver**, verified — no
  longer reads bronze), `gold.fact_match_player_skills` (535,432 rows). dbt is
  now **41 models, 221 data tests**.
- ✅ Report layer complete (TMDL tables `gold fact_match_player_minute` /
  `gold fact_match_player_skills` + `relationships.tmdl` `ffff0001-*` /
  `ffff0002-*`, Play Axis `publicCustomVisuals`, 4 slicers + 2 Play Axis
  visuals, 70 `visualInteractions` entries) — see the report-layer bullet above.
- ⚠️ **Superseded by §5h (Round 7):** the timeline tables + `kind` slicers were
  later replaced by 4 per-minute progression tables, and the Play Axis was
  re-wired to scrub via `dim_match_minute` instead of
  `fact_match_player_minute.minute`. Only a **Power BI Desktop render pass**
  remains — see **RESUME HERE** at the top of this file.

---

### 5h. Round 7 — Match Detail restructure: per-minute itemization + skill tables (2026-08-08)

User feedback round (2026-08-08): the teamfight "items & abilities used over
time" tables (visuals 010/011) were not what was wanted, and the Play Axis did
nothing. New design agreed with user:

- **Two separate per-minute progression tables per side** (4 tables total) —
  **Itemization over time** and **Skill levelling over time** — replacing the
  two teamfight timeline tables. The `kind` column (Item/Ability) is gone
  everywhere (it distinguished the two kinds inside one table; now each kind
  has its own table).
- **Itemization granularity = item purchase events** (one row per purchase:
  minute, player, hero, item).
- **Play Axis drives the new progression tables** (scrubbing minute filters
  them).

**Data layer (dbt, built + verified):**
- `silver.stg_match_player_item_purchases` (incremental on `match_id`,
  unique `(match_id, player_slot, purchase_index)`) — flattens the raw
  per-player `purchase_log` array: each entry is `{"key": <item_internal_name>,
  "time": <seconds>}`; negative times are pre-game starting items, clamped to
  minute 0. **1,526,552 rows / 3,285 matches.**
- `gold.fact_match_player_item_purchases` — silver + item display name via
  `dim_item.item_internal_name` (unmatched keys keep the internal name; the
  100-match sample had 0 unmatched) + player_name / hero_localized_name
  denormalized. 12 columns, indexes on match_id / player_slot / minute.
- `gold.dim_match_minute` — minute dimension `generate_series(0, max(minute)
  across player_minute / skills / item_purchases)` = **0..140 (141 rows)** so
  the Play Axis has one shared minute to scrub both progression tables.
- `fact_match_player_skills` extended with denormalized `player_name` /
  `hero_localized_name` (for the skill tables) — rebuilt (535,432 rows).
- schema.yml updated (silver + gold). Builds: `dbt run` for the 3 new models
  (~10 min one-time flatten) + `fact_match_player_skills` (~4 min) — all PASS.

**Model layer (TMDL):**
- New tables `gold fact_match_player_item_purchases` and `gold dim_match_minute`
  (DirectQuery partitions → `gold` schema). `model.tmdl` refs + PBI_QueryOrder
  updated (30 tables now).
- Relationships added: item_purchases → fact_matches (match_id),
  → dim_hero (hero_id), → dim_player (account_id), → dim_match_minute (minute);
  skills → dim_match_minute (minute). GUIDs `ffff0003-*`, `ffff0002-*013`,
  `ffff0004-*`.

**Report layer (PBIR):**
- Deleted visuals 010/011 (timeline tables) + kind slicers 0003/0004.
- Created 4 table visuals `03f2e3d4-c5b6-4a03-8000-000000000001..004`:
  Itemization (minute, player, hero, item) + Skill levelling (minute, player,
  hero, ability, level), Rad at x=20 / Dir at x=650, y=445 + y=645, each with a
  `side` filterConfig (exact pattern of old 010).
- Match slicer 001 re-bound to `fact_match_player_item_purchases.match_id`
  → dropdown now lists only the **3,285 matches with progression data**.
- Hero slicers 0001/0002 widened (w=450, x=20/x=480) — they now cross-filter
  the player tables **and** all 4 progression tables (relationships
  hero_id → dim_hero exist on both facts).
- Play Axis 0005/0006 re-bound to `dim_match_minute.minute` (was
  `fact_match_player_minute.minute`), side filterConfig removed. Scrubbing now
  filters the 4 progression tables via the minute relationships.
- `page.json` `visualInteractions` regenerated: **32 NoFilter pairs**. Hero
  slicers allow filtering player tables + 4 progression tables; Play Axes allow
  filtering only the 4 progression tables (NoFilter → cards, player tables,
  slicers, match slicer — so scrubbing doesn't blank the match-level visuals).
  Cards / player tables / progression tables keep default cross-filter.

**Verified:** all 138 report JSON files parse (0 bad); Match Detail page
validator = 14 visuals, **0 issues**; other 3 pages 0 issues; full cross-check
0 issues (TMDL columns ↔ DB columns, relationships ↔ tables/columns, model.tmdl
refs, visual projections). Desktop render pass still required (manual).

**Known data nuance:** skill `minute` is approximated from the player's derived
level (round-6 design). 239 of 3,164 skill matches have **no** `player_minute`
data (raw payload lacks the per-minute arrays), so their skills all fall to
minute 0 — pre-existing, not a regression.

---

### 5i. Round 8 — Match Detail polish: side-scoped hero slicers, trimmed player tables, Play Axis removed (2026-08-08)

User feedback round on the Match Detail page. No dbt / model changes — report
layer (PBIR) only.

- **Hero slicers are now side-scoped.** The two `gold dim_hero.hero_localized_name`
  slicers (`02f2e3d4-…001` = **Radiant Hero**, `02f2e3d4-…002` = **Dire Hero**)
  gained titles and the Dire one was moved to x=650 to sit over its column.
  `page.json` `visualInteractions` rewritten (16 NoFilter pairs): the **Radiant
  Hero** slicer filters only the 3 Radiant tables (players `…006`, itemization
  `03…001`, skills `03…003`) and **NoFilters** the match slicer, 3 cards, the
  Dire player table, both Dire progression tables and the Dire hero slicer —
  and vice-versa for the **Dire Hero** slicer. They no longer leak across
  sides via the shared `dim_hero`.
- **Player tables simplified.** Both Radiant (`01f2e3d4-…006`) and Dire
  (`…007`) player tables now project only: `player_name`, `hero_localized_name`,
  `level`, `kills`, `deaths`, `assists`, `net_worth`. Removed `team_win`,
  `gold_per_min`, `xp_per_min`. Winner card untouched.
- **Play Axis removed.** Visuals `02f2e3d4-…005/…006` deleted and the
  `PBI_CV_16948668_…` entry removed from `report.json` `publicCustomVisuals`.
  `gold dim_match_minute` and its two `minute` relationships remain in the
  model but are no longer consumed by any visual. Page height 975 → 850.
- **Progression tables unchanged** (`03f2e3d4-…001..004`) — still minute /
  player / hero / item (or ability / learn level) per side. They are filtered
  by the match slicer (via `fact_match_player_item_purchases.match_id`) and by
  the side hero slicers, so they always show only the players visible in the
  matching-side player table.
- **Verified:** 131 report JSON files parse (0 bad); all 16
  `visualInteractions` refs point at existing visuals; Match Detail page has 12
  visuals. Desktop render pass still required (manual) — see **RESUME HERE**.

**Fix during user testing (2026-08-08):** the match_id slicer did **not**
filter the player/skill tables or the cards. Root cause: the progression-fact
`match_id` → `fact_matches` relationships
(`ffff0001/2/3-…-010` for `fact_match_player_minute` / `_skills` /
`_item_purchases`) were **single-direction**, so a filter applied to
`fact_match_player_item_purchases.match_id` (the many side) never propagated up
to `fact_matches` — only the two itemization tables (which read item_purchases
directly) reacted.

**First attempt — reverted (2026-08-08):** added `crossFilteringBehavior:
bothDirections` to those three relationships (the same pattern
`fact_match_players` / `fact_team_matches` already use). This made Power BI
Desktop **fail to open the report** with
`PFE_XL_USERELATIONSHIP_AMBIGUOUS_PATH`: *"There are ambiguous paths between
'gold fact_match_players' and 'gold dim_match_minute': …→'gold
fact_match_player_skills'→'gold dim_match_minute' and …→'gold
fact_match_player_item_purchases'→'gold dim_match_minute'"*. The three
bidirectional additions were **reverted** — the model is back to its
known-good graph (**53 relationships, 3 bidirectional**).

**Final fix — slicer re-bound (2026-08-08):** the Match Detail match_id slicer
(`01f2e3d4-…-001`) was re-bound from `fact_match_player_item_purchases.match_id`
(the many side) to **`fact_matches.match_id`** (the hub), so a single-direction
filter on the hub propagates down to every fact table. Verified: 53 relationships
(3 bidirectional), all 53 still map to real gold columns, all 131 report JSON
files parse. The slicer now filters the itemization tables, both player tables,
both skill tables and the cards with **no bidirectional match_id links**.
`dim_hero` (hero slicers) is intentionally not match-scoped. Trade-off: the
slicer dropdown now lists **all 4,299 matches** instead of the 3,285 that have
progression data; if the restriction is desired, add a `has_progression` flag on
`fact_matches` in dbt later.

**Hero-slicer scoping (2026-08-08):** the Radiant/Dire hero slicers
(`02f2e3d4-…-001/002`, bound to `dim_hero.hero_localized_name`) listed all 128
heroes because no `hero_id` filter path reached `dim_hero` from the match.
**First attempt — NOT kept (reverted):** making
**`fact_match_player_skills`.hero_id → `dim_hero`.hero_id**
(`ffff0002-…-011`) `crossFilteringBehavior: bothDirections` was evaluated but
**reverted** — the model keeps **3 bidirectional** relationships only (the two
`fact_* → fact_matches` match_id links plus `dim_hero_role ↔ dim_hero`).
**Final fix — Round 9 (§5j), verified in Desktop:** scoping now works via a
**measure + visual-level filter** on the hero slicers (`Hero in Current Match`
on `gold dim_hero`), so no `dim_hero` relationship change is needed at all.
See §5j.

### 5j. Round 9 — Hero slicers scoped to the selected match (Option 2: measure + visual filter) — DONE & VERIFIED (2026-08-08)

User confirmed in Power BI Desktop that the Round 9 fix works as expected —
the Match Detail **Radiant Hero / Dire Hero** slicers now list **only the
heroes that appear in the currently selected match** (all 128 heroes when no
match is selected). Report layer (PBIR) + semantic model (TMDL) only — **no
dbt changes, no relationship changes**.

**How it works (Option 2, chosen over the reverted bidirectional approach):**

1. **New measure `Hero in Current Match`** in `gold dim_hero` (`gold dim_hero.tmdl`):
   ```dax
   measure 'Hero in Current Match' = CALCULATE(COUNTROWS('gold fact_match_players'))
   ```
   Counts each hero's rows in `fact_match_players`. The match slicer
   (`fact_matches.match_id`) reaches `fact_match_players` through the existing
   bidirectional `match_id` relationship (`f6515265`), so in the context of a
   selected match the measure is `1` for the match's heroes and `0` for the
   rest. No `dim_hero` relationship had to be made bidirectional — the slicer
   stays bound to `dim_hero.hero_localized_name`.
2. **Visual-level Advanced filter** added to both hero slicer `visual.json`
   files (`filterConfig.filters[]`, `type: "Advanced"`,
   `[Hero in Current Match] > 0`, `howCreated: "User"`):
   - `.../02f2e3d4-…-000001/visual.json` (Radiant Hero)
   - `.../02f2e3d4-…-000002/visual.json` (Dire Hero)
   The filter serialization (measure container + `From`/`Where` with
   `ComparisonKind: 1`, right literal `0D`) follows the documented PBIR
   measure-filter pattern; the measure lives on `gold dim_hero`.

**Verified:**
- Power BI Desktop render pass: **both hero slicers list only the selected
  match's heroes; all heroes when nothing is selected** (user-confirmed).
- All **131 report JSON files parse** (0 bad); edited files are BOM-less.
- Model unchanged structurally: **30 tables, 53 relationships (3
  bidirectional)**.

**Savepoint (2026-08-08):** fresh `pg_dump` taken —
`backups/gold4_20260808_191856.dump` (290 MB, 147 TOC entries) — supersedes the
stale `gold3_20260802_223003.dump` (see §3.11). Git commit at this round = the
rollback point if anything regresses.

---

## 6. Working on the report (file map)

- Report visuals: `.pbip/dota pipeline.Report/definition/pages/<page>/visuals/<visual>/visual.json`
- Semantic model tables: `.pbip/dota pipeline.SemanticModel/definition/tables/<table>.tmdl`
- Relationships: `.pbip/dota pipeline.SemanticModel/definition/relationships.tmdl`
- Validate after editing (PowerShell):
  `Get-ChildItem ".pbip\dota pipeline.Report\definition" -Recurse -Filter "*.json" | ForEach-Object { Get-Content $_.FullName -Raw | ConvertFrom-Json | Out-Null }`
- Rebuild gold after any dbt change:
  `& .venv\Scripts\dbt.exe build --project-dir transform` then refresh in PBI Desktop.

---

## 7. Precomputed gold columns (built, currently unused)

Added to the dbt gold models (2026-08-05) but **not** exposed in Power BI:

- `dim_hero`: `match_picks`, `match_wins`, `match_win_rate`, `match_avg_kda`,
  `match_avg_gpm`, `match_avg_xpm`, `match_avg_hero_damage`,
  `match_avg_tower_damage`, `match_avg_hero_healing`, `match_avg_last_hits`,
  `match_avg_denies`, `match_avg_net_worth`, `match_avg_stuns`,
  `match_avg_level`, `match_total_kills`, `match_total_deaths`,
  `match_total_assists`, `match_firstbloods`, `match_draft_picks`,
  `match_draft_bans`
- `dim_player`: same `match_*` set as `dim_hero` (minus draft) plus
  `match_avg_rune_pickups`, `match_avg_buybacks`
- `dim_team`: `match_appearances`, `match_wins`, `match_losses`,
  `match_win_rate`, `match_avg_score`, `match_avg_opponent_score`,
  `match_avg_score_differential`, `match_total_score`

All are `coalesce`d to 0/blank so "Unknown" rows stay safe. They are **static
snapshots** — they ignore date/league/region slicers (see §3.2).

---

## 8. Roadmap / improvement ideas

Full detailed spec: **`docs/report_improvements.md`** (per-item goal, data
needed, SQL/DAX/JSON, effort, risk, status). High-level buckets:

- **Coverage**: ~~draft / picks-bans page~~ (Draft page shipped 2026-08-05),
  player detail drill, team head-to-head (tables shipped 2026-08-05), hero
  matchup matrix (`fact_hero_matchups` ready — the table shipped, the matrix
  still needs `USERELATIONSHIP` or Desktop), ~~report documentation~~ (About &
  Glossary page shipped 2026-08-05).
- **Depth**: patch dimension (`dim_patch` ready + slicer added), expose
  teamfight child facts, victim-hero analysis via matchups fact, rank
  distribution (blocked — no rank data).
- **Visuals**: switch fragile `tableEx` to classic `table`; add search slicers;
  better "Unknown" handling (leaderboards already filtered).
- **Ops**: orchestrator (bronze_load → dbt build), ~~backup cadence~~ (**fresh
  dump taken 2026-08-08 — `gold4_20260808_191856.dump`, §5j**), CI on the
  pbip JSON.
- **Next (this session's handover)**: Rounds 8 (§5h/§5i) and 9 (§5j) have been
  opened in Power BI Desktop and the Round 9 hero-slicer scoping is
  **verified working**. The report is at a **savepoint** — see **RESUME HERE**
  at the top of this file and §5j for the commit + fresh dump
  (`gold4_20260808_191856.dump`). Remaining backlog ideas are all below this
  line (orchestrator, matchup matrix, search slicers, etc.).
- **Round 6 (2026-08-07 → 2026-08-08, see §5g):** Match Detail progression
  visuals. dbt models are written (`stg_match_player_minute`,
  `stg_match_player_skills` incremental silver + `fact_match_player_minute`,
  `fact_match_player_skills` gold) and **the report layer is complete**
  (TMDL tables + relationships, `publicCustomVisuals`, 4 slicers, 2 Play Axis
  visuals, 70 `visualInteractions` entries — all JSON-validated). **Remaining:**
  run the ~13 min full dbt backfill, then re-open in Desktop for the final
  render-verify pass. Full resume instructions are in §5g.
- **Round 7 (2026-08-08, see §5h):** Match Detail restructure — timeline tables
  → 4 per-minute progression tables (itemization + skill levelling, per side),
  `kind` column/kind slicers removed, match slicer restricted to the 3,285
  matches with progression data, hero slicers reach the new tables, Play Axis
  re-wired via shared `dim_match_minute` (0..140) so scrubbing drives the
  progression tables. All dbt builds PASS (incl. new
  `stg_match_player_item_purchases` / `fact_match_player_item_purchases` /
  `dim_match_minute`), TMDL + relationships + interactions validated (0 issues).
  **Remaining:** Desktop render pass (manual) to verify the Play Axis actually
  scrubs and the 4 new tables render.
