"""M1b: parse bronze.matches JSONB into Spark silver Delta tables."""
from common import read_table, spark_session, write_delta
from pyspark.sql import functions as F
from pyspark.sql import types as T
from schemas import HERO_RECORD_SCHEMA, PICKS_BANS_SCHEMA, PLAYER_SCHEMA

spark = spark_session("dota-m1-silver")
bronze = read_table(spark, "bronze.matches")


def j(field: str):
    return F.get_json_object("payload", f"$.{field}")


def null_text(expr):
    return F.when(F.trim(expr) == "", F.lit(None)).otherwise(expr)


radiant_win = j("radiant_win").cast("boolean")
radiant_team_id = null_text(j("radiant_team_id"))
dire_team_id = null_text(j("dire_team_id"))
loaded_at = F.coalesce(F.col("source_fetched_at"), F.col("loaded_at"))

# ---------------------------------------------------------------------------
# stg_matches
# ---------------------------------------------------------------------------
stg_matches = bronze.select(
    null_text(j("match_id")).alias("match_id"),
    radiant_win.alias("radiant_win"),
    F.when(radiant_win == F.lit(True), "radiant")
    .when(radiant_win == F.lit(False), "dire")
    .otherwise("draw")
    .alias("winner"),
    null_text(j("duration")).cast("int").alias("duration_sec"),
    null_text(j("game_mode")).alias("game_mode"),
    null_text(j("lobby_type")).alias("lobby_type"),
    null_text(j("region")).alias("region"),
    null_text(j("patch")).alias("patch"),
    F.to_timestamp(F.from_unixtime(null_text(j("start_time")).cast("double"))).alias("start_time"),
    null_text(j("radiant_score")).cast("int").alias("radiant_score"),
    null_text(j("dire_score")).cast("int").alias("dire_score"),
    radiant_team_id.alias("radiant_team_id"),
    dire_team_id.alias("dire_team_id"),
    (radiant_team_id.isNotNull() & (F.trim(radiant_team_id) != "")).alias("has_radiant_team"),
    (dire_team_id.isNotNull() & (F.trim(dire_team_id) != "")).alias("has_dire_team"),
    null_text(j("leagueid")).alias("leagueid"),
    null_text(j("first_blood_time")).cast("int").alias("first_blood_time"),
    null_text(j("human_players")).cast("int").alias("human_players"),
    null_text(j("pre_game_duration")).cast("int").alias("pre_game_duration"),
    null_text(j("replay_salt")).alias("replay_salt"),
    null_text(j("version")).alias("version"),
    loaded_at.alias("loaded_at"),
).filter(F.col("match_id").isNotNull())
write_delta(stg_matches, "stg_matches", "silver")
print(f"stg_matches rows={stg_matches.count()}")

# ---------------------------------------------------------------------------
# stg_match_players
# ---------------------------------------------------------------------------
players = (
    bronze.select(
        null_text(j("match_id")).alias("match_id"),
        radiant_win.alias("radiant_win"),
        loaded_at.alias("loaded_at"),
        F.from_json(j("players"), T.ArrayType(PLAYER_SCHEMA)).alias("players"),
    )
    .filter(F.col("match_id").isNotNull())
    .select("match_id", "radiant_win", "loaded_at", F.explode("players").alias("p"))
)

p = F.col("p")
team_number = p.getField("team_number").cast("string")
team_win = (
    F.when(team_number == "0", F.col("radiant_win"))
    .when(team_number == "1", ~F.col("radiant_win"))
    .otherwise(F.lit(None).cast("boolean"))
)
kills = p.getField("kills").cast("int")
deaths = p.getField("deaths").cast("int")
assists = p.getField("assists").cast("int")
kda = (
    F.when(
        F.coalesce(deaths, F.lit(0)) > 0,
        F.round((kills + assists) / deaths, 2),
    ).otherwise(F.round(kills + assists, 2))
)
obs_placed = F.coalesce(
    F.size(p.getField("obs_log")),
    p.getField("obs_placed").cast("int"),
    F.lit(0),
)
sen_placed = F.coalesce(
    F.size(p.getField("sen_log")),
    p.getField("sen_placed").cast("int"),
    F.lit(0),
)

