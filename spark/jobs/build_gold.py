"""M1a: build core gold tables in PySpark from the dbt silver tables.

This is intentionally a first parity slice, not all 33 gold models. It covers
dim_hero, dim_team, fact_matches, fact_match_players (core columns), and
fact_picks_bans. The next M1 step is replacing silver reads with bronze JSONB
parsing and filling the enriched columns.
"""
from common import read_silver, spark_session, write_delta

spark = spark_session("dota-m1-gold")

sources = [
    "stg_matches",
    "stg_match_players",
    "stg_picks_bans",
    "stg_heroes",
    "stg_hero_stats",
    "stg_teams",
]
for view in sources:
    read_silver(spark, view).createOrReplaceTempView(view)

# ---------------------------------------------------------------------------
# dim_hero
# ---------------------------------------------------------------------------
hero_dim_sql = """
WITH hero_dim AS (
    SELECT
        h.hero_id,
        COALESCE(h.hero_name, 'unknown') AS hero_name,
        COALESCE(h.localized_name, 'Unknown') AS hero_localized_name,
        CASE h.primary_attr
            WHEN 'agi' THEN 'Agility'
            WHEN 'all' THEN 'Universal'
            WHEN 'int' THEN 'Intelligence'
            WHEN 'str' THEN 'Strength'
            ELSE h.primary_attr
        END AS primary_attr,
        h.attack_type,
        h.roles,
        CONCAT('https://cdn.cloudflare.steamstatic.com', regexp_replace(h.img, '\\\\?$', '')) AS img,
        CASE
            WHEN h.hero_name LIKE 'npc_dota_hero_%' THEN
                CONCAT(
                    'https://cdn.cloudflare.steamstatic.com/apps/dota2/images/dota_react/heroes/icons/',
                    regexp_replace(h.hero_name, '^npc_dota_hero_', ''),
                    '.png'
                )
            ELSE NULL
        END AS hero_icon_sm,
        s.pro_pick, s.pro_win, s.pro_ban, s.pub_pick, s.pub_win, s.pub_win_rate
    FROM stg_heroes h
    LEFT JOIN stg_hero_stats s ON h.hero_id = s.hero_id

    UNION ALL

    SELECT '0', 'unknown', 'Unknown', NULL, NULL, NULL, NULL, NULL,
           NULL, NULL, NULL, NULL, NULL, NULL
),
hero_stats AS (
    SELECT
        hero_id,
        CAST(COUNT(*) AS INT) AS match_picks,
        CAST(SUM(CASE WHEN team_win THEN 1 ELSE 0 END) AS INT) AS match_wins,
        ROUND(SUM(CASE WHEN team_win THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0), 4) AS match_win_rate,
        ROUND(AVG(kda), 2) AS match_avg_kda,
        ROUND(AVG(gold_per_min), 0) AS match_avg_gpm,
        ROUND(AVG(xp_per_min), 0) AS match_avg_xpm,
        ROUND(AVG(hero_damage), 0) AS match_avg_hero_damage,
        ROUND(AVG(tower_damage), 0) AS match_avg_tower_damage,
        ROUND(AVG(hero_healing), 0) AS match_avg_hero_healing,
        ROUND(AVG(last_hits), 1) AS match_avg_last_hits,
        ROUND(AVG(denies), 1) AS match_avg_denies,
        ROUND(AVG(net_worth), 0) AS match_avg_net_worth,
        ROUND(AVG(stuns), 2) AS match_avg_stuns,
        ROUND(AVG(CAST(level AS DOUBLE)), 2) AS match_avg_level,
        CAST(SUM(kills) AS INT) AS match_total_kills,
        CAST(SUM(deaths) AS INT) AS match_total_deaths,
        CAST(SUM(assists) AS INT) AS match_total_assists,
        CAST(SUM(CASE WHEN firstblood_claimed = 1 THEN 1 ELSE 0 END) AS INT) AS match_firstbloods
    FROM stg_match_players
    GROUP BY hero_id
),
draft_stats AS (
    SELECT
        hero_id,
        CAST(SUM(CASE WHEN is_pick THEN 1 ELSE 0 END) AS INT) AS match_draft_picks,
        CAST(SUM(CASE WHEN NOT is_pick THEN 1 ELSE 0 END) AS INT) AS match_draft_bans
    FROM stg_picks_bans
    GROUP BY hero_id
)
SELECT
    d.hero_id, d.hero_name, d.hero_localized_name, d.primary_attr,
    d.attack_type, d.roles, d.img, d.hero_icon_sm,
    d.pro_pick, d.pro_win, d.pro_ban, d.pub_pick, d.pub_win, d.pub_win_rate,
    COALESCE(hs.match_picks, 0) AS match_picks,
    COALESCE(hs.match_wins, 0) AS match_wins,
    COALESCE(hs.match_win_rate, 0) AS match_win_rate,
    hs.match_avg_kda, hs.match_avg_gpm, hs.match_avg_xpm,
    hs.match_avg_hero_damage, hs.match_avg_tower_damage, hs.match_avg_hero_healing,
    hs.match_avg_last_hits, hs.match_avg_denies, hs.match_avg_net_worth,
    hs.match_avg_stuns, hs.match_avg_level,
    COALESCE(hs.match_total_kills, 0) AS match_total_kills,
    COALESCE(hs.match_total_deaths, 0) AS match_total_deaths,
    COALESCE(hs.match_total_assists, 0) AS match_total_assists,
    COALESCE(hs.match_firstbloods, 0) AS match_firstbloods,
    COALESCE(ds.match_draft_picks, 0) AS match_draft_picks,
    COALESCE(ds.match_draft_bans, 0) AS match_draft_bans
FROM hero_dim d
LEFT JOIN hero_stats hs ON d.hero_id = hs.hero_id
LEFT JOIN draft_stats ds ON d.hero_id = ds.hero_id
"""
dim_hero = spark.sql(hero_dim_sql)
write_delta(dim_hero, "dim_hero")
print(f"dim_hero rows={dim_hero.count()}")

