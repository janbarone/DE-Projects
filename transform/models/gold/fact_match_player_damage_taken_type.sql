{{ config(
    materialized='table',
    post_hook=[
        "create index if not exists {{ this.schema }}_fact_mpdtt_match_idx on {{ this }}(match_id)",
        "create index if not exists {{ this.schema }}_fact_mpdtt_player_idx on {{ this }}(player_slot)"
    ]
) }}

-- One row per (match, player, damage type): total raw damage received by type
-- (Physical / Magical / Pure / Other). Reads the incremental silver model
-- (stg_match_player_damage_taken_type) so the jsonb unnest + type decode is not
-- repeated. Player/hero names are denormalized.
select
    s.match_id,
    s.player_slot,
    s.account_id,
    s.hero_id,
    s.side,
    s.damage_type,
    sum(s.damage_amount)::int as damage_amount,
    dp.player_name,
    dh.hero_localized_name
from {{ ref('stg_match_player_damage_taken_type') }} s
left join {{ ref('dim_player') }} dp on dp.account_id = s.account_id
left join {{ ref('dim_hero') }} dh on dh.hero_id = s.hero_id
group by s.match_id, s.player_slot, s.account_id, s.hero_id, s.side, s.damage_type,
         dp.player_name, dh.hero_localized_name
order by s.match_id, s.player_slot, s.damage_type
