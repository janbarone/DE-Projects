{{ config(materialized='table') }}

-- Decode lookup: region id -> name, flattened from the 'region' constants
-- resource (a jsonb object keyed by region id, values are plain strings).
select
    kv.key as region_id,
    kv.value #>> '{}' as region_name
from {{ ref('stg_constants') }} c,
     lateral jsonb_each(c.resource_payload) as kv
where c.resource = 'region'
