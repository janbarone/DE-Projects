{{ config(
    materialized='table',
    post_hook=[
        "create index if not exists {{ this.schema }}_fact_mpd_match_idx on {{ this }}(match_id)",
        "create index if not exists {{ this.schema }}_fact_mpd_player_idx on {{ this }}(player_slot)"
    ]
) }}

-- One row per (match, player, damage target): total damage dealt to each unit,
-- categorized by target type. Reads the incremental silver model
-- (stg_match_player_damage) so the jsonb unnest is not repeated.
--
-- target_category:
--   'Hero'      -> npc_dota_hero_* or illusion_* (decoded via dim_hero)
--   'Building'  -> towers / rax / ancient (npc_dota_*tower*, *rax*, ancient)
--   'Creep'     -> npc_dota_creep_*
--   'Neutral'   -> npc_dota_neutral_*
--   'Ward'      -> observer / sentry wards
--   'Other'     -> anything else
select
    s.match_id,
    s.player_slot,
    s.account_id,
    s.hero_id,
    s.side,
    s.target_key,
    case
        when vh.hero_id is not null then 'Hero'
        when s.target_key like 'npc_dota_%tower%' or s.target_key like '%_rax%'
             or s.target_key like '%ancient%' then 'Building'
        when s.target_key like 'npc_dota_creep%' then 'Creep'
        when s.target_key like 'npc_dota_neutral%' then 'Neutral'
        when s.target_key like '%ward%' then 'Ward'
        else 'Other'
    end as target_category,
    coalesce(vh.hero_localized_name, s.target_key) as target_name,
    s.damage_amount,
    dp.player_name,
    dh.hero_localized_name as hero_name
from {{ ref('stg_match_player_damage') }} s
left join {{ ref('dim_hero') }} vh on vh.hero_name = s.target_key
left join {{ ref('dim_player') }} dp on dp.account_id = s.account_id
left join {{ ref('dim_hero') }} dh on dh.hero_id = s.hero_id
order by s.match_id, s.player_slot, s.target_key
