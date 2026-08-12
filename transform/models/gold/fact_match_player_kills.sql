{{ config(
    materialized='table',
    post_hook=[
        "create index if not exists {{ this.schema }}_fact_mpk_match_idx on {{ this }}(match_id)",
        "create index if not exists {{ this.schema }}_fact_mpk_player_idx on {{ this }}(player_slot)",
        "create index if not exists {{ this.schema }}_fact_mpk_minute_idx on {{ this }}(minute)"
    ]
) }}

-- One row per (match, killer player, kill event): the hero's kill timeline.
-- Reads the incremental silver model (stg_match_player_kills) so the jsonb
-- unnest is not repeated. The victim key is an npc hero name
-- (e.g. npc_dota_hero_jakiro) that matches dim_hero.hero_name, so each kill
-- links the killer hero and the victim hero. Player/hero names are
-- denormalized from dim_player / dim_hero.
select
    s.match_id,
    s.player_slot,
    s.account_id,
    s.hero_id,
    s.side,
    s.kill_index,
    s.time_sec,
    s.minute,
    s.victim_hero_name,
    vh.hero_id          as victim_hero_id,
    coalesce(vh.hero_localized_name, s.victim_hero_name) as victim_hero_name_localized,
    case when vh.hero_id is not null then 'Hero' else 'Unit' end as victim_type,
    dp.player_name,
    dh.hero_localized_name as killer_hero_name
from {{ ref('stg_match_player_kills') }} s
left join {{ ref('dim_hero') }} vh on vh.hero_name = s.victim_hero_name
left join {{ ref('dim_player') }} dp on dp.account_id = s.account_id
left join {{ ref('dim_hero') }} dh on dh.hero_id = s.hero_id
order by s.match_id, s.player_slot, s.kill_index
