{{ config(
    materialized='table',
    post_hook=[
        "create index if not exists {{ this.schema }}_fact_tf_match_idx on {{ this }}(match_id)"
    ]
) }}

-- One row per (match, teamfight): teamfight fact.
-- Links to fact_matches via match_id. The raw players array is preserved as
-- text (jsonb-cast-to-text in silver); OpenDota teamfight player entries carry
-- no hero/account id, so no hero relationship exists (documented in
-- docs/data_model.md). Text (not jsonb) keeps DirectQuery folding working in
-- Power BI (see docs/power_bi_setup.md section 8).
select
    match_id,
    teamfight_id,
    start_time,
    end_time,
    last_death,
    round(start_time / 60.0, 2)   as start_min,
    round(end_time / 60.0, 2)     as end_min,
    round(last_death / 60.0, 2)   as last_death_min,
    case
        when start_time < 0 then 'pre-game'
        when start_time / 60.0 < 20 then 'early (0-20m)'
        when start_time / 60.0 < 40 then 'mid (20-40m)'
        else 'late (40m+)'
    end as fight_phase,
    deaths,
    duration_sec,
    round(duration_sec / 60.0, 2) as duration_min,
    players,
    loaded_at
from {{ ref('stg_teamfights') }}
