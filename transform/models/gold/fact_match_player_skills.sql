{{ config(
    materialized='table',
    post_hook=[
        "drop index if exists {{ this.schema }}.{{ this.schema }}_fact_mps_match_idx",
        "create index {{ this.schema }}_fact_mps_match_idx on {{ this }}(match_id)",
        "drop index if exists {{ this.schema }}.{{ this.schema }}_fact_mps_hero_idx",
        "create index {{ this.schema }}_fact_mps_hero_idx on {{ this }}(hero_id)",
        "drop index if exists {{ this.schema }}.{{ this.schema }}_fact_mps_account_idx",
        "create index {{ this.schema }}_fact_mps_account_idx on {{ this }}(account_id)"
    ]) }}

-- One row per (match, player, ability upgrade): the hero's skill progression.
-- Reads the incremental silver model (stg_match_player_skills) so the jsonb
-- unnest is not repeated. Ability ids are decoded to display names through
-- constants: ability_ids (numeric id -> internal name) then abilities
-- (internal name -> dname), so talents like special_bonus_* render as
-- "+40 Damage" rather than internal identifiers.
--
-- The `minute` is an approximation: the k-th upgrade (0-based) is assigned the
-- first minute at which the player's per-minute derived level reached k+1,
-- i.e. the earliest level at which that skill point could have been spent.
-- If the player never reached level k+1 (older matches under-report the final
-- level), the last recorded level-up minute is used. All joins are hash joins
-- on the grouped per-level table (no correlated subqueries).
with level_first_minute as (
    select
        match_id,
        player_slot,
        level,
        min(minute) as first_minute
    from {{ ref('fact_match_player_minute') }}
    group by match_id, player_slot, level
),
max_level_minute as (
    select
        match_id,
        player_slot,
        first_minute as last_minute
    from (
        select
            match_id,
            player_slot,
            first_minute,
            row_number() over (partition by match_id, player_slot order by level desc) as rn
        from level_first_minute
    ) t
    where rn = 1
),
ability_dnames as (
    -- abilities keys (e.g. sandking_caustic_finale) use a different naming
    -- convention than ability_ids (e.g. sand_king_caustic_finale), so join on
    -- underscore-stripped keys (verified collision-free). Generic attribute
    -- bonus lives in abilities under invoker_attribute_bonus.
    select
        replace(kv.key, '_', '') as norm_key,
        kv.value->>'dname' as dname,
        kv.value->>'img'  as img
    from {{ source('bronze', 'constants') }} c
    cross join lateral jsonb_each(c.payload) as kv(key, value)
    where c.resource = 'abilities'
      and (kv.value->>'dname') is not null
      and kv.value->>'dname' <> ''
),
decoded as (
    select
        ug.match_id,
        ug.player_slot,
        ug.account_id,
        ug.hero_id,
        ug.side,
        ug.upgrade_index,
        ug.ability_id,
        ai.payload->>(ug.ability_id) as ability_internal_name,
        coalesce(
            ad.dname,
            case when ai.payload->>(ug.ability_id) = 'attribute_bonus' then 'Attribute Bonus' end,
            nullif(ai.payload->>(ug.ability_id), ''),
            ug.ability_id
        ) as raw_ability_name,
        ad.img as ability_img_raw,
        coalesce(lfm.first_minute, mlm.last_minute, 0) as minute,
        ug.upgrade_index + 1 as learn_level,
        dp.player_name,
        dh.hero_localized_name
    from {{ ref('stg_match_player_skills') }} ug
    left join {{ source('bronze', 'constants') }} ai on ai.resource = 'ability_ids'
    left join ability_dnames ad
        on ad.norm_key = replace(nullif(ai.payload->>(ug.ability_id), ''), '_', '')
    left join {{ ref('dim_player') }} dp on dp.account_id = ug.account_id
    left join {{ ref('dim_hero') }} dh on dh.hero_id = ug.hero_id
    left join level_first_minute lfm
        on lfm.match_id = ug.match_id
       and lfm.player_slot = ug.player_slot
       and lfm.level = ug.upgrade_index + 1
    left join max_level_minute mlm
        on mlm.match_id = ug.match_id
       and mlm.player_slot = ug.player_slot
)
select
    match_id,
    player_slot,
    account_id,
    hero_id,
    side,
    upgrade_index,
    ability_id,
    ability_internal_name,
    -- Talent detection: a talent is any ability whose internal name starts
    -- with special_bonus (talent-tree pick) or is the generic attribute bonus.
    case
        when ability_internal_name like 'special_bonus%' or ability_internal_name = 'attribute_bonus'
            then true else false
    end as is_talent,
    -- Cleaned ability name: for talents, strip the unresolved +{s:...} /
    -- -{s:...} value template so rows read as e.g. "Reflection Duration"
    -- rather than "+{s:bonus_illusion_duration}s Reflection Duration".
    case
        when ability_internal_name like 'special_bonus%' or ability_internal_name = 'attribute_bonus' then
            case
                when ability_internal_name = 'attribute_bonus' then 'Attribute Bonus'
                when ability_internal_name = 'special_bonus_attributes' then 'Attribute Bonus'
                else trim(regexp_replace(raw_ability_name, '^[+-]\s*\{s:[a-zA-Z0-9_]+\}\s*[%a-zA-Z]*\s*', '', 'g'))
            end
        else raw_ability_name
    end as ability_name,
    -- Full CDN URL so Power BI can render the ability icon (same pattern as
    -- dim_hero.img). Talents and a few utility abilities have no icon -> null.
    case
        when nullif(ability_img_raw, '') is null then null
        else 'https://cdn.cloudflare.steamstatic.com' || ability_img_raw
    end as ability_img,
    minute,
    learn_level,
    player_name,
    hero_localized_name
from decoded
order by match_id, player_slot, upgrade_index
