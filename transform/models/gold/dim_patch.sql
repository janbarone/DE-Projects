{{ config(materialized='table') }}

-- Patch dimension.
-- The match `patch` field is OpenDota's internal numeric patch id, not the
-- human-readable game version. This table decodes ids -> names/dates using the
-- 'patch' constants resource (id/date/name array) and keeps the numeric id as
-- sort_order (ids are chronological), plus an 'Unknown' row for any patch id
-- seen in matches but missing from constants.
with patch_constants as (
    select
        e.id::text                as patch_id,
        e.name                    as patch_name,
        (e.date::timestamptz)::date as patch_date
    from {{ ref('stg_constants') }} c,
         lateral jsonb_to_recordset(c.resource_payload) as e(id int, name text, date text)
    where c.resource = 'patch'
),

match_patches as (
    select distinct patch as patch_id
    from {{ ref('stg_matches') }}
    where patch is not null and patch <> ''
),

all_patches as (
    select
        p.patch_id,
        pc.patch_name,
        pc.patch_date,
        p.patch_id::int as sort_order
    from match_patches p
    left join patch_constants pc on p.patch_id = pc.patch_id

    union all

    -- Constant patches that never appear in our matches (kept so the
    -- dimension is complete and filterable, harmless).
    select
        pc.patch_id,
        pc.patch_name,
        pc.patch_date,
        pc.patch_id::int as sort_order
    from patch_constants pc
    where not exists (select 1 from match_patches p where p.patch_id = pc.patch_id)
)

select
    patch_id,
    coalesce(patch_name, 'Unknown') as patch_name,
    patch_date,
    coalesce(sort_order, 0) as sort_order
from all_patches
