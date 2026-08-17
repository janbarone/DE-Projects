{{ config(
    materialized='table',
    post_hook=[
        "drop index if exists {{ this.schema }}.{{ this.schema }}_fact_matches_match_idx",
        "create index {{ this.schema }}_fact_matches_match_idx on {{ this }}(match_id)",
        "drop index if exists {{ this.schema }}.{{ this.schema }}_fact_matches_league_idx",
        "create index {{ this.schema }}_fact_matches_league_idx on {{ this }}(leagueid)",
        "drop index if exists {{ this.schema }}.{{ this.schema }}_fact_matches_patch_idx",
        "create index {{ this.schema }}_fact_matches_patch_idx on {{ this }}(patch)",
        "drop index if exists {{ this.schema }}.{{ this.schema }}_fact_matches_start_date_idx",
        "create index {{ this.schema }}_fact_matches_start_date_idx on {{ this }}(start_date)",
        "drop index if exists {{ this.schema }}.{{ this.schema }}_fact_matches_gm_idx",
        "create index {{ this.schema }}_fact_matches_gm_idx on {{ this }}(game_mode_id)",
        "drop index if exists {{ this.schema }}.{{ this.schema }}_fact_matches_lobby_idx",
        "create index {{ this.schema }}_fact_matches_lobby_idx on {{ this }}(lobby_type_id)",
        "drop index if exists {{ this.schema }}.{{ this.schema }}_fact_matches_region_idx",
        "create index {{ this.schema }}_fact_matches_region_idx on {{ this }}(region_id)",
        "drop index if exists {{ this.schema }}.{{ this.schema }}_fact_matches_radiant_idx",
        "create index {{ this.schema }}_fact_matches_radiant_idx on {{ this }}(radiant_team_id)",
        "drop index if exists {{ this.schema }}.{{ this.schema }}_fact_matches_dire_idx",
        "create index {{ this.schema }}_fact_matches_dire_idx on {{ this }}(dire_team_id)"
    ]) }}

-- One row per match, the hub fact. Game mode / lobby / region / team / league
-- keys are exposed as foreign keys to the gold dimensions.
select
    match_id,
    radiant_win,
    winner,
    duration_sec,
    round(duration_sec / 60.0, 2) as duration_min,
    round(duration_sec / 3600.0, 3) as duration_hour,
    game_mode        as game_mode_id,
    lobby_type       as lobby_type_id,
    region           as region_id,
    patch,
    start_time,
    start_time::date as start_date,
    radiant_score,
    dire_score,
    case
        when abs(radiant_score - dire_score) < 5 then 'close'
        when abs(radiant_score - dire_score) < 10 then 'moderate'
        when abs(radiant_score - dire_score) < 20 then 'blowout'
        else 'rout'
    end as score_bucket,
    radiant_team_id,
    dire_team_id,
    has_radiant_team,
    has_dire_team,
    leagueid,
    first_blood_time,
    human_players,
    pre_game_duration,
    loaded_at
from {{ ref('stg_matches') }}
