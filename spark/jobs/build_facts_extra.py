"""M1c: build the remaining core facts from Spark Delta silver/gold."""
from common import DELTA_DIR, read_silver, spark_session, write_delta
from pyspark.sql import functions as F

spark = spark_session("dota-m1c-facts")
for name in ("stg_matches", "stg_picks_bans"):
    read_silver(spark, name).createOrReplaceTempView(name)
for name in ("fact_matches", "fact_match_players", "dim_hero", "dim_team"):
    spark.read.format("delta").load(f"{DELTA_DIR}/gold/{name}").createOrReplaceTempView(name)

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

fact_team_matches = spark.sql("""
WITH league_stats AS (
    SELECT sm.leagueid, tr.team_id, COUNT(*) AS games,
           SUM(CASE WHEN tr.team_win THEN 1 ELSE 0 END) AS wins,
           ROUND(SUM(CASE WHEN tr.team_win THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0), 4) AS win_rate
    FROM team_rows tr JOIN stg_matches sm ON sm.match_id = tr.match_id
    GROUP BY sm.leagueid, tr.team_id
),
league_ranks AS (
    SELECT leagueid, team_id,
           ROW_NUMBER() OVER (PARTITION BY leagueid ORDER BY wins DESC, win_rate DESC, team_id ASC) AS league_rank
    FROM league_stats
)
SELECT tr.match_id, tr.side, tr.team_id, tr.radiant_win, tr.team_win,
       tr.team_score, tr.opponent_score, lr.league_rank
FROM team_rows tr
LEFT JOIN stg_matches sm ON sm.match_id = tr.match_id
LEFT JOIN league_ranks lr ON lr.leagueid = sm.leagueid AND lr.team_id = tr.team_id
""")
write_delta(fact_team_matches, "fact_team_matches")
print(f"fact_team_matches rows={fact_team_matches.count()}")

fact_hero_side = spark.sql("""
SELECT hero_id, side,
       CAST(COUNT(*) AS INT) AS hero_side_picks,
       CAST(SUM(CASE WHEN team_win THEN 1 ELSE 0 END) AS INT) AS hero_side_wins,
       ROUND(SUM(CASE WHEN team_win THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0), 4) AS hero_side_win_rate
FROM fact_match_players
WHERE side IN ('Radiant', 'Dire')
GROUP BY hero_id, side
""")
write_delta(fact_hero_side, "fact_hero_side")
print(f"fact_hero_side rows={fact_hero_side.count()}")

fact_hero_matchups = spark.sql("""
WITH r AS (
    SELECT match_id, hero_id FROM fact_match_players
    WHERE team_number = '0' AND hero_id <> '0'
),
d AS (
    SELECT match_id, hero_id FROM fact_match_players
    WHERE team_number = '1' AND hero_id <> '0'
)
SELECT m.match_id, r.hero_id AS radiant_hero_id, d.hero_id AS dire_hero_id,
       rh.hero_localized_name || ' vs ' || dh.hero_localized_name AS matchup_label,
       m.radiant_win
FROM r
JOIN fact_matches m ON r.match_id = m.match_id
JOIN d ON r.match_id = d.match_id
LEFT JOIN dim_hero rh ON rh.hero_id = r.hero_id
LEFT JOIN dim_hero dh ON dh.hero_id = d.hero_id
WHERE m.radiant_win IS NOT NULL
""")
write_delta(fact_hero_matchups, "fact_hero_matchups")
print(f"fact_hero_matchups rows={fact_hero_matchups.count()}")
fact_hero_matchups.createOrReplaceTempView("fact_hero_matchups")

fact_matchup_stats = spark.sql("""
SELECT matchup_label,
       CAST(COUNT(*) AS INT) AS matchup_games,
       CAST(SUM(CASE WHEN radiant_win THEN 1 ELSE 0 END) AS INT) AS radiant_wins,
       CAST(SUM(CASE WHEN NOT radiant_win THEN 1 ELSE 0 END) AS INT) AS dire_wins,
       ROUND(SUM(CASE WHEN radiant_win THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0), 4) AS radiant_win_rate,
       ROUND(SUM(CASE WHEN NOT radiant_win THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0), 4) AS dire_win_rate
FROM fact_hero_matchups GROUP BY matchup_label
""")
write_delta(fact_matchup_stats, "fact_hero_matchup_stats")
print(f"fact_hero_matchup_stats rows={fact_matchup_stats.count()}")

