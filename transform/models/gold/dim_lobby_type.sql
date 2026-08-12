{{ config(materialized='table') }}

-- Decode lookup: lobby_type id -> label, flattened from the 'lobby_type'
-- constants resource (a jsonb object keyed by lobby type id).
-- lobby_type_name normalized: strip the 'lobby_type_' prefix and uppercase
-- (e.g. lobby_type_battle_cup -> 'BATTLE CUP').
select
    kv.key                    as lobby_type_id,
    upper(replace(kv.value->>'name', 'lobby_type_', '')) as lobby_type_name,
    (kv.value->>'balanced')::boolean as is_balanced
from {{ ref('stg_constants') }} c,
     lateral jsonb_each(c.resource_payload) as kv
where c.resource = 'lobby_type'
