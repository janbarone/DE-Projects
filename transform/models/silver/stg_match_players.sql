{{ config(
    materialized='incremental',
    unique_key=['match_id', 'player_slot'],
    post_hook=[
        "create index if not exists {{ this.schema }}_stg_match_players_acct_idx on {{ this }}(account_id)",
        "create index if not exists {{ this.schema }}_stg_match_players_hero_idx on {{ this }}(hero_id)",
        "create index if not exists {{ this.schema }}_stg_match_players_match_idx on {{ this }}(match_id)"
    ]
) }}

-- One row per (match, player): the players[] array flattened.
select
    m.payload->>'match_id' as match_id,
    p.value->>'player_slot' as player_slot,
    nullif(p.value->>'account_id', '') as account_id,
    nullif(p.value->>'hero_id', '') as hero_id,
    nullif(p.value->>'team_number', '') as team_number,
    case
        when p.value->>'team_number' = '0' then (m.payload->>'radiant_win')::boolean
        when p.value->>'team_number' = '1' then not (m.payload->>'radiant_win')::boolean
        else null
    end as team_win,
    nullif(p.value->>'kills', '')::int as kills,
    nullif(p.value->>'deaths', '')::int as deaths,
    nullif(p.value->>'assists', '')::int as assists,
    case
        when nullif(p.value->>'deaths', '')::numeric > 0
        then round((nullif(p.value->>'kills', '')::numeric
                   + nullif(p.value->>'assists', '')::numeric)
                   / nullif(p.value->>'deaths', '')::numeric, 2)
        else round(nullif(p.value->>'kills', '')::numeric
                 + nullif(p.value->>'assists', '')::numeric, 2)
    end as kda,
    nullif(p.value->>'gold', '')::int as gold,
    nullif(p.value->>'gold_spent', '')::int as gold_spent,
    nullif(p.value->>'net_worth', '')::int as net_worth,
    nullif(p.value->>'gold_per_min', '')::int as gold_per_min,
    nullif(p.value->>'xp_per_min', '')::int as xp_per_min,
    nullif(p.value->>'hero_damage', '')::int as hero_damage,
    nullif(p.value->>'hero_healing', '')::int as hero_healing,
    nullif(p.value->>'tower_damage', '')::int as tower_damage,
    nullif(p.value->>'tower_kills', '')::int as tower_kills,
    nullif(p.value->>'stuns', '')::numeric as stuns,
    nullif(p.value->>'last_hits', '')::int as last_hits,
    nullif(p.value->>'denies', '')::int as denies,
    nullif(p.value->>'camps_stacked', '')::int as camps_stacked,
    nullif(p.value->>'creeps_stacked', '')::int as creeps_stacked,
    nullif(p.value->>'neutral_kills', '')::int as neutral_kills,
    nullif(p.value->>'rune_pickups', '')::int as rune_pickups,
    -- Ward placements: the obs_placed / sen_placed scalars are null for most
    -- players even in parsed matches, so derive from the authoritative
    -- obs_log / sen_log arrays (one entry per ward placed). Fall back to the
    -- scalar when the array is absent.
    coalesce(
        case when jsonb_typeof(p.value->'obs_log') = 'array' then jsonb_array_length(p.value->'obs_log') end,
        nullif(p.value->>'obs_placed', '')::int,
        0
    ) as obs_placed,
    coalesce(
        case when jsonb_typeof(p.value->'sen_log') = 'array' then jsonb_array_length(p.value->'sen_log') end,
        nullif(p.value->>'sen_placed', '')::int,
        0
    ) as sen_placed,
    nullif(p.value->>'observer_kills', '')::int as observer_kills,
    nullif(p.value->>'sentry_kills', '')::int as sentry_kills,
    nullif(p.value->>'purchase_ward_observer', '')::int as purchase_ward_observer,
    nullif(p.value->>'purchase_ward_sentry', '')::int as purchase_ward_sentry,
    nullif(p.value->>'personaname', '') as personaname,
    nullif(p.value->>'level', '') as level,
    nullif(p.value->>'item_0', '') as item_0,
    nullif(p.value->>'item_1', '') as item_1,
    nullif(p.value->>'item_2', '') as item_2,
    nullif(p.value->>'item_3', '') as item_3,
    nullif(p.value->>'item_4', '') as item_4,
    nullif(p.value->>'item_5', '') as item_5,
    nullif(p.value->>'item_neutral', '') as item_neutral,
    nullif(p.value->>'backpack_0', '') as backpack_0,
    nullif(p.value->>'backpack_1', '') as backpack_1,
    nullif(p.value->>'backpack_2', '') as backpack_2,
    nullif(p.value->>'backpack_3', '') as backpack_3,
    nullif(p.value->>'leaver_status', '') as leaver_status,
    (p.value->>'randomed')::boolean as randomed,
    (p.value->>'firstblood_claimed')::int as firstblood_claimed,
    nullif(p.value->>'buyback_count', '')::int as buyback_count,
    coalesce((m.payload->>'timestamp_fetched')::timestamptz, m.loaded_at) as loaded_at
from {{ source('bronze', 'matches') }} m,
     lateral jsonb_array_elements(m.payload->'players') as p
{% if is_incremental() %}
where m.payload->>'match_id' is not null
  and m.payload->>'match_id' not in (select match_id from {{ this }})
{% endif %}