stg_players = players.select(
    F.col("match_id"),
    p.getField("player_slot").cast("string").alias("player_slot"),
    p.getField("account_id").cast("string").alias("account_id"),
    p.getField("hero_id").cast("string").alias("hero_id"),
    team_number.alias("team_number"),
    team_win.alias("team_win"),
    kills.alias("kills"),
    deaths.alias("deaths"),
    assists.alias("assists"),
    kda.alias("kda"),
    p.getField("gold").cast("int").alias("gold"),
    p.getField("gold_spent").cast("int").alias("gold_spent"),
    p.getField("net_worth").cast("int").alias("net_worth"),
    p.getField("gold_per_min").cast("int").alias("gold_per_min"),
    p.getField("xp_per_min").cast("int").alias("xp_per_min"),
    p.getField("hero_damage").cast("int").alias("hero_damage"),
    p.getField("hero_healing").cast("int").alias("hero_healing"),
    p.getField("tower_damage").cast("int").alias("tower_damage"),
    p.getField("tower_kills").cast("int").alias("tower_kills"),
    p.getField("stuns").cast("double").alias("stuns"),
    p.getField("last_hits").cast("int").alias("last_hits"),
    p.getField("denies").cast("int").alias("denies"),
    p.getField("camps_stacked").cast("int").alias("camps_stacked"),
    p.getField("creeps_stacked").cast("int").alias("creeps_stacked"),
    p.getField("neutral_kills").cast("int").alias("neutral_kills"),
    p.getField("rune_pickups").cast("int").alias("rune_pickups"),
    obs_placed.alias("obs_placed"),
    sen_placed.alias("sen_placed"),
    p.getField("observer_kills").cast("int").alias("observer_kills"),
    p.getField("sentry_kills").cast("int").alias("sentry_kills"),
    p.getField("purchase_ward_observer").cast("int").alias("purchase_ward_observer"),
    p.getField("purchase_ward_sentry").cast("int").alias("purchase_ward_sentry"),
    p.getField("personaname").cast("string").alias("personaname"),
    p.getField("level").cast("string").alias("level"),
    p.getField("item_0").cast("string").alias("item_0"),
    p.getField("item_1").cast("string").alias("item_1"),
    p.getField("item_2").cast("string").alias("item_2"),
    p.getField("item_3").cast("string").alias("item_3"),
    p.getField("item_4").cast("string").alias("item_4"),
    p.getField("item_5").cast("string").alias("item_5"),
    p.getField("item_neutral").cast("string").alias("item_neutral"),
    p.getField("backpack_0").cast("string").alias("backpack_0"),
    p.getField("backpack_1").cast("string").alias("backpack_1"),
    p.getField("backpack_2").cast("string").alias("backpack_2"),
    p.getField("backpack_3").cast("string").alias("backpack_3"),
    p.getField("leaver_status").cast("string").alias("leaver_status"),
    p.getField("randomed").cast("boolean").alias("randomed"),
    p.getField("firstblood_claimed").cast("int").alias("firstblood_claimed"),
    p.getField("buyback_count").cast("int").alias("buyback_count"),
    F.col("loaded_at"),
)
write_delta(stg_players, "stg_match_players", "silver")
print(f"stg_match_players rows={stg_players.count()}")

# ---------------------------------------------------------------------------
# stg_picks_bans
# ---------------------------------------------------------------------------
picks = (
    bronze.select(
        null_text(j("match_id")).alias("match_id"),
        loaded_at.alias("loaded_at"),
        F.from_json(j("picks_bans"), PICKS_BANS_SCHEMA).alias("picks"),
    )
    .filter(F.col("match_id").isNotNull())
    .select("match_id", "loaded_at", F.explode("picks").alias("pb"))
)
pb = F.col("pb")
stg_picks = picks.select(
    F.col("match_id"),
    pb.getField("order").cast("string").alias("order_no"),
    pb.getField("order").cast("int").alias("order_no_int"),
    pb.getField("hero_id").cast("string").alias("hero_id"),
    pb.getField("is_pick").cast("boolean").alias("is_pick"),
    pb.getField("team").cast("string").alias("team_number"),
    F.when(pb.getField("team") == 0, "Radiant")
    .when(pb.getField("team") == 1, "Dire")
    .otherwise(F.lit(None))
    .alias("active_team"),
    pb.getField("player_slot").cast("string").alias("player_slot"),
    F.col("loaded_at"),
)
write_delta(stg_picks, "stg_picks_bans", "silver")
print(f"stg_picks_bans rows={stg_picks.count()}")

