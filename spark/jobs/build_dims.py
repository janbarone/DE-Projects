"""M1c: build the remaining core dimensions from Spark Delta silver."""
from common import read_gold, read_silver, spark_session, write_delta
from pyspark.sql import functions as F
from pyspark.sql import types as T

spark = spark_session("dota-m1c-dims")
constants = read_silver(spark, "stg_constants")
for name in ("stg_matches", "stg_leagues"):
    read_silver(spark, name).createOrReplaceTempView(name)
read_gold(spark, "dim_hero").createOrReplaceTempView("dim_hero")

gm_schema = T.MapType(
    T.StringType(),
    T.StructType([T.StructField("name", T.StringType()), T.StructField("balanced", T.BooleanType())]),
)
gm = (
    constants.filter(F.col("resource") == "game_mode")
    .select(F.explode(F.from_json("resource_payload", gm_schema)).alias("id", "v"))
    .select(
        F.col("id").alias("game_mode_id"),
        F.upper(F.regexp_replace(F.col("v.name"), "^game_mode_", "")).alias("game_mode_name"),
        F.col("v.balanced").alias("is_balanced"),
    )
)
write_delta(gm, "dim_game_mode")
print(f"dim_game_mode rows={gm.count()}")

lobby = (
    constants.filter(F.col("resource") == "lobby_type")
    .select(F.explode(F.from_json("resource_payload", gm_schema)).alias("id", "v"))
    .select(
        F.col("id").alias("lobby_type_id"),
        F.upper(F.regexp_replace(F.col("v.name"), "^lobby_type_", "")).alias("lobby_type_name"),
        F.col("v.balanced").alias("is_balanced"),
    )
)
write_delta(lobby, "dim_lobby_type")
print(f"dim_lobby_type rows={lobby.count()}")

region = (
    constants.filter(F.col("resource") == "region")
    .select(F.explode(F.from_json("resource_payload", T.MapType(T.StringType(), T.StringType()))).alias("id", "v"))
    .select(F.col("id").alias("region_id"), F.col("v").alias("region_name"))
)
write_delta(region, "dim_region")
print(f"dim_region rows={region.count()}")

item_ids = (
    constants.filter(F.col("resource") == "item_ids")
    .select(F.explode(F.from_json("resource_payload", T.MapType(T.StringType(), T.StringType()))).alias("item_id", "item_internal_name"))
)
items_schema = T.MapType(
    T.StringType(),
    T.StructType([T.StructField("dname", T.StringType()), T.StructField("img", T.StringType())]),
)
items = (
    constants.filter(F.col("resource") == "items")
    .select(F.explode(F.from_json("resource_payload", items_schema)).alias("item_internal_name", "v"))
    .select("item_internal_name", F.col("v.dname").alias("item_name"), F.col("v.img").alias("img"))
)
item_dim = (
    item_ids.join(items, "item_internal_name", "left")
    .select(
        F.col("item_id"),
        F.col("item_internal_name"),
        F.coalesce(F.col("item_name"), F.col("item_internal_name")).alias("item_name"),
        F.when(F.col("img").isNull() | (F.col("img") == ""), F.lit(None))
        .otherwise(F.concat(F.lit("https://cdn.cloudflare.steamstatic.com"), F.col("img")))
        .alias("img"),
    )
)
write_delta(item_dim, "dim_item")
print(f"dim_item rows={item_dim.count()}")

patch_schema = T.ArrayType(
    T.StructType([
        T.StructField("id", T.IntegerType()),
        T.StructField("name", T.StringType()),
        T.StructField("date", T.StringType()),
    ])
)
patch_const = (
    constants.filter(F.col("resource") == "patch")
    .select(F.explode(F.from_json("resource_payload", patch_schema)).alias("e"))
    .select(
        F.col("e.id").cast("string").alias("patch_id"),
        F.col("e.name").alias("patch_name"),
        F.to_date(F.col("e.date")).alias("patch_date"),
    )
)
match_patches = spark.table("stg_matches").select("patch").filter("patch is not null and patch <> ''").distinct().withColumnRenamed("patch", "patch_id")
patch_dim = (
    patch_const.unionByName(match_patches.join(patch_const, "patch_id", "left"))
    .dropDuplicates(["patch_id"])
    .select(
        "patch_id",
        F.coalesce("patch_name", F.lit("Unknown")).alias("patch_name"),
        "patch_date",
        F.coalesce(F.col("patch_id").cast("int"), F.lit(0)).alias("sort_order"),
    )
)
write_delta(patch_dim, "dim_patch")
print(f"dim_patch rows={patch_dim.count()}")

league = spark.sql("""
SELECT leagueid, UPPER(league_name) AS league_name, tier, ticket, banner
FROM stg_leagues
""")
write_delta(league, "dim_league")
print(f"dim_league rows={league.count()}")

hero_roles = (
    spark.table("dim_hero")
    .filter(F.col("hero_id") != "0")
    .select("hero_id", F.explode(F.from_json("roles", T.ArrayType(T.StringType()))).alias("role"))
)
write_delta(hero_roles, "dim_hero_role")
print(f"dim_hero_role rows={hero_roles.count()}")

rune_rows = [
    (0, "Double Damage"), (1, "Haste"), (2, "Illusion"), (3, "Invisibility"),
    (4, "Regeneration"), (5, "Bounty"), (6, "Wisdom"), (7, "Arcane"),
    (8, "Water"), (9, "Shield"),
]
rune = spark.createDataFrame(rune_rows, ["rune_key", "rune_name"])
write_delta(rune, "dim_rune")
print(f"dim_rune rows={rune.count()}")

dim_date = spark.sql("""
SELECT
    d AS date,
    DAYOFMONTH(d) AS day_of_month,
    DAYOFWEEK(d) - 1 AS day_of_week,
    DATE_FORMAT(d, 'EEEE') AS day_of_week_name,
    DATE_FORMAT(d, 'EEE') AS day_of_week_short_name,
    ((DAYOFWEEK(d) + 5) % 7) + 1 AS iso_day_of_week,
    CASE WHEN DAYOFWEEK(d) IN (1, 7) THEN TRUE ELSE FALSE END AS is_weekend,
    DAYOFYEAR(d) AS day_of_year,
    WEEKOFYEAR(d) AS week_of_year,
    WEEKOFYEAR(d) AS iso_week_of_year,
    DATE_TRUNC('WEEK', d) AS week_start_date,
    MONTH(d) AS month,
    DATE_FORMAT(d, 'MMMM') AS month_name,
    DATE_FORMAT(d, 'MMM') AS month_short_name,
    DATE_FORMAT(d, 'yyyy-MM') AS year_month,
    QUARTER(d) AS quarter,
    CONCAT('Q', QUARTER(d)) AS quarter_name,
    CONCAT(YEAR(d), '-Q', QUARTER(d)) AS year_quarter,
    YEAR(d) AS year,
    CONCAT(YEAR(d), '-', DATE_FORMAT(d, 'MMM')) AS year_month_name,
    CASE WHEN (YEAR(d) % 4 = 0 AND YEAR(d) % 100 <> 0) OR YEAR(d) % 400 = 0 THEN TRUE ELSE FALSE END AS is_leap_year
FROM (SELECT EXPLODE(SEQUENCE(TO_DATE('2000-01-01'), TO_DATE('2050-12-31'), INTERVAL 1 DAY)) AS d)
""")
write_delta(dim_date, "dim_date")
print(f"dim_date rows={dim_date.count()}")

spark.stop()
