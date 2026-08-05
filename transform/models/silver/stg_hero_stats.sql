{{ config(materialized='view') }}

-- One row per hero aggregate from /heroStats.
select
    id::text as hero_id,
    nullif(payload->>'pro_pick', '')::int as pro_pick,
    nullif(payload->>'pro_win',  '')::int as pro_win,
    nullif(payload->>'pro_ban',  '')::int as pro_ban,
    nullif(payload->>'pub_pick', '')::int as pub_pick,
    nullif(payload->>'pub_win',  '')::int as pub_win,
    case
        when nullif(payload->>'pub_pick', '')::int > 0
        then round(100.0 * nullif(payload->>'pub_win', '')::numeric
                        / nullif(payload->>'pub_pick', '')::numeric, 2)
        else null
    end as pub_win_rate
from {{ source('bronze', 'hero_stats') }}
