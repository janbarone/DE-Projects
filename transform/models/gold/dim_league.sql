{{ config(materialized='table') }}

-- League dimension (staging passthrough, conformed grain).
-- league_name normalized to uppercase for display consistency.
select
    leagueid,
    upper(league_name) as league_name,
    tier,
    ticket,
    banner
from {{ ref('stg_leagues') }}
