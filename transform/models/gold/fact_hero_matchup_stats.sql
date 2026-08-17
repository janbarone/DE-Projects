{{ config(
    materialized='table',
    post_hook=[
        "drop index if exists {{ this.schema }}.{{ this.schema }}_fact_hms_label_idx",
        "create index {{ this.schema }}_fact_hms_label_idx on {{ this }}(matchup_label)"
    ]) }}

-- Per-matchup aggregate: games, radiant/dire wins and win rates, precomputed
-- for DirectQuery. The live COUNTROWS/CALCULATE win-rate measures over
-- fact_hero_matchups grouped by the text matchup_label do not fold to the data
-- source; precomputing gives plain numeric columns that fold cleanly.
select
    matchup_label,
    count(*)::int                                    as matchup_games,
    count(*) filter (where radiant_win)::int         as radiant_wins,
    count(*) filter (where not radiant_win)::int     as dire_wins,
    round(count(*) filter (where radiant_win)::numeric / nullif(count(*), 0), 4) as radiant_win_rate,
    round(count(*) filter (where not radiant_win)::numeric / nullif(count(*), 0), 4) as dire_win_rate
from {{ ref('fact_hero_matchups') }}
group by matchup_label
order by matchup_games desc
