{{ config(materialized='view') }}

select
    team_id::text,
    payload->>'name'     as team_name,
    payload->>'tag'      as team_tag,
    nullif(payload->>'rating', '')::numeric as rating,
    nullif(payload->>'wins', '')::int       as wins,
    nullif(payload->>'losses', '')::int     as losses,
    payload->>'logo_url' as logo_url
from {{ source('bronze', 'teams') }}
