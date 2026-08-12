{{ config(
    materialized='incremental',
    unique_key=['match_id', 'player_slot', 'source_key'],
    post_hook=[
        "create index if not exists {{ this.schema }}_stg_mpdt_match_idx on {{ this }}(match_id)",
        "create index if not exists {{ this.schema }}_stg_mpdt_player_idx on {{ this }}(player_slot)"
    ]
) }}

-- One row per (match, player, damage source): the raw damage this hero received
-- from each unit, flattened from the raw per-player `damage_taken` object
-- (key = source npc unit name, value = raw damage before mitigation). Sources
-- include heroes, buildings, creeps and neutrals. Incremental on match_id.
select
    m.payload->>'match_id'             as match_id,
    p.value->>'player_slot'            as player_slot,
    nullif(p.value->>'account_id', '') as account_id,
    nullif(p.value->>'hero_id', '')    as hero_id,
    case when (p.value->>'player_slot')::int < 128 then 'Radiant' else 'Dire' end as side,
    kv.key                             as source_key,
    kv.value::int                      as damage_amount
from {{ source('bronze', 'matches') }} m
cross join lateral jsonb_array_elements(m.payload->'players') as p
cross join lateral jsonb_each_text(p.value->'damage_taken') as kv
where jsonb_typeof(p.value->'damage_taken') = 'object'
  and (kv.value)::int > 0
{% if is_incremental() %}
  and m.payload->>'match_id' is not null
  and m.payload->>'match_id' not in (select match_id from {{ this }})
{% endif %}
