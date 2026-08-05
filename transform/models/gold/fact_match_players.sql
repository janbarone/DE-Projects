{{ config(
    materialized='table',
    post_hook=[
        "create index if not exists {{ this.schema }}_fact_mp_match_idx on {{ this }}(match_id)",
        "create index if not exists {{ this.schema }}_fact_mp_account_idx on {{ this }}(account_id)",
        "create index if not exists {{ this.schema }}_fact_mp_hero_idx on {{ this }}(hero_id)"
    ]
) }}

-- One row per (match, player): player performance fact.
-- hero_id = 0 (OpenDota placeholder) is preserved and resolves to the
-- 'Unknown' row in dim_hero; account_id resolves to dim_player (all match
-- participants are covered there).
select
    match_id,
    player_slot,
    account_id,
    hero_id,
    team_number,
    team_win,
    kills,
    deaths,
    assists,
    kda,
    gold,
    gold_spent,
    net_worth,
    gold_per_min,
    xp_per_min,
    hero_damage,
    hero_healing,
    tower_damage,
    tower_kills,
    stuns,
    last_hits,
    denies,
    camps_stacked,
    creeps_stacked,
    neutral_kills,
    rune_pickups,
    level,
    item_0,
    item_1,
    item_2,
    item_3,
    item_4,
    item_5,
    item_neutral,
    backpack_0,
    backpack_1,
    backpack_2,
    backpack_3,
    leaver_status,
    randomed,
    firstblood_claimed,
    buyback_count,
    loaded_at
from {{ ref('stg_match_players') }}
