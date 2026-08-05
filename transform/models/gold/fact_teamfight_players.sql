{{ config(materialized='table') }}

-- One row per (match, teamfight, player) at hero level.
-- OpenDota's teamfight players array always has exactly 10 entries, ordered by
-- player slot (indices 0-4 = radiant slots 0-4, indices 5-9 = dire slots
-- 128-132). We use that positional guarantee to recover player_slot and join
-- through fact_match_players to dim_hero. Nested per-ability maps are kept as
-- text (jsonb cast to text) for detail - jsonb columns break DirectQuery
-- folding in Power BI (see docs/power_bi_setup.md section 8).
select
    tf.match_id,
    tf.teamfight_id,
    tf.start_time     as teamfight_start,
    tf.end_time       as teamfight_end,
    -- positional mapping: array idx 1-5 -> slots 0-4, idx 6-10 -> slots 128-132
    (case when tfp.ord <= 5 then tfp.ord - 1 else tfp.ord + 122 end)::text as player_slot,
    mp.hero_id,
    mp.account_id,
    nullif(tfp.p->>'damage', '')::int   as damage,
    nullif(tfp.p->>'healing', '')::int  as healing,
    nullif(tfp.p->>'deaths', '')::int   as deaths,
    nullif(tfp.p->>'buybacks', '')::int as buybacks,
    nullif(tfp.p->>'xp_start', '')::int as xp_start,
    nullif(tfp.p->>'xp_end', '')::int   as xp_end,
    nullif(tfp.p->>'xp_delta', '')::int as xp_delta,
    nullif(tfp.p->>'gold_delta', '')::int as gold_delta,
    tfp.p->>'ability_uses'   as ability_uses,
    tfp.p->>'item_uses'      as item_uses,
    tfp.p->>'ability_targets' as ability_targets,
    tfp.p->>'killed'         as killed,
    tfp.p->>'deaths_pos'     as deaths_pos,
    tf.loaded_at
from {{ ref('fact_teamfights') }} tf
cross join lateral jsonb_array_elements(tf.players::jsonb) with ordinality as tfp(p, ord)
left join {{ ref('fact_match_players') }} mp
    on mp.match_id = tf.match_id
   and mp.player_slot = (case when tfp.ord <= 5 then tfp.ord - 1 else tfp.ord + 122 end)::text

