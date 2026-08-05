{{ config(materialized='view') }}

select
    account_id::text,
    payload->>'name'     as player_name,
    nullif(payload->>'rank_tier', '') as rank_tier,
    nullif(payload->>'team_id', '')   as team_id
from {{ source('bronze', 'players') }}
