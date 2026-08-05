{{ config(materialized='table') }}

-- Conformed hero dimension.
-- Merges stg_heroes (identity) with stg_hero_stats (aggregates) into a single
-- self-contained dimension, and appends an 'Unknown' hero (hero_id = 0) so that
-- every hero_id appearing in the fact tables (including OpenDota's hero_id = 0
-- placeholder) resolves cleanly in Power BI.
select
    h.hero_id,
    coalesce(h.hero_name, 'unknown')       as hero_name,
    coalesce(h.localized_name, 'Unknown')  as hero_localized_name,
    h.primary_attr,
    h.attack_type,
    h.roles,
    h.img,
    s.pro_pick,
    s.pro_win,
    s.pro_ban,
    s.pub_pick,
    s.pub_win,
    s.pub_win_rate
from {{ ref('stg_heroes') }} h
left join {{ ref('stg_hero_stats') }} s on h.hero_id = s.hero_id

union all

-- Unknown hero placeholder (OpenDota uses hero_id = 0 for missing heroes).
select
    '0',
    'unknown',
    'Unknown',
    null,
    null,
    null,
    null,
    null, null, null, null, null, null
