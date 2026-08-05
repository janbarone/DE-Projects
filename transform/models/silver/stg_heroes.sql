{{ config(materialized='view') }}

-- One row per hero from the 'heroes' constants resource.
-- payload is a jsonb object keyed by hero id -> hero record.
select
    kv.key                   as hero_id,
    kv.value->>'name'           as hero_name,
    kv.value->>'localized_name' as localized_name,
    kv.value->>'primary_attr'   as primary_attr,
    kv.value->>'attack_type'    as attack_type,
    kv.value->>'roles'          as roles,
    kv.value->>'img'            as img
from {{ source('bronze', 'constants') }},
     lateral jsonb_each(payload) as kv
where resource = 'heroes'
