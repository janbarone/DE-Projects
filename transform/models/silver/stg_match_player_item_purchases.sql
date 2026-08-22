{{ config(
    materialized='incremental',
    unique_key=['match_id', 'player_slot', 'purchase_index']
) }}

-- One row per (match, player, item purchase): the hero's itemization over
-- time, flattened from the raw per-player purchase_log array (each entry is
-- one item purchase with key = item_internal_name and time = seconds; negative
-- times are pre-game starting items, clamped to minute 0). Incremental on
-- match_id so the expensive jsonb unnest only runs for newly loaded matches.
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
    m.payload->>'match_id'             as match_id,
    p.value->>'player_slot'            as player_slot,
    nullif(p.value->>'account_id', '') as account_id,
    nullif(p.value->>'hero_id', '')    as hero_id,
    case when (p.value->>'player_slot')::int < 128 then 'Radiant' else 'Dire' end as side,
    pl.ord - 1                         as purchase_index,
    pl.elem->>'key'                    as item_internal_name,
    (pl.elem->>'time')::int            as time_sec,
    greatest(floor((pl.elem->>'time')::numeric / 60), 0)::int as minute
from new_matches m
cross join lateral jsonb_array_elements(m.payload->'players') as p
cross join lateral jsonb_array_elements(p.value->'purchase_log') with ordinality as pl(elem, ord)
where jsonb_typeof(p.value->'purchase_log') = 'array'
  and (pl.elem->>'key') is not null
  and (pl.elem->>'time') is not null
