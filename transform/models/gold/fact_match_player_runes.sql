{{ config(
    materialized='table',
    post_hook=[
        "drop index if exists {{ this.schema }}.{{ this.schema }}_fact_mpr_match_idx",
        "create index {{ this.schema }}_fact_mpr_match_idx on {{ this }}(match_id)",
        "drop index if exists {{ this.schema }}.{{ this.schema }}_fact_mpr_hero_idx",
        "create index {{ this.schema }}_fact_mpr_hero_idx on {{ this }}(hero_id)",
        "drop index if exists {{ this.schema }}.{{ this.schema }}_fact_mpr_account_idx",
        "create index {{ this.schema }}_fact_mpr_account_idx on {{ this }}(account_id)"
    ]) }}

-- One row per (match, player, rune type): total runes picked up. Reads the
-- incremental silver model (stg_match_player_runes) so the jsonb unnest is not
-- repeated. Rune ids are decoded to display names via dim_rune (unknown ids
-- keep the numeric id). Player/hero names are denormalized.
select
    s.match_id,
    s.player_slot,
    s.account_id,
    s.hero_id,
    s.side,
    s.rune_key,
    coalesce(dr.rune_name, s.rune_key::text) as rune_name,
    s.rune_count,
    dp.player_name,
    dh.hero_localized_name
from {{ ref('stg_match_player_runes') }} s
left join {{ ref('dim_rune') }} dr on dr.rune_key = s.rune_key
left join {{ ref('dim_player') }} dp on dp.account_id = s.account_id
left join {{ ref('dim_hero') }} dh on dh.hero_id = s.hero_id
order by s.match_id, s.player_slot, s.rune_key
