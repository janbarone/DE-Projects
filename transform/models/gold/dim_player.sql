{{ config(materialized='table') }}

-- Conformed player dimension covering every account_id present in the facts.
-- Pro players carry metadata; non-pro match participants resolve to an
-- 'Unknown' row (name unavailable) so the Power BI relationship from
-- fact_match_players never fails validation.
select
    account_id,
    player_name,
    rank_tier,
    team_id,
    'pro' as player_type
from {{ ref('stg_players') }}

union all

select distinct
    mp.account_id,
    null::text as player_name,
    null::text as rank_tier,
    null::text as team_id,
    'match_participant' as player_type
from {{ ref('stg_match_players') }} mp
where mp.account_id not in (select account_id from {{ ref('stg_players') }})
