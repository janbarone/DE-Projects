{{ config(materialized='table') }}

-- Decode lookup: game_mode id -> label, flattened from the 'game_mode'
-- constants resource (a jsonb object keyed by game mode id).
-- game_mode_name normalized: strip the 'game_mode_' prefix and uppercase
-- (e.g. game_mode_captains_mode -> 'CAPTAINS MODE').
select
    kv.key                    as game_mode_id,
    upper(replace(kv.value->>'name', 'game_mode_', '')) as game_mode_name,
    (kv.value->>'balanced')::boolean as is_balanced
from {{ ref('stg_constants') }} c,
     lateral jsonb_each(c.resource_payload) as kv
where c.resource = 'game_mode'
