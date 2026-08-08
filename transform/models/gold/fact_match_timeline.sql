{{ config(
    materialized='table',
    post_hook=[
        "create index if not exists {{ this.schema }}_fact_tl_match_idx on {{ this }}(match_id)",
        "create index if not exists {{ this.schema }}_fact_tl_team_idx on {{ this }}(team_number)",
        "create index if not exists {{ this.schema }}_fact_tl_min_idx on {{ this }}(start_min)"
    ]
) }}

-- One row per (match, side, teamfight): a time-progression view of each team
-- through the match. For every teamfight (ordered by game minute) this shows
-- the top items and abilities that team actually used in that fight, plus the
-- team's gold/XP swing and deaths. Use it like a match timeline: as start_min
-- increases, you see which items/skills each side was leaning on at that point
-- in the game.
--
-- Item keys from OpenDota's teamfight payload (e.g. 'blink', 'power_treads')
-- are joined to dim_item.item_internal_name for display names. Abilities keep
-- their internal names (there is no ability decode dimension).
--
-- Pre-game fights (start_time < 0) are excluded.
with team_players as (
    select
        ftp.match_id,
        ftp.teamfight_id,
        tf.start_time,
        tf.start_min,
        case when ftp.player_slot::int < 128 then '0' else '1' end as team_number,
        ftp.gold_delta,
        ftp.xp_delta,
        ftp.deaths,
        ftp.item_uses,
        ftp.ability_uses
    from {{ ref('fact_teamfight_players') }} ftp
    inner join {{ ref('fact_teamfights') }} tf
        on tf.match_id = ftp.match_id
       and tf.teamfight_id = ftp.teamfight_id
    where tf.fight_phase <> 'pre-game'
),
team_agg as (
    select
        match_id,
        teamfight_id,
        team_number,
        min(start_time) as start_time,
        min(start_min) as start_min,
        sum(coalesce(gold_delta, 0)) as gold_delta,
        sum(coalesce(xp_delta, 0))   as xp_delta,
        sum(coalesce(deaths, 0))     as deaths
    from team_players
    group by match_id, teamfight_id, team_number
),
item_uses as (
    select
        tp.match_id,
        tp.teamfight_id,
        tp.team_number,
        di.item_name,
        sum(kv.value::int) as uses
    from team_players tp,
         jsonb_each_text(tp.item_uses::jsonb) as kv
    left join {{ ref('dim_item') }} di
        on di.item_internal_name = kv.key
    where kv.value::int > 0
    group by tp.match_id, tp.teamfight_id, tp.team_number, di.item_name
),
ability_uses as (
    select
        tp.match_id,
        tp.teamfight_id,
        tp.team_number,
        kv.key as ability_name,
        sum(kv.value::int) as uses
    from team_players tp,
         jsonb_each_text(tp.ability_uses::jsonb) as kv
    where kv.value::int > 0
    group by tp.match_id, tp.teamfight_id, tp.team_number, kv.key
),
top_items as (
    select
        match_id,
        teamfight_id,
        team_number,
        string_agg(item_label, ', ' order by uses desc) as items_used
    from (
        select
            match_id,
            teamfight_id,
            team_number,
            item_name,
            uses,
            coalesce(item_name, '?') || ' x' || uses as item_label,
            row_number() over (
                partition by match_id, teamfight_id, team_number
                order by uses desc
            ) as rn
        from item_uses
    ) t
    where rn <= 4
    group by match_id, teamfight_id, team_number
),
top_abilities as (
    select
        match_id,
        teamfight_id,
        team_number,
        string_agg(ability_label, ', ' order by uses desc) as abilities_used
    from (
        select
            match_id,
            teamfight_id,
            team_number,
            ability_name,
            uses,
            ability_name || ' x' || uses as ability_label,
            row_number() over (
                partition by match_id, teamfight_id, team_number
                order by uses desc
            ) as rn
        from ability_uses
    ) t
    where rn <= 4
    group by match_id, teamfight_id, team_number
)
select
    ta.match_id,
    ta.teamfight_id,
    ta.team_number,
    case when ta.team_number = '0' then 'Radiant' else 'Dire' end as side,
    round(ta.start_time / 60.0, 2) as start_min,
    ta.gold_delta,
    ta.xp_delta,
    ta.deaths,
    ti.items_used,
    tab.abilities_used,
    fm.radiant_win
from team_agg ta
left join top_items ti
    on ti.match_id = ta.match_id
   and ti.teamfight_id = ta.teamfight_id
   and ti.team_number = ta.team_number
left join top_abilities tab
    on tab.match_id = ta.match_id
   and tab.teamfight_id = ta.teamfight_id
   and tab.team_number = ta.team_number
left join {{ ref('fact_matches') }} fm
    on fm.match_id = ta.match_id
