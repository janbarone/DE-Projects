{{ config(
    materialized='incremental',
    unique_key=['match_id', 'teamfight_id']
) }}

-- One row per (match, teamfight). The players array is kept as text (jsonb
-- cast to text) because OpenDota does not expose a hero/account id inside
-- teamfight player entries (only ability names, damage, xp/gold deltas) -
-- parsing it reliably is not possible without a hero key, so we preserve the
-- raw payload as text for later use. Text (not jsonb) keeps DirectQuery
-- folding working in Power BI (jsonb columns break query folding, see
-- docs/power_bi_setup.md section 8).
select
    m.payload->>'match_id' as match_id,
    tf.ordinality::text as teamfight_id,
    nullif(tf.value->>'start', '')::int as start_time,
    nullif(tf.value->>'end', '')::int as end_time,
    nullif(tf.value->>'last_death', '')::int as last_death,
    nullif(tf.value->>'deaths', '')::int as deaths,
    (tf.value->>'end')::int - (tf.value->>'start')::int as duration_sec,
    tf.value->>'players' as players,
    coalesce((m.payload->>'timestamp_fetched')::timestamptz, m.loaded_at) as loaded_at
from {{ source('bronze', 'matches') }} m,
     lateral jsonb_array_elements(coalesce(nullif(m.payload->'teamfights', 'null'::jsonb), '[]'::jsonb)) with ordinality as tf
{% if is_incremental() %}
where m.payload->>'match_id' is not null
  and m.payload->>'match_id' not in (select match_id from {{ this }})
{% endif %}
