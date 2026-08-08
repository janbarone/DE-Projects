{{ config(materialized='table') }}

-- Decode lookup: OpenDota item id -> display name, flattened from the
-- 'item_ids' resource (id -> internal name) joined to the 'items'
-- resource (internal name -> dname). Unmatched ids (recipes,
-- ability_base) fall back to the internal name.
with item_ids as (
    select
        kv.key            as item_id,
        kv.value->>0      as item_internal_name
    from {{ ref('stg_constants') }} c,
         lateral jsonb_each(c.resource_payload) as kv
    where c.resource = 'item_ids'
),
items as (
    select
        kv.key                as item_internal_name,
        (kv.value->>'dname')  as item_name
    from {{ ref('stg_constants') }} c,
         lateral jsonb_each(c.resource_payload) as kv
    where c.resource = 'items'
      and kv.value->>'dname' is not null
)
select
    ii.item_id            as item_id,
    ii.item_internal_name as item_internal_name,
    coalesce(i.item_name, ii.item_internal_name) as item_name
from item_ids ii
left join items i on i.item_internal_name = ii.item_internal_name
