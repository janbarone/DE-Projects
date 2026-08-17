{{ config(
    materialized='table',
    post_hook=[
        "drop index if exists {{ this.schema }}.{{ this.schema }}_fact_mtm_match_idx",
        "create index {{ this.schema }}_fact_mtm_match_idx on {{ this }}(match_id)"
    ]) }}

-- One row per (match, side, minute): team-level per-minute gold (net worth) and
-- XP, aggregated from fact_match_player_minute (itself flattened from the raw
-- gold_t / xp_t arrays). Sums all 5 players per side per minute.
select
    match_id,
    side,
    minute,
    sum(gold)::int as team_gold,
    sum(xp)::int   as team_xp,
    count(*)       as players_sampled
from {{ ref('fact_match_player_minute') }}
group by match_id, side, minute
order by match_id, side, minute
