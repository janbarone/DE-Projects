# Power BI Report — Status, Change Log & Known Issues

Status as of **2026-08-17**. This file is the running ledger for the report at
`.pbip/dota pipeline.Report` (PBIR format) and its semantic model at
`.pbip/dota pipeline.SemanticModel` (TMDL).

> **SAVEPOINT (2026-08-17):** Rounds 1–16 complete. Round 16 (§5t) pruned 8
> unused gold tables + their indexes/relationships (model 38 → **31 tables,
> 52 relationships**), added index hardening + `on-run-end: analyze`, and
> shipped the **Grand Report** page (all report pages merged on one 3840 px
> canvas, `scripts/build_grand_page.py`). The gold layer rebuilt green
> (227/227 PASS). Fresh dump —
> `backups/gold_20260817_161207.dump` (see §5t).

- Model mode: **DirectQuery** → PostgreSQL `localhost:5432` / db `dota`, **gold** schema.
- PBIR version: `2.0.0`; visualContainer schema: **2.11.0** (report was imported at
  visual `1.8.95`, upgraded by Power BI Desktop re-saves); theme `CY24SU10`.
- Rule: **Power BI Desktop must be closed** while the JSON/TMDL files are edited,
  otherwise it overwrites the files on save.

---

## ▶ RESUME HERE — next session (what's left)

All rounds (1–16) are built and JSON/TMDL-validated (290 report JSON files,
0 bad, 0 BOMs; model = 31 tables, 52 relationships, 3 bidirectional; Grand
Report page `--verify` = 474 field references all resolve). The gold layer was
rebuilt green on 2026-08-17 (`dbt build --select gold --threads 1`,
227/227 PASS) after the Round-16 pruning. The remaining backlog is report-level
verification in Power BI Desktop plus non-report work (matchup matrix via
USERELATIONSHIP, player drill-through — see §8).

Safe resume checklist:

1. Start Docker Desktop (PostgreSQL `postgres:16`, `localhost:5432`, db `dota`)
   — DirectQuery source. Keep Power BI Desktop **closed** while editing files.
   **Heavy dbt builds may OOM-kill Postgres on this machine (§4) — run them
   with `--threads 1`.**
2. Open `.pbip/dota pipeline.Report` in Power BI Desktop. The report now opens
   on the **Grand Report** page (landing page, `a1b2c3d4-…`, 3840×8517 px —
   every report page merged into chapters with a deduplicated global filter
   bar; rebuild with `python scripts/build_grand_page.py`). Everything from
   Rounds 8–15 is as previously verified: Match Detail hero slicers scoped to
   the selected match, 25-column player tables, per-minute progression tables,
   Combat Match ID slicer, Hero Meta Top-opponents table, searchable
   high-cardinality slicers.
3. Confirm the model imported cleanly: **31 tables, 52 relationships (3
   bidirectional)** — the Round-16 pruning removed 7 tables from the model
   (`fact_teamfight_item_uses`, `fact_teamfight_kills`,
   `fact_team_compositions`, `fact_match_timeline`,
   `fact_match_timeline_events`, `dim_match_minute`,
   `fact_match_player_kills`); `fact_match_player_damage_taken_type` was
   already out since Round 11d.
4. If a visual errors, note its GUID from its `visual.json`; do **not** let
   Desktop re-save over the hand-edited files without diffing first (§3.9).
