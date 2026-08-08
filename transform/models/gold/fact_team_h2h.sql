{{ config(
    materialized='table',
    post_hook=[
        "create index if not exists {{ this.schema }}_fact_th2h_match_idx on {{ this }}(match_id)",
        "create index if not exists {{ this.schema }}_fact_th2h_a_idx on {{ this }}(team_a_id)",
        "create index if not exists {{ this.schema }}_fact_th2h_b_idx on {{ this }}(team_b_id)"
    ]
) }}

-- Team head-to-head fact: one row per match where both teams are known,
-- with the team pair stored in canonical order (team_a_id < team_b_id) so each
-- pair appears exactly once. team_a_win is whether team A's side won.
-- Same DirectQuery rationale as fact_hero_matchups: two team dimensions on one
-- row cannot be live in DirectQuery, so it is precomputed.
select
    match_id,
    least(radiant_team_id, dire_team_id) as team_a_id,
    greatest(radiant_team_id, dire_team_id) as team_b_id,
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
where has_radiant_team and has_dire_team
  and radiant_win is not null
