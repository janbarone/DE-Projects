{{ config(
    materialized='incremental',
    unique_key=['match_id', 'player_slot', 'rune_key'],
    post_hook=[
        "create index if not exists {{ this.schema }}_stg_mpr_match_idx on {{ this }}(match_id)",
        "create index if not exists {{ this.schema }}_stg_mpr_player_idx on {{ this }}(player_slot)"
    ]
) }}

-- One row per (match, player, rune type): total runes picked up, flattened
-- from the raw per-player `runes` object (key = rune type id, value = count).
-- The `runes` map is the authoritative source and is populated for nearly every
-- parsed player, whereas the `runes_log` timeline array is only present for a
-- subset of players/matches. Rune ids are decoded in gold via dim_rune.
-- Incremental on match_id so the expensive jsonb unnest only runs for newly
-- loaded matches.
select
    m.payload->>'match_id'             as match_id,
    p.value->>'player_slot'            as player_slot,
    nullif(p.value->>'account_id', '') as account_id,
    nullif(p.value->>'hero_id', '')    as hero_id,
    case when (p.value->>'player_slot')::int < 128 then 'Radiant' else 'Dire' end as side,
    kv.key::int                        as rune_key,
    kv.value::int                      as rune_count
from {{ source('bronze', 'matches') }} m
cross join lateral jsonb_array_elements(m.payload->'players') as p
cross join lateral jsonb_each_text(p.value->'runes') as kv
where jsonb_typeof(p.value->'runes') = 'object'
  and (kv.value)::int > 0
{% if is_incremental() %}
  and m.payload->>'match_id' is not null
  and m.payload->>'match_id' not in (select match_id from {{ this }})
{% endif %}
