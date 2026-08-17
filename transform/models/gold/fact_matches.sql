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
-- radiant_team_name / dire_team_name and radiant_heroes / dire_heroes are
-- precomputed strings (materialized) so the Match Details table renders
-- correct per-row values in DirectQuery without cross-table measure context.
select
    sm.match_id,
    sm.radiant_win,
    sm.winner,
    sm.duration_sec,
    round(sm.duration_sec / 60.0, 2) as duration_min,
    round(sm.duration_sec / 3600.0, 3) as duration_hour,
    sm.game_mode        as game_mode_id,
    sm.lobby_type       as lobby_type_id,
    sm.region           as region_id,
    sm.patch,
    sm.start_time,
    sm.start_time::date as start_date,
    sm.radiant_score,
    sm.dire_score,
    case
        when abs(sm.radiant_score - sm.dire_score) < 5 then 'close'
        when abs(sm.radiant_score - sm.dire_score) < 10 then 'moderate'
        when abs(sm.radiant_score - sm.dire_score) < 20 then 'blowout'
        else 'rout'
    end as score_bucket,
    sm.radiant_team_id,
    sm.dire_team_id,
    sm.has_radiant_team,
    sm.has_dire_team,
    sm.leagueid,
    sm.first_blood_time,
    sm.human_players,
    sm.pre_game_duration,
    sm.loaded_at,
    case sm.winner
        when 'radiant' then 'Radiant'
        when 'dire' then 'Dire'
        else 'Draw'
    end as winner_name,
    (
        select t.team_name
        from {{ ref('fact_team_matches') }} ftm
        join {{ ref('dim_team') }} t on t.team_id = ftm.team_id
        where ftm.match_id = sm.match_id
          and ftm.side = 'Radiant'
    ) as radiant_team_name,
    (
        select t.team_name
        from {{ ref('fact_team_matches') }} ftm
        join {{ ref('dim_team') }} t on t.team_id = ftm.team_id
        where ftm.match_id = sm.match_id
          and ftm.side = 'Dire'
    ) as dire_team_name,
    (
        select t.logo_url
        from {{ ref('fact_team_matches') }} ftm
        join {{ ref('dim_team') }} t on t.team_id = ftm.team_id
        where ftm.match_id = sm.match_id
          and ftm.side = 'Radiant'
    ) as radiant_team_logo,
    (
        select t.logo_url
        from {{ ref('fact_team_matches') }} ftm
        join {{ ref('dim_team') }} t on t.team_id = ftm.team_id
        where ftm.match_id = sm.match_id
          and ftm.side = 'Dire'
    ) as dire_team_logo,
    (
        select string_agg(coalesce(h.localized_name, 'Unknown'), ', ' order by mp.player_slot::int)
        from {{ ref('stg_match_players') }} mp
        join {{ ref('stg_heroes') }} h on h.hero_id = mp.hero_id
        where mp.match_id = sm.match_id
          and mp.team_number = '0'
    ) as radiant_heroes,
    (
        select string_agg(coalesce(h.localized_name, 'Unknown'), ', ' order by mp.player_slot::int)
        from {{ ref('stg_match_players') }} mp
        join {{ ref('stg_heroes') }} h on h.hero_id = mp.hero_id
        where mp.match_id = sm.match_id
          and mp.team_number = '1'
    ) as dire_heroes
from {{ ref('stg_matches') }} sm
