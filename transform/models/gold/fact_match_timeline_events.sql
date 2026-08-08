{{ config(
    materialized='table',
    post_hook=[
        "create index if not exists {{ this.schema }}_fact_tle_match_idx on {{ this }}(match_id)",
        "create index if not exists {{ this.schema }}_fact_tle_min_idx on {{ this }}(start_min)",
        "create index if not exists {{ this.schema }}_fact_tle_player_idx on {{ this }}(player_slot)"
    ]
) }}

-- One row per (match, teamfight, player, item/ability use): the chronological
-- breakdown of what every player used in every teamfight, ordered by fight
-- minute. Items are decoded to display names via dim_item.item_internal_name;
-- abilities keep their internal names (no ability decode dimension exists).
-- Pre-game fights are excluded. Player/hero names are denormalized from
-- dim_player / dim_hero so the Match Detail page needs no extra relationships.
--
-- The `kind` column distinguishes 'Item' vs 'Ability' rows. `uses` is the
-- number of times that item/ability was used by that player in that fight.
-- gold_delta / xp_delta / deaths are that player's swing in the fight.
with fights as (
    select
        match_id,
        teamfight_id,
        start_min
    from {{ ref('fact_teamfights') }}
    where fight_phase <> 'pre-game'
),
players as (
    select
        ftp.match_id,
        ftp.teamfight_id,
        f.start_min,
        ftp.player_slot,
        ftp.hero_id,
        ftp.account_id,
        case when ftp.player_slot::int < 128 then 'Radiant' else 'Dire' end as side,
        coalesce(ftp.gold_delta, 0) as gold_delta,
        coalesce(ftp.xp_delta, 0)   as xp_delta,
        coalesce(ftp.deaths, 0)     as deaths,
        ftp.item_uses,
        ftp.ability_uses
    from {{ ref('fact_teamfight_players') }} ftp
    inner join fights f
        on f.match_id = ftp.match_id
       and f.teamfight_id = ftp.teamfight_id
),
item_uses as (
    select
        p.match_id,
        p.teamfight_id,
        p.start_min,
        p.player_slot,
        p.account_id,
        p.hero_id,
        p.side,
        p.gold_delta,
        p.xp_delta,
        p.deaths,
        dp.player_name,
        dh.hero_localized_name,
        'Item' as kind,
        coalesce(di.item_name, kv.key) as name,
        sum(kv.value::int) as uses
    from players p
    cross join lateral jsonb_each_text(p.item_uses::jsonb) as kv
    left join {{ ref('dim_item') }} di
        on di.item_internal_name = kv.key
    left join {{ ref('dim_player') }} dp on dp.account_id = p.account_id
    left join {{ ref('dim_hero') }} dh on dh.hero_id = p.hero_id
    where kv.value::int > 0
    group by p.match_id, p.teamfight_id, p.start_min, p.player_slot, p.account_id, p.hero_id,
             p.side, p.gold_delta, p.xp_delta, p.deaths, dp.player_name, dh.hero_localized_name,
             coalesce(di.item_name, kv.key)
),
ability_uses as (
    select
        p.match_id,
        p.teamfight_id,
        p.start_min,
        p.player_slot,
        p.account_id,
        p.hero_id,
        p.side,
        p.gold_delta,
        p.xp_delta,
        p.deaths,
        dp.player_name,
        dh.hero_localized_name,
        'Ability' as kind,
        kv.key as name,
        sum(kv.value::int) as uses
    from players p
    cross join lateral jsonb_each_text(p.ability_uses::jsonb) as kv
    left join {{ ref('dim_player') }} dp on dp.account_id = p.account_id
    left join {{ ref('dim_hero') }} dh on dh.hero_id = p.hero_id
    where kv.value::int > 0
    group by p.match_id, p.teamfight_id, p.start_min, p.player_slot, p.account_id, p.hero_id,
             p.side, p.gold_delta, p.xp_delta, p.deaths, dp.player_name, dh.hero_localized_name, kv.key
),
unioned as (
    select * from item_uses
    union all
    select * from ability_uses
)
select
    match_id,
    teamfight_id,
    start_min,
    side,
    player_slot,
    account_id,
    hero_id,
    player_name,
    hero_localized_name,
    kind,
    name,
    uses,
    gold_delta,
    xp_delta,
    deaths
from unioned
order by start_min, player_slot, kind, uses desc
