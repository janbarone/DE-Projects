{{ config(materialized='table') }}

-- One row per (match, teamfight, player, ability) usage.
-- Flattens fact_teamfight_players.ability_uses (jsonb map stored as text;
-- cast back to jsonb here to parse).
select
    fp.match_id,
    fp.teamfight_id,
    fp.player_slot,
    fp.hero_id,
    fp.account_id,
    kv.key as ability_name,
    kv.value::int as uses
from {{ ref('fact_teamfight_players') }} fp,
     jsonb_each_text(fp.ability_uses::jsonb) as kv
