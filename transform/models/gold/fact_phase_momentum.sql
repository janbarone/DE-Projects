{{ config(
    materialized='table',
    post_hook=[
        "create index if not exists {{ this.schema }}_fact_phase_m_match_idx on {{ this }}(match_id)",
        "create index if not exists {{ this.schema }}_fact_phase_m_team_idx on {{ this }}(team_number)",
        "create index if not exists {{ this.schema }}_fact_phase_m_phase_idx on {{ this }}(fight_phase)"
    ]
) }}

-- One row per (match, team, fight phase): the team's gold/XP swing and death
-- count inside the teamfights that happened during that phase, plus the final
-- team outcome. Supports both a per-match "momentum" view (how did each team's
-- economy swing early/mid/late) and aggregate analysis ("if a team wins the
-- gold in the early phase, how often does it win the game").
--
-- Pre-game fights (start_time < 0) and unknown outcomes (draws) are excluded.
-- Built from the raw teamfight players array so this model does NOT depend on
-- fact_match_players (avoids a circular ref when fact_match_players joins it).
with phase_fights as (
    select
        match_id,
        teamfight_id,
        fight_phase
    from {{ ref('fact_teamfights') }}
    where fight_phase <> 'pre-game'
),
player_phase as (
    select
        tf.match_id,
        tf.teamfight_id,
        pf.fight_phase,
        case when tp.ord <= 5 then '0' else '1' end as team_number,
        nullif(tp.p->>'gold_delta', '')::int as gold_delta,
        nullif(tp.p->>'xp_delta', '')::int   as xp_delta,
        nullif(tp.p->>'deaths', '')::int     as deaths
    from {{ ref('fact_teamfights') }} tf
    cross join lateral jsonb_array_elements(tf.players::jsonb) with ordinality as tp(p, ord)
    inner join phase_fights pf
        on pf.match_id = tf.match_id
       and pf.teamfight_id = tf.teamfight_id
),
phase_agg as (
    select
        match_id,
        team_number,
        fight_phase,
        sum(coalesce(gold_delta, 0)) as gold_delta,
        sum(coalesce(xp_delta, 0))   as xp_delta,
        sum(coalesce(deaths, 0))     as deaths,
        count(distinct teamfight_id) as fights
    from player_phase
    group by match_id, team_number, fight_phase
)
select
    pa.match_id,
    pa.team_number,
    case when pa.team_number = '0' then 'Radiant' else 'Dire' end as side,
    pa.fight_phase,
    case pa.fight_phase
        when 'early (0-20m)' then 0
        when 'mid (20-40m)' then 1
        else 2
    end as phase_ord,
    pa.gold_delta,
    pa.xp_delta,
    pa.deaths,
    pa.fights,
    fm.radiant_win,
    fm.duration_min,
    case
        when fm.radiant_win is null then null
        when pa.team_number = '0' then fm.radiant_win
        else not fm.radiant_win
    end as team_win
from phase_agg pa
left join {{ ref('fact_matches') }} fm
    on fm.match_id = pa.match_id
