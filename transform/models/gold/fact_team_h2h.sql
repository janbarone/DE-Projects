{{ config(
    materialized='table',
    post_hook=[
        "drop index if exists {{ this.schema }}.{{ this.schema }}_fact_th2h_match_idx",
        "create index {{ this.schema }}_fact_th2h_match_idx on {{ this }}(match_id)",
        "drop index if exists {{ this.schema }}.{{ this.schema }}_fact_th2h_a_idx",
        "create index {{ this.schema }}_fact_th2h_a_idx on {{ this }}(team_a_id)",
        "drop index if exists {{ this.schema }}.{{ this.schema }}_fact_th2h_b_idx",
        "create index {{ this.schema }}_fact_th2h_b_idx on {{ this }}(team_b_id)"
    ]) }}

-- Team head-to-head fact: one row per match where both teams are known,
-- with the team pair stored in canonical order (team_a_id < team_b_id) so each
-- pair appears exactly once. team_a_win is whether team A's side won.
-- Same DirectQuery rationale as fact_hero_matchups: two team dimensions on one
-- row cannot be live in DirectQuery, so it is precomputed. team_a_name /
-- team_b_name are denormalized because only team_a_id has an active link to
-- dim_team in the Power BI model (the team_b_id link is inactive).
select
    match_id,
    least(radiant_team_id, dire_team_id) as team_a_id,
    greatest(radiant_team_id, dire_team_id) as team_b_id,
    t_a.team_name as team_a_name,
    t_b.team_name as team_b_name,
    case
        when radiant_team_id < dire_team_id then radiant_win
        else not radiant_win
    end as team_a_win,
    case
        when radiant_team_id < dire_team_id then radiant_score
        else dire_score
    end as team_a_score,
    case
        when radiant_team_id < dire_team_id then dire_score
        else radiant_score
    end as team_b_score
from {{ ref('fact_matches') }}
left join {{ ref('dim_team') }} t_a on t_a.team_id = least(radiant_team_id, dire_team_id)
left join {{ ref('dim_team') }} t_b on t_b.team_id = greatest(radiant_team_id, dire_team_id)
where has_radiant_team and has_dire_team
  and radiant_win is not null
