{{ config(
    materialized='incremental',
    unique_key=['match_id', 'player_slot', 'minute']
) }}

-- One row per (match, player, minute): the player's per-minute progression
-- flattened from the raw payload arrays (times / gold_t / xp_t / lh_t / dn_t,
-- indexed by the same ordinality, one sample per minute). Incremental on
-- match_id so the expensive jsonb unnest only runs for newly loaded matches.
{% if is_incremental() %}
with new_matches as (
    select payload, loaded_at
    from {{ source('bronze', 'matches') }}
    where payload->>'match_id' is not null
      and payload->>'match_id' not in (select distinct match_id from {{ this }})
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
    s.elem::numeric as time_sec,
    floor(s.elem::numeric / 60)::int as minute,
    (p.value->'gold_t'->(s.ord - 1))::int   as gold,
    (p.value->'xp_t'->(s.ord - 1))::int     as xp,
    (p.value->'lh_t'->(s.ord - 1))::int     as last_hits,
    (p.value->'dn_t'->(s.ord - 1))::int     as denies
from new_matches m
cross join lateral jsonb_array_elements(m.payload->'players') as p
cross join lateral jsonb_array_elements(p.value->'times') with ordinality as s(elem, ord)
where p.value ? 'times'
  and p.value ? 'gold_t'
  and p.value ? 'xp_t'
  and p.value ? 'lh_t'
  and p.value ? 'dn_t'
  and jsonb_typeof(p.value->'times') = 'array'
  and jsonb_typeof(p.value->'gold_t') = 'array'
  and jsonb_typeof(p.value->'xp_t') = 'array'
  and jsonb_typeof(p.value->'lh_t') = 'array'
  and jsonb_typeof(p.value->'dn_t') = 'array'
