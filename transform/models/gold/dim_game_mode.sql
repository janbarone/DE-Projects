{{ config(materialized='table') }}

-- Decode lookup: game_mode id -> label, flattened from the 'game_mode'
-- constants resource (a jsonb object keyed by game mode id).
select
    kv.key                    as game_mode_id,
    kv.value->>'name'        as game_mode_name,
    (kv.value->>'balanced')::boolean as is_balanced
from {{ ref('stg_constants') }} c,
     lateral jsonb_each(c.resource_payload) as kv
where c.resource = 'game_mode'
