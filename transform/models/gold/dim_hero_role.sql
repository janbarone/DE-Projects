{{ config(materialized='table') }}

-- Bridge table: one row per (hero, role). Lets Power BI filter heroes by role
-- with a clean many-to-one relationship (dim_hero 1 -> many dim_hero_role).
-- dim_hero.roles (jsonb stored as text) is kept for raw detail; use this
-- table for filtering.
select
    h.hero_id,
    jt.role
from {{ ref('dim_hero') }} h,
     jsonb_array_elements_text(h.roles::jsonb) as jt(role)
where h.hero_id != '0'  -- the Unknown hero has no roles