# ---------------------------------------------------------------------------
# Reference silver tables used by the gold dimensions
# ---------------------------------------------------------------------------
constants = read_table(spark, "bronze.constants")
hero_map = (
    constants.filter(F.col("resource") == "heroes")
    .select(F.from_json("payload", T.MapType(T.StringType(), HERO_RECORD_SCHEMA)).alias("heroes"))
    .select(F.explode("heroes").alias("hero_id", "h"))
    .select(
        F.col("hero_id"),
        F.col("h.name").alias("hero_name"),
        F.col("h.localized_name").alias("localized_name"),
        F.col("h.primary_attr").alias("primary_attr"),
        F.col("h.attack_type").alias("attack_type"),
        F.to_json(F.col("h.roles")).alias("roles"),
        F.col("h.img").alias("img"),
    )
)
write_delta(hero_map, "stg_heroes", "silver")
print(f"stg_heroes rows={hero_map.count()}")

hero_stats_bronze = read_table(spark, "bronze.hero_stats")
hero_stats = hero_stats_bronze.select(
    null_text(j("id")).alias("hero_id"),
    null_text(j("pro_pick")).cast("int").alias("pro_pick"),
    null_text(j("pro_win")).cast("int").alias("pro_win"),
    null_text(j("pro_ban")).cast("int").alias("pro_ban"),
    null_text(j("pub_pick")).cast("int").alias("pub_pick"),
    null_text(j("pub_win")).cast("int").alias("pub_win"),
    F.when(
        null_text(j("pub_pick")).cast("int") > 0,
        F.round(
            100.0 * null_text(j("pub_win")).cast("double")
            / null_text(j("pub_pick")).cast("double"),
            2,
        ),
    ).otherwise(F.lit(None)).alias("pub_win_rate"),
)
write_delta(hero_stats, "stg_hero_stats", "silver")
print(f"stg_hero_stats rows={hero_stats.count()}")

teams_bronze = read_table(spark, "bronze.teams")
teams = teams_bronze.select(
    null_text(j("team_id")).alias("team_id"),
    null_text(j("name")).alias("team_name"),
    null_text(j("tag")).alias("team_tag"),
    null_text(j("rating")).cast("double").alias("rating"),
    null_text(j("wins")).cast("int").alias("wins"),
    null_text(j("losses")).cast("int").alias("losses"),
    null_text(j("logo_url")).alias("logo_url"),
).filter(F.col("team_id").isNotNull())
write_delta(teams, "stg_teams", "silver")
print(f"stg_teams rows={teams.count()}")

players_bronze = read_table(spark, "bronze.players")
players_ref = players_bronze.select(
    null_text(j("account_id")).alias("account_id"),
    null_text(j("name")).alias("player_name"),
    null_text(j("rank_tier")).alias("rank_tier"),
    null_text(j("team_id")).alias("team_id"),
    null_text(j("avatarmedium")).alias("avatar_medium"),
).filter(F.col("account_id").isNotNull())
write_delta(players_ref, "stg_players", "silver")
print(f"stg_players rows={players_ref.count()}")

leagues_bronze = read_table(spark, "bronze.leagues")
leagues_ref = leagues_bronze.select(
    null_text(j("leagueid")).alias("leagueid"),
    null_text(j("name")).alias("league_name"),
    null_text(j("tier")).alias("tier"),
    null_text(j("ticket")).alias("ticket"),
    null_text(j("banner")).alias("banner"),
).filter(F.col("leagueid").isNotNull())
write_delta(leagues_ref, "stg_leagues", "silver")
print(f"stg_leagues rows={leagues_ref.count()}")

constants_bronze = read_table(spark, "bronze.constants")
constants_ref = constants_bronze.select(
    F.col("resource"),
    F.col("payload").alias("resource_payload"),
    F.col("loaded_at"),
)
write_delta(constants_ref, "stg_constants", "silver")
print(f"stg_constants rows={constants_ref.count()}")

spark.stop()
