{{ config(
    materialized='incremental',
    unique_key=['match_id', 'order_no'],
    post_hook=[
        "create index if not exists {{ this.schema }}_stg_picks_bans_hero_idx on {{ this }}(hero_id)",
        "create index if not exists {{ this.schema }}_stg_picks_bans_match_idx on {{ this }}(match_id)"
    ]
) }}

-- One row per (match, draft order): the picks_bans[] array flattened.
-- `team` (0 = Radiant, 1 = Dire) is the side making the pick/ban.
select
    m.payload->>'match_id' as match_id,
    pb.value->>'order' as order_no,
    nullif(pb.value->>'order', '')::int as order_no_int,
    nullif(pb.value->>'hero_id', '') as hero_id,
    (pb.value->>'is_pick')::boolean as is_pick,
    nullif(pb.value->>'team', '') as team_number,
    case when pb.value->>'team' = '0' then 'Radiant' when pb.value->>'team' = '1' then 'Dire' else null end as active_team,
    nullif(pb.value->>'player_slot', '') as player_slot,
    coalesce((m.payload->>'timestamp_fetched')::timestamptz, m.loaded_at) as loaded_at
from {{ source('bronze', 'matches') }} m,
     lateral jsonb_array_elements(coalesce(nullif(m.payload->'picks_bans', 'null'::jsonb), '[]'::jsonb)) as pb
{% if is_incremental() %}
where m.payload->>'match_id' is not null
  and m.payload->>'match_id' not in (select match_id from {{ this }})
{% endif %}