# ---------------------------------------------------------------------------
# dim_team
# ---------------------------------------------------------------------------
dim_team_sql = """
WITH team_dim AS (
    SELECT
        team_id,
        CASE
            WHEN NULLIF(UPPER(TRIM(team_name)), '') IS NULL
                THEN COALESCE(NULLIF(UPPER(TRIM(team_tag)), ''), CONCAT('TEAM ', team_id))
            ELSE UPPER(TRIM(team_name))
        END AS team_name,
        team_tag,
        CAST(rating AS DOUBLE) AS rating,
        CAST(wins AS INT) AS wins,
        CAST(losses AS INT) AS losses,
        logo_url
    FROM stg_teams

    UNION

    SELECT DISTINCT
        m.team_id,
        'UNKNOWN' AS team_name,
        CAST(NULL AS STRING) AS team_tag,
        CAST(NULL AS DOUBLE) AS rating,
        CAST(NULL AS INT) AS wins,
        CAST(NULL AS INT) AS losses,
        CAST(NULL AS STRING) AS logo_url
    FROM (
        SELECT radiant_team_id AS team_id FROM stg_matches WHERE has_radiant_team
        UNION
        SELECT dire_team_id AS team_id FROM stg_matches WHERE has_dire_team
    ) m
    WHERE NOT EXISTS (SELECT 1 FROM stg_teams t WHERE t.team_id = m.team_id)
),
team_rows AS (
    SELECT match_id, 'Radiant' AS side, radiant_team_id AS team_id,
           radiant_win, radiant_win AS team_win,
           radiant_score AS team_score, dire_score AS opponent_score
    FROM stg_matches WHERE has_radiant_team
    UNION ALL
    SELECT match_id, 'Dire' AS side, dire_team_id AS team_id,
           radiant_win, NOT radiant_win AS team_win,
           dire_score AS team_score, radiant_score AS opponent_score
    FROM stg_matches WHERE has_dire_team
),
team_stats AS (
    SELECT
        team_id,
        CAST(COUNT(*) AS INT) AS match_appearances,
        CAST(SUM(CASE WHEN team_win THEN 1 ELSE 0 END) AS INT) AS match_wins,
        CAST(SUM(CASE WHEN team_win = FALSE THEN 1 ELSE 0 END) AS INT) AS match_losses,
        ROUND(SUM(CASE WHEN team_win THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0), 4) AS match_win_rate,
        ROUND(AVG(team_score), 1) AS match_avg_score,
        ROUND(AVG(opponent_score), 1) AS match_avg_opponent_score,
        ROUND(AVG(team_score - opponent_score), 2) AS match_avg_score_differential,
        CAST(SUM(team_score) AS INT) AS match_total_score
    FROM team_rows
    GROUP BY team_id
)
SELECT
    d.team_id, d.team_name, d.team_tag, d.rating, d.wins, d.losses, d.logo_url,
    COALESCE(ts.match_appearances, 0) AS match_appearances,
    COALESCE(ts.match_wins, 0) AS match_wins,
    COALESCE(ts.match_losses, 0) AS match_losses,
    COALESCE(ts.match_win_rate, 0) AS match_win_rate,
    ts.match_avg_score, ts.match_avg_opponent_score, ts.match_avg_score_differential,
    COALESCE(ts.match_total_score, 0) AS match_total_score
FROM team_dim d
LEFT JOIN team_stats ts ON d.team_id = ts.team_id
"""
dim_team = spark.sql(dim_team_sql)
write_delta(dim_team, "dim_team")
print(f"dim_team rows={dim_team.count()}")

