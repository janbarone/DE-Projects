{{ config(
    materialized='table',
    post_hook=[
        "create index if not exists {{ this.schema }}_fact_hm_match_idx on {{ this }}(match_id)",
        "create index if not exists {{ this.schema }}_fact_hm_radiant_idx on {{ this }}(radiant_hero_id)",
        "create index if not exists {{ this.schema }}_fact_hm_dire_idx on {{ this }}(dire_hero_id)"
    ]
) }}

-- Hero-vs-hero matchup fact: one row per (match, radiant hero, dire hero) =
-- 25 rows per match. Enables hero matchup / counter matrices that cannot be
-- done live in DirectQuery (two hero dimensions on one row).
-- radiant_win is duplicated from fact_matches for self-contained queries.
-- Unknown heroes (hero_id = '0') are excluded so the fact stays clean.
with radiant_players as (
    select
        match_id,
        hero_id
    from {{ ref('fact_match_players') }}
    where team_number = '0'
      and hero_id <> '0'
),

dire_players as (
    select
        match_id,
        hero_id
    from {{ ref('fact_match_players') }}
    where team_number = '1'
      and hero_id <> '0'
)

select
    m.match_id,
    r.hero_id as radiant_hero_id,
    d.hero_id as dire_hero_id,
    rh.hero_localized_name || ' vs ' || dh.hero_localized_name as matchup_label,
    m.radiant_win
from radiant_players r
join {{ ref('fact_matches') }} m on r.match_id = m.match_id
join dire_players d on r.match_id = d.match_id
left join {{ ref('dim_hero') }} rh on rh.hero_id = r.hero_id
left join {{ ref('dim_hero') }} dh on dh.hero_id = d.hero_id
where m.radiant_win is not null
