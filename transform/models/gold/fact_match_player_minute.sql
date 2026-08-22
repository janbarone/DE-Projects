{{ config(
    materialized='table',
    post_hook=[
        "drop index if exists {{ this.schema }}.{{ this.schema }}_fact_mpm_match_idx",
        "create index {{ this.schema }}_fact_mpm_match_idx on {{ this }}(match_id)",
        "drop index if exists {{ this.schema }}.{{ this.schema }}_fact_mpm_hero_idx",
        "create index {{ this.schema }}_fact_mpm_hero_idx on {{ this }}(hero_id)",
        "drop index if exists {{ this.schema }}.{{ this.schema }}_fact_mpm_account_idx",
        "create index {{ this.schema }}_fact_mpm_account_idx on {{ this }}(account_id)"
    ]) }}

-- One row per (match, player, minute): the player's progression through the
-- match. Reads the incremental silver model (stg_match_player_minute) so the
-- expensive jsonb unnest is not repeated on every rebuild. Level is derived
-- from the cumulative xp using the xp_level constant thresholds (verified
-- against current-patch matches where derived level == reported level).
-- Player/hero names are denormalized from dim_player / dim_hero.
with xp_levels as (
    select payload as xp_level
    from {{ source('bronze', 'constants') }}
    where resource = 'xp_level'
)
select
    s.match_id,
    s.player_slot,
    s.account_id,
    s.hero_id,
    s.side,
    s.minute,
    s.time_sec,
    s.gold,
    s.xp,
    (
        select count(*)::int
        from jsonb_array_elements((select xp_level from xp_levels)) e
        where e.value::numeric <= s.xp
    ) as level,
    s.last_hits,
    s.denies,
    dp.player_name,
    dh.hero_localized_name
from {{ ref('stg_match_player_minute') }} s
left join {{ ref('dim_player') }} dp on dp.account_id = s.account_id
left join {{ ref('dim_hero') }} dh on dh.hero_id = s.hero_id
