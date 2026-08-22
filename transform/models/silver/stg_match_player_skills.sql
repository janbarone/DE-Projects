{{ config(
    materialized='incremental',
    unique_key=['match_id', 'player_slot', 'upgrade_index']
) }}

-- One row per (match, player, ability upgrade): the hero's skill learning
-- order, flattened from the raw ability_upgrades_arr array (element index ==
-- learning order; ids are numeric strings, decoded in gold via constants).
-- Incremental on match_id so the expensive jsonb unnest only runs for newly
-- loaded matches.
{% if is_incremental() %}
with new_matches as (
    select payload, loaded_at
    from {{ source('bronze', 'matches') }}
    where payload->>'match_id' is not null
      and payload->>'match_id' not in (select match_id from {{ this }})
)
{% else %}
with new_matches as (
    select payload, loaded_at
    from {{ source('bronze', 'matches') }}
)
{% endif %}
select
    m.payload->>'match_id'        as match_id,
    p.value->>'player_slot'       as player_slot,
    nullif(p.value->>'account_id', '') as account_id,
    nullif(p.value->>'hero_id', '') as hero_id,
    case when (p.value->>'player_slot')::int < 128 then 'Radiant' else 'Dire' end as side,
    u.ord - 1                     as upgrade_index,
    u.elem #>> '{}'               as ability_id
from new_matches m
cross join lateral jsonb_array_elements(m.payload->'players') as p
cross join lateral jsonb_array_elements(p.value->'ability_upgrades_arr') with ordinality as u(elem, ord)
where jsonb_typeof(p.value->'ability_upgrades_arr') = 'array'
