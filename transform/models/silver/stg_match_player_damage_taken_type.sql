{{ config(
    materialized='incremental',
    unique_key=['match_id', 'player_slot', 'inflictor_key']
) }}

-- One row per (match, player, damage inflictor): raw damage received from each
-- source, flattened from the raw per-player `damage_inflictor_received` object
-- (key = ability/item name or 'null' for auto-attacks, value = raw damage).
-- Each inflictor is classified to a damage type:
--   'null'                       -> Physical (auto-attack / basic damage)
--   ability key with dmg_type    -> that ability's dmg_type (Physical/Magical/Pure)
--   item key with dmg_type       -> that item's dmg_type
--   anything else                -> 'Other'
-- Incremental on match_id.
select
    m.payload->>'match_id'             as match_id,
    p.value->>'player_slot'            as player_slot,
    nullif(p.value->>'account_id', '') as account_id,
    nullif(p.value->>'hero_id', '')    as hero_id,
    case when (p.value->>'player_slot')::int < 128 then 'Radiant' else 'Dire' end as side,
    kv.key                             as inflictor_key,
    case
        when kv.key = 'null' then 'Physical'
        when a.dmg_type in ('Physical', 'Magical', 'Pure') then a.dmg_type
        when i.dmg_type in ('Physical', 'Magical', 'Pure') then i.dmg_type
        else 'Other'
    end as damage_type,
    kv.value::int                      as damage_amount
from {{ source('bronze', 'matches') }} m
cross join lateral jsonb_array_elements(m.payload->'players') as p
cross join lateral jsonb_each_text(p.value->'damage_inflictor_received') as kv
left join (
    select kv2.key as k, kv2.value->>'dmg_type' as dmg_type
    from {{ source('bronze', 'constants') }} c
    cross join lateral jsonb_each(c.payload) as kv2
    where c.resource = 'abilities'
) a on a.k = kv.key
left join (
    select kv2.key as k, kv2.value->>'dmg_type' as dmg_type
    from {{ source('bronze', 'constants') }} c
    cross join lateral jsonb_each(c.payload) as kv2
    where c.resource = 'items'
) i on i.k = kv.key
where jsonb_typeof(p.value->'damage_inflictor_received') = 'object'
  and (kv.value)::int > 0
{% if is_incremental() %}
  and m.payload->>'match_id' is not null
  and m.payload->>'match_id' not in (select match_id from {{ this }})
{% endif %}
