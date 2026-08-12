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
--
-- Enriched columns (materialized, filter-static by design):
--   side           'Radiant' / 'Dire' derived from team_number
--   hero_games     total appearances of this hero (team_win known)
--   hero_win_rate  all-time win rate of this hero (0..1)
--   item_*_name    decoded item names for item_0..5 and item_neutral
--   top_skills     top-3 abilities by total uses across this match's teamfights
--   gold_early/mid/late   team gold swing in each fight phase
--   xp_early/mid/late     team XP swing in each fight phase
with team_comps as (
    select
        match_id,
        team_number,
        string_agg(hero_id, '_' order by hero_id) as comp_sig
    from {{ ref('stg_match_players') }}
    group by match_id, team_number
),
hero_stats as (
    select
        hero_id,
        count(*) as hero_games,
        count(*) filter (where team_win) as hero_wins,
        round(1.0 * count(*) filter (where team_win) / nullif(count(*), 0), 4) as hero_win_rate
    from {{ ref('stg_match_players') }}
    where hero_id <> '0'
      and team_win is not null
    group by hero_id
),
skills as (
    select
        match_id,
        player_slot,
        string_agg(ability || ' x' || uses, ', ' order by uses desc) as top_skills
    from (
        select
            match_id,
            player_slot,
            ability_name as ability,
            sum(uses) as uses,
            row_number() over (
                partition by match_id, player_slot
                order by sum(uses) desc
            ) as rn
        from {{ ref('fact_teamfight_ability_uses') }}
        group by match_id, player_slot, ability_name
    ) t
    where rn <= 3
    group by match_id, player_slot
),
momentum as (
    select
        match_id,
        team_number,
        max(case when phase_ord = 0 then gold_delta end) as gold_early,
        max(case when phase_ord = 1 then gold_delta end) as gold_mid,
        max(case when phase_ord = 2 then gold_delta end) as gold_late,
        max(case when phase_ord = 0 then xp_delta end) as xp_early,
        max(case when phase_ord = 1 then xp_delta end) as xp_mid,
        max(case when phase_ord = 2 then xp_delta end) as xp_late
    from {{ ref('fact_phase_momentum') }}
    group by match_id, team_number
),
pick_order as (
    select
        match_id,
        hero_id,
        max(case when is_pick = '1' then seq end) as pick_sequence,
        max(case when is_pick = '0' then seq end) as ban_sequence
    from (
        select
            p.match_id,
            p.hero_id,
            p.is_pick,
            row_number() over (
                partition by p.match_id, p.is_pick
                order by nullif(p.order_no, '')::int
            ) as seq
        from {{ ref('fact_picks_bans') }} p
    ) d
    group by match_id, hero_id
),
enemy_kills as (
    select
        match_id,
        player_slot,
        count(*) as enemy_heroes_killed
    from {{ ref('stg_match_player_kills') }}
    group by match_id, player_slot
),
support_items as (
    select
        match_id,
        player_slot,
        count(*) filter (where item_internal_name = 'ward_observer') as ward_observer_bought,
        count(*) filter (where item_internal_name = 'ward_sentry')   as ward_sentry_bought,
        count(*) filter (where item_internal_name = 'dust')          as dust_bought,
        count(*) filter (where item_internal_name = 'smoke_of_deceit') as smoke_bought,
        count(*) filter (where item_internal_name = 'gem')           as gem_bought,
        -- support gold: sum of (count bought x current item cost) for the
        -- support items. Observer ward costs 0 in current constants.
        coalesce(count(*) filter (where item_internal_name = 'ward_observer') * 0, 0)
        + coalesce(count(*) filter (where item_internal_name = 'ward_sentry') * 50, 0)
        + coalesce(count(*) filter (where item_internal_name = 'dust') * 80, 0)
        + coalesce(count(*) filter (where item_internal_name = 'smoke_of_deceit') * 50, 0)
        + coalesce(count(*) filter (where item_internal_name = 'gem') * 900, 0)
            as support_gold
    from {{ ref('stg_match_player_item_purchases') }}
    group by match_id, player_slot
),
damage_taken_type as (
    select
        match_id,
        player_slot,
        sum(damage_amount) filter (where damage_type = 'Physical') as damage_taken_physical,
        sum(damage_amount) filter (where damage_type = 'Magical')  as damage_taken_magical,
        sum(damage_amount) filter (where damage_type = 'Pure')     as damage_taken_pure
    from {{ ref('stg_match_player_damage_taken_type') }}
    group by match_id, player_slot
)
select
    mp.match_id,
    mp.player_slot,
    mp.account_id,
    mp.hero_id,
    mp.team_number,
    case when mp.team_number = '0' then 'Radiant' else 'Dire' end as side,
    mp.team_win,
    tc.comp_sig,
    hs.hero_games,
    hs.hero_win_rate,
    s.top_skills,
    di0.item_name as item_0_name,
    di1.item_name as item_1_name,
    di2.item_name as item_2_name,
    di3.item_name as item_3_name,
    di4.item_name as item_4_name,
    di5.item_name as item_5_name,
    din.item_name as item_neutral_name,
    mo.gold_early,
    mo.gold_mid,
    mo.gold_late,
    mo.xp_early,
    mo.xp_mid,
    mo.xp_late,
    mp.kills,
    mp.deaths,
    mp.assists,
    mp.kda,
    mp.gold,
    mp.gold_spent,
    mp.net_worth,
    mp.gold_per_min,
    mp.xp_per_min,
    mp.hero_damage,
    mp.hero_healing,
    mp.tower_damage,
    mp.tower_kills,
    mp.stuns,
    mp.last_hits,
    mp.denies,
    mp.camps_stacked,
    mp.creeps_stacked,
    mp.neutral_kills,
    mp.rune_pickups,
    mp.obs_placed,
    mp.sen_placed,
    mp.observer_kills,
    mp.sentry_kills,
    mp.purchase_ward_observer,
    mp.purchase_ward_sentry,
    mp.level,
    po.pick_sequence,
    po.ban_sequence,
    ek.enemy_heroes_killed,
    si.ward_observer_bought,
    si.ward_sentry_bought,
    si.dust_bought,
    si.smoke_bought,
    si.gem_bought,
    si.support_gold,
    dtt.damage_taken_physical,
    dtt.damage_taken_magical,
    dtt.damage_taken_pure,
    mp.item_0,
    mp.item_1,
    mp.item_2,
    mp.item_3,
    mp.item_4,
    mp.item_5,
    mp.item_neutral,
    mp.backpack_0,
    mp.backpack_1,
    mp.backpack_2,
    mp.backpack_3,
    mp.leaver_status,
    mp.randomed,
    mp.firstblood_claimed,
    mp.buyback_count,
    mp.loaded_at
