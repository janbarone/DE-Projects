{{ config(
    materialized='incremental',
    unique_key=['match_id', 'player_slot', 'target_key']
) }}

-- One row per (match, player, damage target): the hero's total damage dealt to
-- each unit, flattened from the raw per-player `damage` object (key = target
-- npc unit name, value = total damage). Targets include heroes
-- (npc_dota_hero_*), buildings (npc_dota_*tower*, *rax*, ancient), creeps,
-- neutrals and wards. Incremental on match_id.
select
    m.payload->>'match_id'             as match_id,
    p.value->>'player_slot'            as player_slot,
    nullif(p.value->>'account_id', '') as account_id,
    nullif(p.value->>'hero_id', '')    as hero_id,
    case when (p.value->>'player_slot')::int < 128 then 'Radiant' else 'Dire' end as side,
    kv.key                             as target_key,
    kv.value::int                      as damage_amount
from {{ source('bronze', 'matches') }} m
cross join lateral jsonb_array_elements(m.payload->'players') as p
cross join lateral jsonb_each_text(p.value->'damage') as kv
where jsonb_typeof(p.value->'damage') = 'object'
  and (kv.value)::int > 0
{% if is_incremental() %}
  and m.payload->>'match_id' is not null
  and m.payload->>'match_id' not in (select match_id from {{ this }})
{% endif %}