# ---------------------------------------------------------------------------
# fact_team_matches shape is needed by fact_matches, but is not a report target.
# ---------------------------------------------------------------------------
team_rows = spark.sql("""
SELECT match_id, 'Radiant' AS side, radiant_team_id AS team_id,
       radiant_win, radiant_win AS team_win,
       radiant_score AS team_score, dire_score AS opponent_score
FROM stg_matches WHERE has_radiant_team
UNION ALL
SELECT match_id, 'Dire' AS side, dire_team_id AS team_id,
       radiant_win, NOT radiant_win AS team_win,
       dire_score AS team_score, radiant_score AS opponent_score
FROM stg_matches WHERE has_dire_team
""")
team_rows.createOrReplaceTempView("team_rows")
dim_team.createOrReplaceTempView("dim_team")

# ---------------------------------------------------------------------------
# fact_matches
# ---------------------------------------------------------------------------
fact_matches_sql = """
WITH team_info AS (
    SELECT
        tr.match_id,
        MAX(CASE WHEN tr.side = 'Radiant' THEN t.team_name END) AS radiant_team_name,
        MAX(CASE WHEN tr.side = 'Dire' THEN t.team_name END) AS dire_team_name,
        MAX(CASE WHEN tr.side = 'Radiant' THEN t.logo_url END) AS radiant_team_logo,
        MAX(CASE WHEN tr.side = 'Dire' THEN t.logo_url END) AS dire_team_logo
    FROM team_rows tr
    JOIN dim_team t ON t.team_id = tr.team_id
    GROUP BY tr.match_id
),
radiant_heroes AS (
    SELECT
        mp.match_id,
        CONCAT_WS(', ', TRANSFORM(
            SORT_ARRAY(COLLECT_LIST(NAMED_STRUCT(
                'slot', CAST(mp.player_slot AS INT),
                'name', COALESCE(h.localized_name, 'Unknown')
            ))),
            x -> x.name
        )) AS radiant_heroes
    FROM stg_match_players mp
    JOIN stg_heroes h ON h.hero_id = mp.hero_id
    WHERE mp.team_number = '0'
    GROUP BY mp.match_id
),
dire_heroes AS (
    SELECT
        mp.match_id,
        CONCAT_WS(', ', TRANSFORM(
            SORT_ARRAY(COLLECT_LIST(NAMED_STRUCT(
                'slot', CAST(mp.player_slot AS INT),
                'name', COALESCE(h.localized_name, 'Unknown')
            ))),
            x -> x.name
        )) AS dire_heroes
    FROM stg_match_players mp
    JOIN stg_heroes h ON h.hero_id = mp.hero_id
    WHERE mp.team_number = '1'
    GROUP BY mp.match_id
)
SELECT
    sm.match_id,
    sm.radiant_win,
    sm.winner,
    sm.duration_sec,
    ROUND(sm.duration_sec / 60.0, 2) AS duration_min,
    ROUND(sm.duration_sec / 3600.0, 3) AS duration_hour,
    sm.game_mode AS game_mode_id,
    sm.lobby_type AS lobby_type_id,
    sm.region AS region_id,
    sm.patch,
    sm.start_time,
    CAST(sm.start_time AS DATE) AS start_date,
    sm.radiant_score,
    sm.dire_score,
    CASE
        WHEN ABS(sm.radiant_score - sm.dire_score) < 5 THEN 'close'
        WHEN ABS(sm.radiant_score - sm.dire_score) < 10 THEN 'moderate'
        WHEN ABS(sm.radiant_score - sm.dire_score) < 20 THEN 'blowout'
        ELSE 'rout'
    END AS score_bucket,
    sm.radiant_team_id,
    sm.dire_team_id,
    sm.has_radiant_team,
    sm.has_dire_team,
    sm.leagueid,
    sm.first_blood_time,
    sm.human_players,
    sm.pre_game_duration,
    sm.loaded_at,
    CASE sm.winner
        WHEN 'radiant' THEN 'Radiant'
        WHEN 'dire' THEN 'Dire'
        ELSE 'Draw'
    END AS winner_name,
    ti.radiant_team_name,
    ti.dire_team_name,
    ti.radiant_team_logo,
    ti.dire_team_logo,
    rh.radiant_heroes,
    dh.dire_heroes
FROM stg_matches sm
LEFT JOIN team_info ti ON ti.match_id = sm.match_id
LEFT JOIN radiant_heroes rh ON rh.match_id = sm.match_id
LEFT JOIN dire_heroes dh ON dh.match_id = sm.match_id
"""
fact_matches = spark.sql(fact_matches_sql)
write_delta(fact_matches, "fact_matches")
print(f"fact_matches rows={fact_matches.count()}")

