{{ config(materialized='view') }}

select
    leagueid::text,
    payload->>'name'   as league_name,
    payload->>'tier'   as tier,
    payload->>'ticket' as ticket,
    payload->>'banner' as banner
from {{ source('bronze', 'leagues') }}
