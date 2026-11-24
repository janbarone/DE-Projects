"""M1c: dim_player from pro players, match participants, and player stats."""
from common import DELTA_DIR, read_silver, spark_session, write_delta
from pyspark.sql import functions as F
from pyspark.sql.window import Window

spark = spark_session("dota-m1c-player-dim")
for name in ("stg_players", "stg_match_players"):
    read_silver(spark, name).createOrReplaceTempView(name)
spark.read.format("delta").load(f"{DELTA_DIR}/gold/fact_match_players").createOrReplaceTempView("fact_match_players")

pro_players = spark.table("stg_players").select(
    "account_id", "player_name", "rank_tier", "team_id", "avatar_medium",
    F.lit("Pro").alias("player_type"),
)
participants = (
    spark.table("stg_match_players")
    .join(pro_players.select("account_id"), "account_id", "left_anti")
    .filter(F.col("account_id").isNotNull())
    .withColumn("rn", F.row_number().over(Window.partitionBy("account_id").orderBy(F.col("loaded_at").desc_nulls_last())))
    .filter(F.col("rn") == 1)
    .select(
        "account_id", F.col("personaname").alias("player_name"),
        F.lit(None).cast("string").alias("rank_tier"),
        F.lit(None).cast("string").alias("team_id"),
        F.lit(None).cast("string").alias("avatar_medium"),
        F.lit("Match Participant").alias("player_type"),
    )
)
player_dim = pro_players.unionByName(participants)
player_stats = spark.sql("""
SELECT account_id,
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
       CAST(SUM(CASE WHEN firstblood_claimed = 1 THEN 1 ELSE 0 END) AS INT) AS match_firstbloods,
       ROUND(AVG(rune_pickups), 2) AS match_avg_rune_pickups,
       ROUND(AVG(buyback_count), 2) AS match_avg_buybacks
FROM fact_match_players GROUP BY account_id
""")
player_dim = (
    player_dim.join(player_stats, "account_id", "left")
    .select(
        "account_id", "player_name", "rank_tier", "team_id", "avatar_medium", "player_type",
        F.coalesce("match_picks", F.lit(0)).alias("match_picks"),
        F.coalesce("match_wins", F.lit(0)).alias("match_wins"),
        F.coalesce("match_win_rate", F.lit(0)).alias("match_win_rate"),
        "match_avg_kda", "match_avg_gpm", "match_avg_xpm", "match_avg_hero_damage",
        "match_avg_tower_damage", "match_avg_hero_healing", "match_avg_last_hits",
        "match_avg_denies", "match_avg_net_worth", "match_avg_stuns", "match_avg_level",
        F.coalesce("match_total_kills", F.lit(0)).alias("match_total_kills"),
        F.coalesce("match_total_deaths", F.lit(0)).alias("match_total_deaths"),
        F.coalesce("match_total_assists", F.lit(0)).alias("match_total_assists"),
        F.coalesce("match_firstbloods", F.lit(0)).alias("match_firstbloods"),
        "match_avg_rune_pickups", "match_avg_buybacks",
    )
)
write_delta(player_dim, "dim_player")
print(f"dim_player rows={player_dim.count()}")
spark.stop()