5. A fresh `pg_dump` was taken at the Round 16 savepoint
   (`backups/gold_20260817_161207.dump`, §5t); re-dump after any future
   round that changes the DB (or run the pipeline's `--backup` step).

Full detail: §5g (Round 6), §5h (Round 7), §5i (Round 8), §5j (Round 9),
§5k (Round 10), §5l (Round 11), §5p (Round 12), §5q (Round 13), §5r (Round 14),
§5s (Round 15), §5t (Round 16), and the gold schema in `docs/data_model.md`.

---

## 1. Pages & visuals at a glance

| Page (id) | Key visuals |
|---|---|
| **Overview** (`50256b7314243dac109b`) | 9 cards, donut (win rate by side), region column chart, top-leagues bar, matches-per-month line, slicers |
| **Matches** (`136f0b59-59f9-4d46-9815-2c2c5c552ab2`) | total-kills-by-month, avg-duration line, matches-by-game-mode, matches-by-patch (**decoded names**, chronological), first-blood-time line, slicers (incl. **Patch** via `dim_patch`) |
| **Hero Meta** (`5995aa2f-890e-4dd1-bbfb-56148396a2b6`) | role slicer, year slicer, top heroes by win rate / picks (bars), **Hero stats table (tableEx `a408a2f7`)**, Picks vs Bans (barChart `fce86b13`) |
| **Players** (`cb9a7fde-3c5d-4449-9186-0175d103dd67`) | top players by KDA / picks (bars), player appearances by month, **Player leaderboard (tableEx `6516df28`, null names excluded)**, top-picks bar has blank-name exclusion (`a44d5e76`) |
| **Teams** (`baedb79c-f6fe-4143-a748-0c78bfe55ff9`) | appearances-by-side (barChart `17130a8d`), team win rate over time, top teams by appearances / win rate (bars), **Team leaderboard (tableEx `a33fb46e`, "Unknown" teams excluded)** |
| **Combat** (`56eca095-57e2-46f9-98ab-f5b23aed77d9`) | teamfight cards (Total Teamfights `d4f6758f`, Avg Fights per Match `27b1d136`), damage & healing per fight (avg/total charts `bca57bf0` / `a786e082`, hero + player slicers `2b9f3b80` / `dbc0270a`), Total Fight Buybacks, Avg Gold/XP Swing, **Match ID** slicer (`6e9cce4f` — added Round 14, §5r) |
| **Economy** (`a535cc39-aabf-4e7d-aedb-4bdba9e40445`) | **NEW (2026-08-05, 1280×900)** — 7 stat cards (GPM/XPM/Net Worth/LH/Denies/Stuns/Healing), top farm leaders, top last-hit leaders, support impact by hero (healing + camps), most common first items (tableEx `58aeb46e`), matches by lobby type donut, GPM/XPM trend line |
| **Draft** (`655dabd0-cc4b-492e-a84d-f8e7a134a24d`) | **NEW (2026-08-05, 1280×900)** — top picks / top bans / picks-vs-bans bars, picks by draft phase (First/Mid/Late), draft activity by side, most common hero matchups (tableEx `c23c3aa8`), team head-to-head records (tableEx `173c2a3f`) |
| **About & Glossary** (`736e1272-e6f1-4d3e-9c53-21721b6d03c6`) | **NEW (2026-08-05, 1280×1000)** — 11 textboxes: what the report is / what to expect / how to use it, a Dota term glossary, and one description box per page listing every visual and what it shows |
| **Match Detail** (`9d4f2e1a-8b3c-47d5-a6f7-8c9d0e1f2a3b`) | **NEW (2026-08-06)** — dropdown slicer on `match_id`, 3 cards (Winner / Duration / Total Kills), Radiant + Dire player tables (player, hero, team result, KDA, GPM/XPM, net worth, top skills, 6 items). See §5e. **Round 6:** independent Radiant/Dire hero + kind slicers + two Play Axis visuals — **report layer complete (2026-08-08)**, see §5g. **Round 7 (2026-08-08):** timeline tables replaced by 4 per-minute progression tables (Radiant/Dire **itemization over time** + Radiant/Dire **skill levelling over time**), `kind` column + kind slicers removed, match slicer restricted to matches with progression data (3,285), hero slicers now reach the progression tables, Play Axis re-wired to a shared `dim_match_minute` so scrubbing drives the progression tables — see §5h. **Round 8 (2026-08-08):** Play Axis removed; hero slicers titled & side-scoped (Radiant → Radiant tables only, Dire → Dire tables only); player tables trimmed to player / hero / level / K / D / A / net worth (team_win, GPM, XPM dropped); progression tables filter via match + side hero slicers — see §5i. **Round 9 (2026-08-08, §5j):** hero slicers now scope to the selected match via the `Hero in Current Match` measure + visual-level filter (**verified in Desktop**). **Round 11 (2026-08-08, §5l):** both player tables extended to **25 columns** — player / hero / level / K / D / A / net worth / GPM / XPM / damage to heroes / damage to buildings / damage received phys·mag·pure / LH / denies / heal / pick sequence / enemy heroes killed / support gold / wards·dust·smoke·gem bought. |
| **Match Breakdown** (`8691a6fe-f9a0-40e7-b33f-4f0a4c276465`) | **NEW (2026-08-08, Round 10, 1280×1000)** — per-match deep-dive: match dropdown, **rune pickups by hero** (via `fact_match_player_runes` + `dim_rune`), **support contribution** (wards placed / dewards via new `fact_match_players` support columns), **damage dealt/taken** split Radiant/Dire with **target/source-category slicers** (Hero/Building) and **building/hero damage KPI cards** (via `fact_match_player_damage` / `_taken`). See §5k. |
| **Progression** (`a0d69ef1-5555-4687-a1ee-623c1399b01f`) | **NEW (2026-08-08, Round 12, 1280×900)** — per-minute line charts with a shared minute slicer + match dropdown: **Team XP & Net Worth** (`fact_match_team_minute`), **Player Net Worth**, **Player Level** (`fact_match_player_minute`), **Player Item Purchases** (`fact_match_player_item_purchases`). X = minute, Y = metric, legend = side/hero. See §5p. |

290 report JSON files, all parse cleanly, 0 bad, 0 BOMs (validated 2026-08-17).

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
- All **52 relationships** validate (types are text at the schema level); the
  Round-16 pruning removed the kills/timeline/composition/minute links, and the
  remaining ones (round 4–13 timeline-era, matchup, H2H, per-minute, runes,
  damage, team-minute, hero-side links) were re-verified against the model
  (2026-08-17, §5t).
- **Grand Report page** (`a1b2c3d4-…`, 2026-08-16): all pages merged on one
  3840×8517 px canvas as chapters with a deduplicated global filter bar —
  144 visuals, 38 unique slicers of 40 total, registered as the landing page;
  `build_grand_page.py --verify` resolves all 474 field references.

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
7. **`victim_hero_id → dim_hero` was an inactive relationship** (only one
   active link per pair) on the old `fact_teamfight_kills` / `fact_match_player_kills`
   tables — **both pruned in Round 16**, so the caveat no longer applies to any
   live table. `fact_hero_matchups.dire_hero_id` and
   `fact_hero_matchups_hero.opponent_id` are still inactive second links (same
   DirectQuery constraint); victim-side analysis uses the denormalized
   `fact_match_players.enemy_heroes_killed` column.
8. **Staleness.** The gold layer is a dbt build; new matches appear only after
   `dbt run` and a report refresh. No scheduler yet.
9. **Report files are hand-edited** (visual.json / TMDL). PBI Desktop re-saves
   can rewrite/upgrade them (it upgraded 2.2.0 → 2.11.0 schemas), so re-check the
   diff after opening/saving in Desktop.
10. **New "second-dimension" links are inactive by design.** `dire_hero_id`,
    `team_b_id` (and the old `victim_hero_id`) each need `USERELATIONSHIP` in a
    measure to filter — DirectQuery supports only one active relationship per
    pair.
11. **Backups are refreshed at each savepoint.** Newest dump:
    **`backups/gold_20260817_161207.dump`** (304.7 MB, taken 2026-08-17 after
    the Round 16 pruning + gold rebuild, §5t). Previous:
    `gold_20260814_025223.dump` (Round 15), `gold5_20260812_162008.dump`
    (rounds 4–14). Re-dump after any future round that changes the DB (or run
    the pipeline's `--backup` step).
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
- **Heavy builds can OOM-kill Postgres on this machine (2026-08-16/17).**
  The Docker Desktop VM (~6.7 GB) SIGKILLs Postgres (`server process was
  terminated by signal 9`) when dbt runs parallel heavy builds — the host
  (13.9 GB) is often too memory-pressured (browser, qBittorrent, etc.).
  Recovery replays WAL and the DB comes back in ~7 s, but dbt aborts.
  **Run heavy gold rebuilds with `--threads 1`.** See §5t.

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

### 5k. Round 10 — Match Breakdown page: kills, runes, support, damage (2026-08-08)

- **Goal:** a dedicated per-match deep-dive page ("Match Breakdown", page
  `8691a6fe-f9a0-40e7-b33f-4f0a4c276465`) exposing data that was in the
  bronze parsed payload but never surfaced: hero kill counts, rune pickups
  (incl. bounty), support contribution, and damage dealt / taken breakdowns.
- **New gold facts (dbt):**
  - `fact_match_player_kills` — one row per (match, killer, kill) from
    `kills_log`; victim decoded to hero via `dim_hero.hero_name`
    (157,498 rows; 99.85% victims decode to a hero).
  - `fact_match_player_runes` — one row per (match, player, rune type) from the
    **aggregate `runes` map** (authoritative; the `runes_log` timeline array is
    only present for a subset of players), rune type decoded via new
    **`dim_rune`** seed (79,044 rows).
  - `fact_match_player_damage` — one row per (match, player, target) from the
    `damage` object, categorized Hero / Building / Creep / Neutral / Ward /
    Other (1,351,389 rows).
  - `fact_match_player_damage_taken` — same shape from `damage_taken` (raw,
    pre-mitigation) (936,459 rows).
  - `fact_match_players` **+6 support columns**: `obs_placed`, `sen_placed`,
    `observer_kills`, `sentry_kills`, `purchase_ward_observer`,
    `purchase_ward_sentry`. `obs_placed`/`sen_placed` are derived from the
    authoritative `obs_log`/`sen_log` arrays (the OpenDota scalars are null for
    most players).
  - `dim_player` now populates `player_name` for match participants from the
    bronze `personaname` (latest seen) — fixes blank names across the report.
- **Model:** +5 tables (4 facts + `dim_rune`), +30 relationships → **35 tables,
  83 relationships** (3 bidirectional). The `fact_match_player_kills` victim →
  `dim_hero` relationship is **inactive** (`isActive: false`) to avoid the
  ambiguous-path error (`PFE_XL_USERELATIONSHIP_AMBIGUOUS_PATH`) that a second
  active `dim_hero` link would cause — the same pattern `fact_teamfight_kills`
  already uses. New measures: `Hero Kills`, `Rune Count` (SUM of `rune_count`),
  `Total Damage`, `Total Building Damage`, `Total Hero Damage`,
  `Total Damage Taken`, `Total Wards Placed`, `Total Dewards`, etc.
- **Page visuals (Round 10b fixes):**
  - **Hero kills** split into two tables — **Radiant** and **Dire** (visual-level
    `side` filter; the `side` column was removed since it's now implied).
  - **Rune pickups by hero** table (side / hero / rune / count) — now shows all
    sides and heroes (aggregate map, not the sparse timeline).
  - **Support contribution** table (side / player / hero / wards placed /
    dewards) — now shows player names and ward counts correctly.
  - **Damage dealt** split into **Radiant** and **Dire** tables, each filtered to
    `target_category` = Hero/Building, plus a **target_category slicer** and two
    **KPI cards** (`Total Building Damage`, `Total Hero Damage`).
  - **Damage taken** split into **Radiant** and **Dire** tables filtered to
    `source_category` = Hero/Building, plus a **source_category slicer**.
  - Physical / magical / pure damage breakdown (5.1) is **not available** — the
    `damage_inflictor(_received)` fields are null for these matches; per the
    user, a category slicer is used instead.
- **Not buildable from bronze (documented):** outposts taken, wisdom-shrine
  captures, neutral-item upgrade timeline, permanent-buff timestamps.
- **Verified:** dbt build + tests pass; 145 report JSON files parse (0 bad);
  all visual projections/measures/filters resolve against TMDL; all 68
  relationship from-columns exist.
- **Remaining:** Desktop render pass of the Match Breakdown page.

---

### 5l. Round 11 — Match Detail player tables: full stat columns (2026-08-08)

- **Goal:** extend the two Match Detail player tables (**Radiant** /
  `01f2e3d4-…-000006`, **Dire** / `01f2e3d4-…-000007`) with 18 additional
  per-player columns.
- **New columns (all on `fact_match_players`, denormalized):**
  - `gold_per_min` (GPM), `xp_per_min` (XPM), `hero_damage` (total to heroes),
    `tower_damage` (total to buildings), `last_hits`, `denies`,
    `hero_healing` (heal) — already existed as columns, added to the visuals.
  - `pick_sequence` — hero's draft pick order (from `fact_picks_bans.order_no`
    joined on match + hero).
  - `enemy_heroes_killed` — kills of the opposite side by this player (from
    `stg_match_player_kills` count; Radiant table = Dire heroes killed, Dire
    table = Radiant heroes killed).
  - `damage_taken_physical` / `damage_taken_magical` / `damage_taken_pure` —
    raw damage received by type, from the new **`fact_match_player_damage_taken_type`**
    fact (`damage_inflictor_received` classified via ability/item `dmg_type`;
    the `null` auto-attack key maps to Physical). Note: matches with empty
    `damage_inflictor_received` (e.g. the user-tested 1502168860) show blanks —
    same source-data limitation as the Match Breakdown damage tables.
  - `ward_observer_bought`, `ward_sentry_bought`, `dust_bought`, `smoke_bought`,
    `gem_bought` — support item purchase counts (from `purchase_log`).
  - `support_gold` — total gold spent on support items (observer×0 + sentry×50 +
    dust×80 + smoke×50 + gem×900, current item costs). No native support-gold
    label exists in OpenDota; this is the computed definition.
- **New gold fact:** `fact_match_player_damage_taken_type` (silver
  `stg_match_player_damage_taken_type`; 474,310 inflictor rows → 104,057
  match/player/type rows). +1 table, +3 relationships → **36 tables, 71
  relationships** (3 bidirectional).
- **dbt detail:** the `enemy_kills` / `support_items` / `damage_taken_type`
  CTEs read the **silver** stages (`stg_match_player_kills`,
  `stg_match_player_item_purchases`, `stg_match_player_damage_taken_type`) to
  avoid a dbt dependency cycle (`dim_hero` ↔ `fact_match_players`).
- **Fix (model load failure):** `pick_sequence` initially came out as `text`
  (from `fact_picks_bans.order_no` which is text) but was declared `int64` in
  TMDL — this broke the whole model load in Desktop ("failed to load report",
  empty data pane). Fixed by casting `order_no` to int in the dbt model so the
  column is `integer`, matching the TMDL. All other new columns are int/bigint
  and verified consistent.
- **Fix (report pages missing):** the two player-table `visual.json` files were
  rebuilt with PowerShell `ConvertTo-Json`, which dropped the `$schema` key.
  Power BI's PBIR deserializer requires `$schema` on every visual — missing it
  made the report fail to load its pages. Restored `$schema` on both files
  (`visualContainer/2.11.0`); a full structural sweep confirmed every
  `visual.json` has `$schema`, `filterConfig` is at top level, and all
  projections/measures/filters resolve.
- **Verified:** dbt build + 29 tests pass; 145 report JSON files parse (0 bad);
  all visual projections resolve against TMDL; 0 BOM files.
- **Remaining:** Desktop render pass — both player tables are now ~25 columns
  wide (may need horizontal scroll / frozen first column).

---

### 5m. Round 11b — pick sequence fix + ban data (2026-08-08)

- **Problem:** `pick_sequence` showed the raw draft `order_no` (1–20), which
  mixed picks and bans into one global order — not intuitive.
- **Fix (`fact_match_players.sql`):** `pick_sequence` is now the pick's rank
  among picks only (**1–10**, via `row_number() over (partition by match_id,
  is_pick)`). Added **`ban_sequence`** (rank among bans only, 1–N) as a column
  — it is NULL in the player tables because all players are picks; banned
  heroes never play.
- **Ban data bug fixed (`stg_picks_bans.sql`):** the raw `picks_bans[].team`
  (0=Radiant, 1=Dire) was never captured — `stg_picks_bans` read the empty
  `active_team` field. Now reads `team` and exposes `team_number` +
  `active_team` (Radiant/Dire). `fact_picks_bans` + TMDL + schema.yml updated.
- **Match Detail player tables renamed:** 'Radiant - players, heroes, items &
  skills' → **'Radiant - Match Details'**, 'Dire - …' → **'Dire - Match
  Details'** (visuals `01f2e3d4-…-000006` / `…-000007`).
- **Draft page:** new **'Ban frequency by hero'** tableEx
  (`d6d3e7e7-e475-4765-830d-e7fc578ca658`) — hero / Draft Bans / Ban Rate /
  Avg Ban Position. New measures on `fact_picks_bans`: `First Ban`,
  `Avg Ban Position`, `Ban Sequence`.
- **Verified:** dbt build + 13 tests pass; 146 report JSON files parse (0 bad);
  all projections/measures resolve; 0 BOM files.
- **Remaining:** Desktop render pass.

---

### 5n. Round 11c — talents in skill-levelling tables (2026-08-08)

- **Goal:** make talent-tree picks visible and readable in the Match Detail
  **skill levelling over time** tables (Radiant/Dire, `03f2e3d4-…-000003` /
  `…-000004`). Talent data was already present in bronze
  (`ability_upgrades_arr` contains `special_bonus_*` ability ids) and flowing
  into `fact_match_player_skills`, but labels were poor: unresolved `+{s:…}`
  templates (e.g. `+{s:bonus_illusion_duration}s Reflection Duration`) or raw
  `special_bonus_*` keys.
- **dbt (`fact_match_player_skills.sql`):** added **`is_talent`** flag (true
  when the internal name starts with `special_bonus` or is `attribute_bonus`),
  and **cleaned talent labels** by stripping the `+{s:…}` / `-{s:…}` value
  template (e.g. → `Reflection Duration`). `special_bonus_attributes` /
  `attribute_bonus` → `Attribute Bonus`.
- **Coverage:** 88,060 talent rows; ~3% (2,598) still show raw
  `special_bonus_unique_*` keys because those talent abilities have no `dname`
  in the abilities constants (newer heroes / gaps in the source constants).
- **TMDL:** `fact_match_player_skills` + `is_talent` column.
- **Report:** both skill-levelling tables now show an **is_talent** column.
- **Verified:** dbt build + 13 tests pass; 146 JSON files parse (0 bad); all
  projections resolve; 0 BOM files.

### 5o. Round 11d — fix cyclic-reference refresh error (2026-08-08)

- **Symptom:** after the talent change, data refresh reported **"a cyclic
  reference was encountered during evaluation"** blocking 32 queries across
  `gold dim_hero_role`, `gold fact_matches`, `gold fact_teamfight_kills`,
  `gold dim_hero`.
- **Causes removed:**
  - **Unused table `gold fact_match_player_damage_taken_type`** (added Round 11
    but superseded — the visuals use denormalized
    `fact_match_players.damage_taken_*` columns). Removed its TMDL file + 3
    relationships (`match_id→fact_matches`, `hero_id→dim_hero`,
    `account_id→dim_player`) + model.tmdl refs. This eliminated the newest
    cycle-contributing relationships.
  - **Unused `Ban Sequence` measure** on `fact_picks_bans`
    (`RANKX(ALL(...), ...)` — a known cyclic-reference trigger in DirectQuery).
    Kept `Avg Ban Position` (used by the Draft page).
- **Model:** now **35 tables, 68 relationships** (3 bidirectional). The silver
  `stg_match_player_damage_taken_type` stage is still used by
  `fact_match_players` for the damage-type columns; only the standalone gold
  model is no longer exposed to Power BI.
- **Verified:** 146 JSON files parse (0 bad); all visual measure/column refs
  resolve; all 68 relationship from-columns exist; no dangling
  `damage_taken_type` references.

---

### 5p. Round 12 — Progression page: per-minute line charts (2026-08-08)

- **Goal:** a new **Progression** page (`a0d69ef1-5555-4687-a1ee-623c1399b01f`,
  1280×900) with per-minute line charts. X = game minute; Y = the metric.
- **New gold fact `fact_match_team_minute`** — one row per (match, side,
  minute): `team_gold` / `team_xp` summed from `fact_match_player_minute`
  (the raw `gold_t`/`xp_t` arrays). +1 table, +3 relationships.
- **Also added** a missing `fact_match_player_minute.minute → dim_match_minute`
  relationship (was absent — the minute slicer could not filter Player Net
  Worth / Player Level charts without it).
- **Slicers (top row):** **match** dropdown (`fact_matches.match_id`), **minute**
  dropdown (`dim_match_minute.minute` — switched from Between mode which
  rendered blank), **Radiant Hero** and **Dire Hero** dropdowns
  (`dim_hero.hero_localized_name`, each side-scoped via a visual-level
  `side` filter). The match/minute/hero slicers propagate to all charts.
- **Charts (all lineChart):**
  1. **Team XP & Net Worth** (`1f5375c7`) — `fact_match_team_minute`: minute ×
     team_gold + team_xp, **legend = side** (Radiant/Dire lines).
  2. **Player Net Worth** (`d8b50a76`) — `fact_match_player_minute`: minute ×
     gold, **legend = player_name** (all 10 players, not split by team).
  3. **Player Level** (`192b95ac`) — `fact_match_player_minute`: minute ×
     level, legend = player_name.
  4. **Player Item Purchases** (`eb48713a`) — `fact_match_player_item_purchases`:
     minute × `Total Purchases` (COUNTROWS measure), **legend = item_name**
     (shows which item was bought at each minute).
- **Skipped per user decision:** **Player damage** — OpenDota has no per-minute
  damage data (only final totals and per-teamfight damage without player ids).
- **Note:** `fact_match_player_minute.gold` is total gold earned (`gold_t`),
  the standard net-worth-over-time proxy.
- **Round 12b fixes:** the minute slicer was `Between` mode with a Categorical
  filter (rendered blank / blocked other charts); switched to **Dropdown**.
  Hero slicers added with side scoping; player charts now legend by
  `player_name` (not hero); team chart legends by `side`.
- **Round 12c fix (charts blank):** the three player/team charts used **raw
  columns** (`gold`, `level`, `team_gold`, `team_xp`) as Y values, which do not
  render in a PBIR line chart. Added **measures** and bound Y to them:
  `Avg Net Worth` / `Avg XP` / `Player Level` on `fact_match_player_minute`,
  `Team Gold` / `Team XP` on `fact_match_team_minute`. The item chart already
  used a measure (`Total Purchases`) — that is why it was the only one that
  rendered. All four now use measure-based Y values.
- **Round 12d revisions (per user):**
  1. **Team XP & Net Worth by side** — now four side-specific Y measures so
     both teams show simultaneously: `Radiant Team Gold`, `Dire Team Gold`,
     `Radiant Team XP`, `Dire Team XP` (no legend; the measures are
     self-describing).
  2. **Player Net Worth** — legend changed to `hero_localized_name` (one line
     per hero, not one aggregate line).
   3. **Player Level** — legend changed to `hero_localized_name` (reverted to a
      line chart after testing; the ribbon chart experiment was discarded).
   4. **Player Item Purchases** — replaced the line chart with a **table**
      (side / hero / player / item_name / minute) showing the actual items each
      hero bought, instead of a per-minute purchase count.
- **Round 12e (2026-08-08):** the **Radiant – Hero** / **Dire – Hero**
  slicers on the Progression page now show **only the heroes present in the
  currently selected match, side-scoped**: Radiant slicer lists only the
  match's Radiant heroes, Dire slicer only its Dire heroes. Achieved with two
  new side-specific measures on `dim_hero` — **`Hero in Current Radiant Match`**
  and **`Hero in Current Dire Match`** — each `CALCULATE(COUNTROWS(fact_match_players))`
  filtered by side, applied as a `> 0` Advanced visual filter on the
  respective slicer. (The earlier attempt used a `side` column filter on
  `fact_match_player_minute`, but that relationship to `dim_hero` is
  single-direction, so it did not reach the slicer's `dim_hero` values; the
  measure approach filters `dim_hero` directly.)
- **Round 12f (2026-08-08):** the two side-scoped hero slicers were **merged
  into one "Hero" slicer** that lists **all heroes present in the current
  match** (via the original `Hero in Current Match > 0` filter). The Dire
  slicer was removed.
- **Round 12g (2026-08-08):** **border enabled on all 138 report visuals**
  (tables, slicers, charts, cards) — `visualContainerObjects.border.show = true`
  added/updated across every `visual.json`. Verified: all JSON parse, 0 BOMs,
  `$schema` intact, model unchanged (36 tables / 71 relationships).

---

### 5q. Round 13 — normalization + page enhancements (2026-08-09)

**Normalization (dbt gold, all text columns — TMDL unchanged):**
- `dim_league.league_name` → uppercase.
- `dim_team.team_name` → uppercase (`'Unknown'` → `'UNKNOWN'`).
- `dim_game_mode.game_mode_name` → strip `game_mode_` prefix + uppercase
  (e.g. `CAPTAINS MODE`).
- `dim_lobby_type.lobby_type_name` → strip `lobby_type_` prefix + uppercase
  (e.g. `BATTLE CUP`).
- `dim_hero.primary_attr` → friendly labels (`agi→Agility`, `all→Universal`,
  `int→Intelligence`, `str→Strength`).
- `dim_player.player_type` → `'Pro'` / `'Match Participant'`.
- `fact_team_h2h` → **denormalized `team_a_name` / `team_b_name`** (the
  `team_b_id → dim_team` link is inactive; precomputed names follow the
  `fact_hero_matchups.matchup_label` pattern).

**Report pages:**
- **Hero Meta**: + Patch slicer; + **Hero win rate per patch** line chart
  (top-20 by picks via `Hero Pick Rank <= 20`); + **Hero ban rate per patch**
  line chart (top-15 by bans via `Hero Ban Rank <= 15`). New rank measures on
  `dim_hero`. Page height 720 → 1000.
- **Players**: + **Player appearances by league** bar chart (`dim_league.league_name`
  × `Total Picks`). Page height 720 → 1000.
- **Teams**: + League Name slicer; + **Team win rate by league (by side)**
  table (`team_name`, `league_name`, `side`, `Team Appearances`,
  `Team Win Rate`). Page height 900 → 1100.
- **Matches**: "Avg match duration by month" → **by patch**
  (`dim_patch.patch_name`).
- **Economy**: "GPM / XPM trend by month" → **by patch**.
- **Draft**: fixed `Avg Ban Position` (`AVERAGEX(...VALUE(order_no))` — was
  `AVERAGE` on a text column → the reported MdxScript error); + **Dire Hero
  Win Rate** column on "Most common hero matchups"; + **Hero win rate by
  side** table; reworked **Team vs Team head-to-head** table to
  Team A | Team B | Matches | A Win% | B Win% | A W–L | B W–L (new measures
  `Team A Losses`, `Team B Wins`, `Team B Losses`, `Team B Win Rate`).
- **Round 13b fixes (2026-08-09):** the "Most common hero matchups" and "Hero
  win rate by side" visuals hit DirectQuery **query-folding errors**
  (`We couldn't fold the expression`) because win-rate measures referenced
  other measures (`1 - [Radiant Hero Win Rate]`) or used cross-table
  `COUNTROWS` grouping. Fixed by: (a) making `Dire Hero Win Rate` self-contained
  (`DIVIDE([Dire Hero Wins], [Matchup Count])` with explicit `= TRUE()` /
  `= FALSE()` on `radiant_win`); (b) adding a **precomputed `fact_hero_side`**
  gold table (one row per hero+side: `hero_side_picks`, `hero_side_wins`,
  `hero_side_win_rate`) — the same DirectQuery pattern as `fact_team_h2h`.
  The "Hero win rate by side" table was **split into two** — **Hero win rate –
  Radiant** and **Hero win rate – Dire** (visual-level `side` filter on the new
  fact).
- **Round 13c fixes (2026-08-09):** "Most common hero matchups" and "Ban
  frequency by hero" still wouldn't fold. Root cause: `Avg Ban Position` used
  `AVERAGEX(FILTER(...), VALUE(order_no))` over a text column (iterator not
  foldable), and the matchups win-rate measures grouped a text `matchup_label`
  by `CALCULATE(COUNTROWS(...))`. Fixed by: (a) adding **`order_no_int`**
  (numeric) to `stg_picks_bans` / `fact_picks_bans` and changing
  `Avg Ban Position` to `CALCULATE(AVERAGE(order_no_int), is_pick = FALSE())`;
  (b) adding a **precomputed `fact_hero_matchup_stats`** gold table (one row
  per `matchup_label` with `matchup_games`, `radiant_wins`, `dire_wins`,
  `radiant_win_rate`, `dire_win_rate`) and rewiring the matchups table to it
  (measures `Matchup Games`, `Matchup Radiant Win Rate`, `Matchup Dire Win
  Rate`). Model: **38 tables, 72 relationships**.

**Verified:** dbt 317 tests pass (2026-08-12); 143 report JSON files parse (0
bad); 0 BOMs; all visual projections/measures/filters resolve; no duplicate
measures.

---

### 5r. Round 14 — Combat page Match ID slicer (2026-08-12)

User feedback round. No dbt / model changes — report layer (PBIR) only.

- **Combat page gained a Match ID slicer.** New dropdown slicer
  (`6e9cce4f-5e23-470e-8975-af2a57645046`, `visualType: slicer`, mode Dropdown)
  bound to `gold fact_matches.match_id`, placed in the free top-right strip at
  x=650 / y=15 (w=300, h=70) next to the existing Hero (x=20) and Player (x=335)
  slicers. Follows the exact Match Detail / Progression match-slicer pattern
  (2.11.0 schema, `nativeQueryRef: "Match ID"`, `$schema` present, BOM-less,
  border enabled, `drillFilterOtherVisuals: true`).
- **Filtering:** `fact_matches.match_id` reaches the combat facts through the
  existing single-direction `fact_teamfights.match_id → fact_matches` and
  `fact_teamfight_players.match_id → fact_matches` links (one→many), so the
  slicer filters the 3 cards, the "Avg damage & healing per fight" bar and the
  "Most killed heroes" table — the same hub-slicer pattern as Match Detail
  (§5i).
- **Verified:** all 8 Combat-page JSON files parse (0 bad); full report = 143
  JSON files, 0 bad; 0 BOMs; `$schema` intact. Model unchanged (38 tables, 72
  relationships, 3 bidirectional).
- **Savepoint (2026-08-12):** fresh `pg_dump` taken —
  `backups/gold5_20260812_162008.dump` (337 MB, 210 TOC entries) — supersedes
  the stale `gold4_20260808_191856.dump` (see §3.11). Git commit at this round
  = the rollback point. All report pages render correctly in Power BI Desktop.

### 5s. Round 15 — Hero Meta matchup visual + search slicers + orchestrator hardening (2026-08-14)

- **Data (dbt):** `gold.fact_hero_matchups_hero` gained two display columns —
  `hero_name` and `opponent_name` (localized names, joined from `dim_hero` in
  both perspectives) — so a table can list opponents without the second
  (inactive) hero relationship. Added `not_null` tests for both columns in
  `transform/models/gold/schema.yml`; mirrored into the TMDL
  (`gold fact_hero_matchups_hero.tmdl`, lineageTags …013/…014). Rebuilt with
  `dbt build` — 213,390 rows, all 11 tests PASS.
- **Hero Meta page (`5995aa2f`, §5e) — Top opponents table:** new **Hero**
  dropdown slicer (`b759809c-0df0-4153-86cb-b68307b74771`, x=870/y=15, w=390)
  bound to `gold dim_hero.hero_localized_name` (searchable, §3.10-style) drives
  a new **Top opponents** `tableEx` (`3f09eacb-fceb-4ff8-81ef-c7165f86d411`,
  x=20/y=990, w=1240/h=270) projecting `opponent_name` + `Hero Matchup Games` +
  `Hero Matchup Win Rate` (measures on `gold fact_hero_matchups_hero`), sorted
  by games desc. Page height 1000 → **1280** to fit it; the existing hero-stats
  table (`a408a2f7`) cross-filters it. Because `hero_id → dim_hero` is the only
  active relationship, the slicer shows the focal hero's true record vs every
  opponent on both sides.
- **Search slicers (item 4):** added `objects.general.properties.
  selfFilterEnabled = true` (the PBIR serialization of the slicer search-box
  toggle) to all high-cardinality slicers — hero (`56eca095`/2b9f3b80,
  `cb9a7fde`/02340ea0, `9d4f2e1a`/02f2e3d4…01/…02, `5995aa2f`/b759809c),
  player (`56eca095`/dbc0270a, `cb9a7fde`/e818b205), match ID (`56eca095`
  /6e9cce4f, `8691a6fe`/48d2ed1e, `9d4f2e1a`/01f2e3d4), league (`655dabd0`
  /aaaa0202, `a535cc39`/aaaa0102, `baedb79c`/b191d359). League/team/hero
  slicers on Overview/Teams/Combat pages already had it from earlier rounds.
- **Orchestrator hardening (items 1–2, data pipeline):** `scripts/run_pipeline.py`
  now has `--backup`/`--only-backup`/`--backup-prefix`/`--backups-dir`/
  `--backup-docker` (pg_dump via `docker exec dota_postgres`, since pg_dump is
  not on Windows PATH nor in the orchestrator images) and
  `dbt_source_freshness()` + `--freshness`/`--only-freshness`. Airflow DAG
  `dota_medallion_pipeline` now runs
  `load_bronze >> dbt_build >> [dbt_source_freshness, pg_dump_backup]`; the
  Dagster job gained `source_freshness` and `db_backed_up` assets. Verified
  live: `dbt source freshness` exits 0 on WARN (bronze.matches 7d threshold),
  and the backup step wrote a valid 337 MB `-Fc` dump.
- **Verified:** full report = 146 JSON files, 0 bad, 0 BOMs, `$schema` intact;
  18/40 slicers have `selfFilterEnabled` (all high-cardinality ones). Model
  unchanged (38 tables, 72 relationships, 3 bidirectional).
- **Savepoint (2026-08-14):** fresh `pg_dump` taken —
  `backups/gold_20260814_025223.dump` (337 MB) via the pipeline's
  `--only-backup --backup-docker` step — supersedes `gold5_20260812_162008.dump`.

### 5t. Round 16 — DB optimization + Grand Report page (2026-08-16 → resumed 2026-08-17)

Status ledger (kept updated as the round progresses):

- [x] **Drop 8 unused gold tables (dbt + model).** All confirmed unused — zero
      references anywhere in the report:
      `fact_match_player_kills`, `fact_match_timeline`,
      `fact_match_timeline_events`, `fact_team_compositions`,
      `fact_teamfight_item_uses`, `fact_teamfight_kills`, `dim_match_minute`
      (kept only as `generate_series` range in `fact_match_player_minute`) and
      the gold `fact_match_player_damage_taken_type` (silver
      `stg_match_player_damage_taken_type` still feeds `fact_match_players`).
      schema.yml tests removed with them.
- [x] **Index hardening (all gold models).** Fixed the double-schema index-name
      bug (`{{ this.schema }}_{{ this.schema }}_fact_*_idx` → single prefix, with
      `drop index if exists` before `create index` so rebuilds stay idempotent).
      `fact_matches` gained `match_id`, `patch` and `start_date` indexes.
- [x] **`on-run-end: analyze`** in `transform/dbt_project.yml` — Postgres
      statistics refresh after every build (visible as a ~23s hook at the end of
      each `dbt build`).
- [x] **Semantic model pruned 38 → 31 tables** (relationships.tmdl, model.tmdl
      `PBI_QueryOrder`), TMDL files for the dropped tables deleted.
- [x] **Grand Report page** (`a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d`): a new
      script `scripts/build_grand_page.py` merges every page of the report onto
      one 3840 px canvas — deduplicated global filter bar (~40 slicers → unique
      set), one chapter per source page with story textboxes, preserved
      cross-visual interactions, `--verify` flag that checks every field
      reference against the semantic model. `tests/test_build_grand_page.py`
      covers slicer dedupe + layout. Generated page registered as the report's
      landing/active page in `pages.json`.
- [x] **Interrupted build diagnosed.** The 2026-08-16 `dbt build` ran 30/32
      models then failed when Docker was stopped mid-run: `server closed the
      connection unexpectedly` / `FATAL: the database system is shutting down`.
      Failed: `fact_match_player_skills`, `fact_match_team_minute` (both leaf
      facts, no downstream dependents).
- [x] **Resumed 2026-08-17 — targeted repair build:** `dbt build --select
      fact_match_player_skills fact_match_team_minute` → PASS 23/23
      (skills 535,432 rows in ~10 min, team_minute 250,640 rows; 20 tests green;
      `analyze` hook OK).
- [x] **Gold layer rebuilt & verified green:** `dbt build --select gold
      --threads 1` → **PASS 227/227** (32 table models + 194 data tests,
      9.5 min; `on-run-end: analyze` OK). The 3 full-build attempts crashed on
      the OOM issue below; gold-only was stable and covers the session's
      changes (silver edits were hook-only, content unchanged).
- [x] **Orphaned gold tables dropped:** the 8 removed tables were already gone
      from the DB (dropped during the 2026-08-16 session before the stop); the
      one leftover was the stale experiment `fact_team_h2h_new` (4,220 rows,
      not in dbt or the report) — dropped 2026-08-17. DB gold = manifest gold
      = 32 tables.
- [x] **Validations:** pytest 33/33 PASS; `build_grand_page.py --verify` =
      474 field references all resolve against the pruned model (page
      regenerated, 144 visuals, 38 unique slicers); 290 report JSON files,
      0 bad, 0 BOMs.
- [x] **Fresh `pg_dump`:** `backups/gold_20260817_161207.dump` (304.7 MB,
      193 TOC entries, `-Fc` via `run_pipeline.py --only-backup
      --backup-docker`) — supersedes `gold_20260814_025223.dump`.
- [x] **Docs + commit savepoint** — this round closes with a commit (see git
      log).

**OOM discovery (2026-08-17):** the "interrupted build" had a second cause
besides the Docker stop. Postgres logs show repeated
`server process was terminated by signal 9: Killed` (OOM killer) — three times
on 2026-08-16 (12:26/12:28/12:30 UTC) and three times on 2026-08-17 (07:51,
07:53, 07:55 UTC) during builds. Root cause: the Docker Desktop VM (6.7 GB) is
squeezed — the host (13.9 GB) often has only ~5 GB free
(Firefox/qBittorrent/Steam/etc.), so dbt builds spike Postgres past the VM
limit and the OS SIGKILLs a backend; WAL recovery replays (~7 s) and dbt
aborts. Even `--threads 1` full builds crashed while scanning the big
silver/bronze tables; **gold-only builds (`--select gold`) were stable** — use
`--threads 1` + `--select gold` for heavy rebuilds. Power BI DirectQuery is
unaffected (single-user, small queries). Documented in §4 below.

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
  matchup matrix (**top-opponents table shipped 2026-08-14, §5s** — the full
  matrix still needs `USERELATIONSHIP` or Desktop), ~~report documentation~~
  (About & Glossary page shipped 2026-08-05).
- **Depth**: patch dimension (`dim_patch` ready + slicer added), expose
  teamfight child facts, victim-hero analysis via matchups fact, rank
  distribution (blocked — no rank data).
- **Visuals**: switch fragile `tableEx` to classic `table`; ~~add search
  slicers~~ (**done 2026-08-14, §5s** — `selfFilterEnabled` on all
  high-cardinality slicers); better "Unknown" handling (leaderboards already
  filtered).
- **Ops**: ~~orchestrator (bronze_load → dbt build)~~ (**done 2026-08-13/14 —
  Airflow DAG + Dagster job now also run `source freshness` and `pg_dump` backup**),
  ~~backup cadence~~ (**fresh dump taken 2026-08-14 —
  `gold_20260814_025223.dump`, §5s**), CI on the pbip JSON.
- **Next (this session's handover)**: Rounds 1–15 are complete and **render
  correctly in Power BI Desktop** (Round 9 hero-slicer scoping, Round 10 Match
  Breakdown, Round 11 player stat columns, Round 12 Progression, Round 13
  normalization, Round 14 Combat Match ID slicer, Round 15 Hero Meta
  top-opponents + search slicers). The report is at a **savepoint** — see
  **RESUME HERE** at the top of this file and §5s for the commit + fresh dump
  (`gold_20260814_025223.dump`). Remaining backlog ideas are all below this
  line (full matchup matrix via USERELATIONSHIP, player drill-through, images).
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
