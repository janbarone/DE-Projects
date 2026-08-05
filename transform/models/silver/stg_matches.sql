{{ config(
    materialized='incremental',
    unique_key='match_id',
    post_hook=[
        "create index if not exists {{ this.schema }}_stg_matches_league_idx on {{ this }}(leagueid)",
        "create index if not exists {{ this.schema }}_stg_matches_radiant_idx on {{ this }}(radiant_team_id)",
        "create index if not exists {{ this.schema }}_stg_matches_dire_idx on {{ this }}(dire_team_id)"
    ]
) }}

-- One row per match, flattened from the raw match jsonb.
select
    payload->>'match_id' as match_id,
    (payload->>'radiant_win')::boolean as radiant_win,
    case
        when (payload->>'radiant_win')::boolean is true then 'radiant'
        when (payload->>'radiant_win')::boolean is false then 'dire'
        else 'draw'
    end as winner,
    nullif(payload->>'duration', '')::int as duration_sec,
    nullif(payload->>'game_mode', '') as game_mode,
    nullif(payload->>'lobby_type', '') as lobby_type,
    nullif(payload->>'region', '') as region,
    nullif(payload->>'patch', '') as patch,
    to_timestamp(nullif(payload->>'start_time', '')::double precision) as start_time,
    nullif(payload->>'radiant_score', '')::int as radiant_score,
    nullif(payload->>'dire_score', '')::int as dire_score,
    nullif(payload->>'radiant_team_id', '') as radiant_team_id,
    nullif(payload->>'dire_team_id', '') as dire_team_id,
    (payload->>'radiant_team_id') is not null and nullif(payload->>'radiant_team_id', '') is not null as has_radiant_team,
    (payload->>'dire_team_id') is not null and nullif(payload->>'dire_team_id', '') is not null as has_dire_team,
    nullif(payload->>'leagueid', '') as leagueid,
    nullif(payload->>'first_blood_time', '')::int as first_blood_time,
    nullif(payload->>'human_players', '')::int as human_players,
    nullif(payload->>'pre_game_duration', '')::int as pre_game_duration,
    nullif(payload->>'replay_salt', '') as replay_salt,
    nullif(payload->>'version', '') as version,
    coalesce((payload->>'timestamp_fetched')::timestamptz, loaded_at) as loaded_at
from {{ source('bronze', 'matches') }}
{% if is_incremental() %}
where payload->>'match_id' is not null
  and payload->>'match_id' not in (select match_id from {{ this }})
{% endif %}
