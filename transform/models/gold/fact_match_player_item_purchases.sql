{{ config(
    materialized='table',
    post_hook=[
        "drop index if exists {{ this.schema }}.{{ this.schema }}_fact_mpip_match_idx",
        "create index {{ this.schema }}_fact_mpip_match_idx on {{ this }}(match_id)",
        "drop index if exists {{ this.schema }}.{{ this.schema }}_fact_mpip_hero_idx",
        "create index {{ this.schema }}_fact_mpip_hero_idx on {{ this }}(hero_id)",
        "drop index if exists {{ this.schema }}.{{ this.schema }}_fact_mpip_account_idx",
        "create index {{ this.schema }}_fact_mpip_account_idx on {{ this }}(account_id)"
    ]) }}

-- One row per (match, player, item purchase): the hero's itemization over
-- time. Reads the incremental silver model (stg_match_player_item_purchases)
-- so the jsonb unnest is not repeated. Items are decoded to display names via
-- dim_item.item_internal_name (unmatched keys keep the internal name).
-- Player/hero names are denormalized from dim_player / dim_hero.
select
    s.match_id,
    s.player_slot,
    s.account_id,
    s.hero_id,
    s.side,
    s.purchase_index,
    s.item_internal_name,
    s.time_sec,
    s.minute,
    coalesce(di.item_name, s.item_internal_name) as item_name,
    di.img,
    dp.player_name,
    dh.hero_localized_name
from {{ ref('stg_match_player_item_purchases') }} s
left join {{ ref('dim_item') }} di on di.item_internal_name = s.item_internal_name
left join {{ ref('dim_player') }} dp on dp.account_id = s.account_id
left join {{ ref('dim_hero') }} dh on dh.hero_id = s.hero_id
order by s.match_id, s.player_slot, s.purchase_index
