{{ config(
    materialized='incremental',
    unique_key=['match_id', 'player_slot', 'kill_index']
) }}

-- One row per (match, player, kill): the hero's kill timeline, flattened from
-- the raw per-player kills_log array (each entry is one kill with
-- key = victim npc hero name, time = seconds). Victim names are decoded to
-- hero ids in gold via dim_hero.hero_name. Incremental on match_id so the
-- expensive jsonb unnest only runs for newly loaded matches.
select
    m.payload->>'match_id'             as match_id,
    p.value->>'player_slot'            as player_slot,
    nullif(p.value->>'account_id', '') as account_id,
    nullif(p.value->>'hero_id', '')    as hero_id,
    case when (p.value->>'player_slot')::int < 128 then 'Radiant' else 'Dire' end as side,
    kl.ord - 1                         as kill_index,
    kl.elem->>'key'                    as victim_hero_name,
    (kl.elem->>'time')::int            as time_sec,
    greatest(floor((kl.elem->>'time')::numeric / 60), 0)::int as minute
from {{ source('bronze', 'matches') }} m
cross join lateral jsonb_array_elements(m.payload->'players') as p
cross join lateral jsonb_array_elements(p.value->'kills_log') with ordinality as kl(elem, ord)
where jsonb_typeof(p.value->'kills_log') = 'array'
  and (kl.elem->>'key') is not null
  and (kl.elem->>'time') is not null
{% if is_incremental() %}
  and m.payload->>'match_id' is not null
  and m.payload->>'match_id' not in (select match_id from {{ this }})
{% endif %}
