{{ config(materialized='table') }}

-- Decode lookup: lobby_type id -> label, flattened from the 'lobby_type'
-- constants resource (a jsonb object keyed by lobby type id).
select
    kv.key                    as lobby_type_id,
    kv.value->>'name'        as lobby_type_name,
    (kv.value->>'balanced')::boolean as is_balanced
from {{ ref('stg_constants') }} c,
     lateral jsonb_each(c.resource_payload) as kv
where c.resource = 'lobby_type'