# ---------------------------------------------------------------------------
# fact_match_players (core columns; enriched dbt-only columns come later)
# ---------------------------------------------------------------------------
fact_players_sql = """
SELECT
    match_id,
    player_slot,
    account_id,
    hero_id,
    team_number,
    CASE WHEN team_number = '0' THEN 'Radiant' ELSE 'Dire' END AS side,
    team_win,
    kills, deaths, assists, kda,
    gold, gold_spent, net_worth, gold_per_min, xp_per_min,
    hero_damage, hero_healing, tower_damage, tower_kills, stuns,
    last_hits, denies, camps_stacked, creeps_stacked, neutral_kills,
    rune_pickups, obs_placed, sen_placed, level,
    item_0, item_1, item_2, item_3, item_4, item_5, item_neutral,
    leaver_status, randomed, firstblood_claimed, buyback_count, loaded_at
FROM stg_match_players
"""
fact_players = spark.sql(fact_players_sql)
write_delta(fact_players, "fact_match_players")
print(f"fact_match_players rows={fact_players.count()}")

# ---------------------------------------------------------------------------
# fact_picks_bans
# ---------------------------------------------------------------------------
fact_picks_sql = """
SELECT
    match_id, order_no, order_no_int, hero_id, is_pick,
    team_number, active_team, player_slot, loaded_at
FROM stg_picks_bans
"""
fact_picks = spark.sql(fact_picks_sql)
write_delta(fact_picks, "fact_picks_bans")
print(f"fact_picks_bans rows={fact_picks.count()}")

spark.stop()
