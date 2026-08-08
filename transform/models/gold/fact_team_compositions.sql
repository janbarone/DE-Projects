{{ config(
    materialized='table',
    post_hook=[
        "create index if not exists {{ this.schema }}_fact_tcomp_match_idx on {{ this }}(match_id)",
        "create index if not exists {{ this.schema }}_fact_tcomp_team_idx on {{ this }}(team_id)"
    ]
) }}

-- Team role-composition fact: one row per (match, team). Primary role = the
-- first role tag on each hero (roles[0] is the canonical primary role in the
-- OpenDota hero constants). role_label is the sorted multiset of the 5 primary
-- roles, so identical lineups group together (e.g. 'Carry,Carry,Initiator,
-- Support,Support'). support_count / carry_count / ... expose per-role counts
-- for drill-down. team_id is nullable (matches without a known team on that
-- side). Only full 5-hero teams are kept so partial/abandoned lineups don't
-- dilute composition win rates; hero_count is kept for verification.
with player_roles as (
    select
        mp.match_id,
        mp.team_number,
        mp.team_win,
        r.role as primary_role
    from {{ ref('fact_match_players') }} mp
    join {{ ref('dim_hero') }} h on h.hero_id = mp.hero_id
    cross join lateral jsonb_array_elements_text(h.roles::jsonb) with ordinality as r(role, ord)
    where h.hero_id <> '0'
      and r.ord = 1
),

team_agg as (
    select
        match_id,
        team_number,
        bool_or(team_win) as team_win,
        count(*) as hero_count,
        string_agg(primary_role, ',' order by primary_role) as role_label,
        count(*) filter (where primary_role = 'Carry') as carry_count,
        count(*) filter (where primary_role = 'Support') as support_count,
        count(*) filter (where primary_role = 'Nuker') as nuker_count,
        count(*) filter (where primary_role = 'Disabler') as disabler_count,
        count(*) filter (where primary_role = 'Durable') as durable_count,
        count(*) filter (where primary_role = 'Initiator') as initiator_count,
        count(*) filter (where primary_role = 'Escape') as escape_count,
        count(*) filter (where primary_role = 'Pusher') as pusher_count
    from player_roles
    group by match_id, team_number
)

select
    t.match_id,
    t.team_number,
    case when t.team_number = '0' then 'Radiant' else 'Dire' end as side,
    tm.team_id,
    t.team_win,
    t.hero_count,
    t.role_label,
    t.support_count,
    t.carry_count,
    t.nuker_count,
    t.disabler_count,
    t.durable_count,
    t.initiator_count,
    t.escape_count,
    t.pusher_count
from team_agg t
left join {{ ref('fact_team_matches') }} tm
    on tm.match_id = t.match_id
   and case when t.team_number = '0' then 'Radiant' else 'Dire' end = tm.side
where t.hero_count = 5
