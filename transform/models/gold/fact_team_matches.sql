{{ config(
    materialized='table',
    post_hook=[
        "drop index if exists {{ this.schema }}.{{ this.schema }}_fact_team_matches_match_idx",
        "create index {{ this.schema }}_fact_team_matches_match_idx on {{ this }}(match_id)",
        "drop index if exists {{ this.schema }}.{{ this.schema }}_fact_team_matches_team_idx",
        "create index {{ this.schema }}_fact_team_matches_team_idx on {{ this }}(team_id)",
        "drop index if exists {{ this.schema }}.{{ this.schema }}_fact_team_matches_side_idx",
        "create index {{ this.schema }}_fact_team_matches_side_idx on {{ this }}(side)"
    ]) }}

-- Bridge fact: one row per (match, side) connecting dim_team through a single
-- path, so both the radiant and dire team are queryable at the same time.
-- This replaces the role-playing-dimension / inactive-relationship workaround
-- (Power BI cannot have two active links between fact_matches and dim_team).
-- league_rank is precomputed per league (wins desc, then win rate desc, then
-- team_id for determinism) so the Team Details leaderboard renders correct
-- ranks in DirectQuery without a RANKX measure (cross-table measure context
-- does not correlate reliably in DirectQuery).
with team_rows as (
    select
        match_id,
        'Radiant' as side,
        radiant_team_id as team_id,
        radiant_win,
        radiant_win as team_win,
        radiant_score as team_score,
        dire_score as opponent_score
    from {{ ref('stg_matches') }}
    where has_radiant_team

    union all

    select
        match_id,
        'Dire' as side,
        dire_team_id as team_id,
        radiant_win,
        not radiant_win as team_win,
        dire_score as team_score,
        radiant_score as opponent_score
    from {{ ref('stg_matches') }}
    where has_dire_team
),
league_team_stats as (
    select
        sm.leagueid,
        tr.team_id,
        count(*) as games,
        count(*) filter (where tr.team_win) as wins,
        round(count(*) filter (where tr.team_win)::numeric / nullif(count(*), 0), 4) as win_rate
    from team_rows tr
    join {{ ref('stg_matches') }} sm on sm.match_id = tr.match_id
    group by sm.leagueid, tr.team_id
),
league_ranks as (
    select
        leagueid,
        team_id,
        row_number() over (
            partition by leagueid
            order by wins desc, win_rate desc, team_id asc
        ) as league_rank
    from league_team_stats
)
select
    tr.match_id,
    tr.side,
    tr.team_id,
    tr.radiant_win,
    tr.team_win,
    tr.team_score,
    tr.opponent_score,
    lr.league_rank
from team_rows tr
left join {{ ref('stg_matches') }} sm on sm.match_id = tr.match_id
left join league_ranks lr on lr.leagueid = sm.leagueid and lr.team_id = tr.team_id
