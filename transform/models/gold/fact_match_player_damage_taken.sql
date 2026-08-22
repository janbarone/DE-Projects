{{ config(
    materialized='table',
    post_hook=[
        "drop index if exists {{ this.schema }}.{{ this.schema }}_fact_mpdt_match_idx",
        "create index {{ this.schema }}_fact_mpdt_match_idx on {{ this }}(match_id)",
        "drop index if exists {{ this.schema }}.{{ this.schema }}_fact_mpdt_hero_idx",
        "create index {{ this.schema }}_fact_mpdt_hero_idx on {{ this }}(hero_id)",
        "drop index if exists {{ this.schema }}.{{ this.schema }}_fact_mpdt_account_idx",
        "create index {{ this.schema }}_fact_mpdt_account_idx on {{ this }}(account_id)"
    ]) }}

-- One row per (match, player, damage source): raw damage received from each
-- unit, categorized by source type. Reads the incremental silver model
-- (stg_match_player_damage_taken) so the jsonb unnest is not repeated.
--
-- source_category mirrors fact_match_player_damage.target_category:
--   'Hero' / 'Building' / 'Creep' / 'Neutral' / 'Ward' / 'Other'
-- Note: OpenDota's damage_taken is raw (pre-mitigation) damage; the reduced
-- (post-mitigation) figure is not separately exposed, but can be reconstructed
-- from damage_inflictor_received if needed.
select
    s.match_id,
    s.player_slot,
    s.account_id,
    s.hero_id,
    s.side,
    s.source_key,
    case
        when vh.hero_id is not null then 'Hero'
        when s.source_key like 'npc_dota_%tower%' or s.source_key like '%_rax%'
             or s.source_key like '%ancient%' then 'Building'
        when s.source_key like 'npc_dota_creep%' then 'Creep'
        when s.source_key like 'npc_dota_neutral%' then 'Neutral'
        when s.source_key like '%ward%' then 'Ward'
        else 'Other'
    end as source_category,
    coalesce(vh.hero_localized_name, s.source_key) as source_name,
    s.damage_amount,
    dp.player_name,
    dh.hero_localized_name as hero_name
from {{ ref('stg_match_player_damage_taken') }} s
left join {{ ref('dim_hero') }} vh on vh.hero_name = s.source_key
left join {{ ref('dim_player') }} dp on dp.account_id = s.account_id
left join {{ ref('dim_hero') }} dh on dh.hero_id = s.hero_id
