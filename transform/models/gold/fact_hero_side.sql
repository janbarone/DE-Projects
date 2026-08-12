{{ config(
    materialized='table',
    post_hook=[
        "create index if not exists {{ this.schema }}_fact_hs_hero_idx on {{ this }}(hero_id)",
        "create index if not exists {{ this.schema }}_fact_hs_side_idx on {{ this }}(side)"
    ]
) }}

-- Hero win rate by side fact: one row per (hero, side) with picks, wins and
-- win rate. Precomputed for DirectQuery because grouping a COUNTROWS-based
-- measure by a cross-table column (dim_hero.hero_localized_name + side) does
-- not fold to the data source. Same rationale as fact_team_h2h / fact_hero_matchups.
select
    hero_id,
    side,
    count(*)::int                                 as hero_side_picks,
    count(*) filter (where team_win)::int         as hero_side_wins,
    round(count(*) filter (where team_win)::numeric / nullif(count(*), 0), 4) as hero_side_win_rate
from {{ ref('fact_match_players') }}
where side in ('Radiant', 'Dire')
group by hero_id, side
order by hero_id, side
