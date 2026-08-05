{{ config(materialized='table') }}

-- One row per (match, teamfight, killer player, victim hero) kill event.
-- Flattens fact_teamfight_players.killed (jsonb map stored as text;
-- cast back to jsonb here to parse).
-- The victim key is an npc hero name (e.g. npc_dota_hero_dazzle) that matches
-- dim_hero.hero_name, so the victim links to dim_hero too.
select
    fp.match_id,
    fp.teamfight_id,
    fp.player_slot,
    fp.hero_id,
    fp.account_id,
    kv.key as victim_hero_name,
    kv.value::int as kills,
    vh.hero_id as victim_hero_id
from {{ ref('fact_teamfight_players') }} fp,
     jsonb_each_text(fp.killed::jsonb) as kv
left join {{ ref('dim_hero') }} vh
    on vh.hero_name = kv.key
