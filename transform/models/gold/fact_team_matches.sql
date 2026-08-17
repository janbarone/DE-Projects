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