fact_matchups_hero = spark.sql("""
WITH rp AS (
    SELECT m.match_id, m.radiant_hero_id AS hero_id, m.dire_hero_id AS opponent_id,
           hh.hero_localized_name AS hero_name, oh.hero_localized_name AS opponent_name,
           hh.hero_localized_name || ' vs ' || oh.hero_localized_name AS matchup_label,
           m.radiant_win AS hero_win
    FROM fact_hero_matchups m
    JOIN dim_hero hh ON hh.hero_id = m.radiant_hero_id
    JOIN dim_hero oh ON oh.hero_id = m.dire_hero_id
),
dp AS (
    SELECT m.match_id, m.dire_hero_id AS hero_id, m.radiant_hero_id AS opponent_id,
           hh.hero_localized_name AS hero_name, oh.hero_localized_name AS opponent_name,
           hh.hero_localized_name || ' vs ' || oh.hero_localized_name AS matchup_label,
           NOT m.radiant_win AS hero_win
    FROM fact_hero_matchups m
    JOIN dim_hero hh ON hh.hero_id = m.dire_hero_id
    JOIN dim_hero oh ON oh.hero_id = m.radiant_hero_id
)
SELECT * FROM (SELECT * FROM rp UNION ALL SELECT * FROM dp) x
WHERE hero_id <> opponent_id
""")
write_delta(fact_matchups_hero, "fact_hero_matchups_hero")
print(f"fact_hero_matchups_hero rows={fact_matchups_hero.count()}")

fact_team_h2h = spark.sql("""
SELECT m.match_id,
       LEAST(m.radiant_team_id, m.dire_team_id) AS team_a_id,
       GREATEST(m.radiant_team_id, m.dire_team_id) AS team_b_id,
       ta.team_name AS team_a_name,
       tb.team_name AS team_b_name,
       CASE WHEN m.radiant_team_id < m.dire_team_id THEN m.radiant_win ELSE NOT m.radiant_win END AS team_a_win,
       CASE WHEN m.radiant_team_id < m.dire_team_id THEN m.radiant_score ELSE m.dire_score END AS team_a_score,
       CASE WHEN m.radiant_team_id < m.dire_team_id THEN m.dire_score ELSE m.radiant_score END AS team_b_score
FROM fact_matches m
LEFT JOIN dim_team ta ON ta.team_id = LEAST(m.radiant_team_id, m.dire_team_id)
LEFT JOIN dim_team tb ON tb.team_id = GREATEST(m.radiant_team_id, m.dire_team_id)
WHERE m.has_radiant_team AND m.has_dire_team AND m.radiant_win IS NOT NULL
""")
write_delta(fact_team_h2h, "fact_team_h2h")
print(f"fact_team_h2h rows={fact_team_h2h.count()}")

pb = spark.sql("""
SELECT match_id, order_no_int, is_pick, active_team, hero_id,
       ROW_NUMBER() OVER (PARTITION BY match_id, active_team, is_pick ORDER BY order_no_int) AS team_seq,
       ROW_NUMBER() OVER (PARTITION BY match_id, is_pick ORDER BY order_no_int) AS global_seq
FROM stg_picks_bans
""")
pb.createOrReplaceTempView("pb")
max_slot = pb.agg(F.max("team_seq")).first()[0] or 5
spark.range(1, int(max_slot) + 1).select(F.col("id").cast("int").alias("slot")).createOrReplaceTempView("slots")
fact_draft = spark.sql("""
WITH matches AS (SELECT DISTINCT match_id FROM pb),
grid AS (SELECT m.match_id, s.slot FROM matches m CROSS JOIN slots s),
base AS (
    SELECT g.match_id, g.slot,
           dp.hero_id AS dire_pick_hero_id, dp.global_seq AS dire_pick_seq,
           db.hero_id AS dire_ban_hero_id, db.global_seq AS dire_ban_seq,
           rp.hero_id AS radiant_pick_hero_id, rp.global_seq AS radiant_pick_seq,
           rb.hero_id AS radiant_ban_hero_id, rb.global_seq AS radiant_ban_seq
    FROM grid g
    LEFT JOIN pb dp ON dp.match_id = g.match_id AND dp.team_seq = g.slot AND dp.active_team = 'Dire' AND dp.is_pick
    LEFT JOIN pb db ON db.match_id = g.match_id AND db.team_seq = g.slot AND db.active_team = 'Dire' AND NOT db.is_pick
    LEFT JOIN pb rp ON rp.match_id = g.match_id AND rp.team_seq = g.slot AND rp.active_team = 'Radiant' AND rp.is_pick
    LEFT JOIN pb rb ON rb.match_id = g.match_id AND rb.team_seq = g.slot AND rb.active_team = 'Radiant' AND NOT rb.is_pick
)
SELECT b.match_id, b.slot,
       dp.hero_localized_name AS dire_pick_hero, dp.img AS dire_pick_hero_img,
       b.dire_pick_seq,
       db.hero_localized_name AS dire_ban_hero, db.img AS dire_ban_hero_img,
       b.dire_ban_seq,
       rp.hero_localized_name AS radiant_pick_hero, rp.img AS radiant_pick_hero_img,
       b.radiant_pick_seq,
       rb.hero_localized_name AS radiant_ban_hero, rb.img AS radiant_ban_hero_img,
       b.radiant_ban_seq
FROM base b
LEFT JOIN dim_hero dp ON dp.hero_id = b.dire_pick_hero_id
LEFT JOIN dim_hero db ON db.hero_id = b.dire_ban_hero_id
LEFT JOIN dim_hero rp ON rp.hero_id = b.radiant_pick_hero_id
LEFT JOIN dim_hero rb ON rb.hero_id = b.radiant_ban_hero_id
""")
write_delta(fact_draft, "fact_draft_sequence")
print(f"fact_draft_sequence rows={fact_draft.count()}")

spark.stop()
