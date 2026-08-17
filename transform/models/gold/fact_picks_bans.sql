{{ config(
    materialized='table',
    post_hook=[
        "drop index if exists {{ this.schema }}.{{ this.schema }}_fact_pb_match_idx",
        "create index {{ this.schema }}_fact_pb_match_idx on {{ this }}(match_id)",
        "drop index if exists {{ this.schema }}.{{ this.schema }}_fact_pb_hero_idx",
        "create index {{ this.schema }}_fact_pb_hero_idx on {{ this }}(hero_id)"
    ]) }}

-- One row per (match, draft order): draft picks and bans.
-- hero_id resolves to dim_hero; matches with missing picks_bans simply have no
-- rows here (200 matches, expected).
select
    match_id,
    order_no,
    order_no_int,
    hero_id,
    is_pick,
    team_number,
    active_team,
    player_slot,
    loaded_at
from {{ ref('stg_picks_bans') }}