from {{ ref('stg_match_players') }} mp
left join team_comps tc
    on mp.match_id = tc.match_id
    and mp.team_number = tc.team_number
left join hero_stats hs
    on mp.hero_id = hs.hero_id
left join skills s
    on s.match_id = mp.match_id
    and s.player_slot = mp.player_slot
left join {{ ref('dim_item') }} di0 on di0.item_id = mp.item_0
left join {{ ref('dim_item') }} di1 on di1.item_id = mp.item_1
left join {{ ref('dim_item') }} di2 on di2.item_id = mp.item_2
left join {{ ref('dim_item') }} di3 on di3.item_id = mp.item_3
left join {{ ref('dim_item') }} di4 on di4.item_id = mp.item_4
left join {{ ref('dim_item') }} di5 on di5.item_id = mp.item_5
left join {{ ref('dim_item') }} din on din.item_id = mp.item_neutral
left join momentum mo
    on mo.match_id = mp.match_id
    and mo.team_number = mp.team_number
left join pick_order po
    on po.match_id = mp.match_id
    and po.hero_id = mp.hero_id
left join enemy_kills ek
    on ek.match_id = mp.match_id
    and ek.player_slot = mp.player_slot
left join support_items si
    on si.match_id = mp.match_id
    and si.player_slot = mp.player_slot
left join damage_taken_type dtt
    on dtt.match_id = mp.match_id
    and dtt.player_slot = mp.player_slot
