{{ config(
    materialized='table',
    post_hook=[
        "create index if not exists {{ this.schema }}_fact_hmh_match_idx on {{ this }}(match_id)",
        "create index if not exists {{ this.schema }}_fact_hmh_hero_idx on {{ this }}(hero_id)",
        "create index if not exists {{ this.schema }}_fact_hmh_opp_idx on {{ this }}(opponent_id)"
    ]
) }}

-- Hero-centric matchup fact: one row per (match, hero, opponent) = 50 rows per
-- match (each of the 25 radiant/dire pairings emitted once per perspective).
-- Unlike fact_hero_matchups (which is radiant-side-anchored), this fact lets a
-- single active dim_hero relationship filter a hero's games on BOTH sides, so
-- a hero slicer shows the hero's true win rate against every opponent.
-- hero_win = the focal hero's team won (radiant side: radiant_win; dire side:
-- NOT radiant_win). hero_id = 0 is excluded (inherited from fact_hero_matchups).
-- Self-matchups (same hero on both teams in mirror/all-random modes) are
-- excluded as noise - a hero can't be its own counter.
with radiant_perspective as (
    select
        m.match_id,
        m.radiant_hero_id as hero_id,
        m.dire_hero_id as opponent_id,
        hh.hero_localized_name || ' vs ' || oh.hero_localized_name as matchup_label,
        m.radiant_win as hero_win
    from {{ ref('fact_hero_matchups') }} m
    join {{ ref('dim_hero') }} hh on hh.hero_id = m.radiant_hero_id
    join {{ ref('dim_hero') }} oh on oh.hero_id = m.dire_hero_id
),

dire_perspective as (
    select
        m.match_id,
        m.dire_hero_id as hero_id,
        m.radiant_hero_id as opponent_id,
        hh.hero_localized_name || ' vs ' || oh.hero_localized_name as matchup_label,
        not m.radiant_win as hero_win
    from {{ ref('fact_hero_matchups') }} m
    join {{ ref('dim_hero') }} hh on hh.hero_id = m.dire_hero_id
    join {{ ref('dim_hero') }} oh on oh.hero_id = m.radiant_hero_id
)

select *
from (
    select * from radiant_perspective
    union all
    select * from dire_perspective
) all_matchups
where hero_id <> opponent_id
