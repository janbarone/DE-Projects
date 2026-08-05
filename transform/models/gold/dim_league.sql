{{ config(materialized='table') }}

-- League dimension (staging passthrough, conformed grain).
select
    leagueid,
    league_name,
    tier,
    ticket,
    banner
from {{ ref('stg_leagues') }}
