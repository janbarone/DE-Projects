{{ config(materialized='table') }}

-- Conformed hero dimension.
-- Merges stg_heroes (identity) with stg_hero_stats (OpenDota global pub/pro
-- aggregates) into a single self-contained dimension, appends an 'Unknown'
-- hero (hero_id = 0) so that every hero_id appearing in the fact tables
-- (including OpenDota's hero_id = 0 placeholder) resolves cleanly in Power BI,
-- and precomputes statistics over the loaded matches (fact_match_players) plus
-- draft counts (fact_picks_bans) as plain columns for DirectQuery leaderboards.
with hero_dim as (
    select
        h.hero_id,
        coalesce(h.hero_name, 'unknown')       as hero_name,
        coalesce(h.localized_name, 'Unknown')  as hero_localized_name,
        h.primary_attr,
        h.attack_type,
        h.roles,
        h.img,
        s.pro_pick,
        s.pro_win,
        s.pro_ban,
        s.pub_pick,
        s.pub_win,
        s.pub_win_rate
    from {{ ref('stg_heroes') }} h
    left join {{ ref('stg_hero_stats') }} s on h.hero_id = s.hero_id

    union all

    -- Unknown hero placeholder (OpenDota uses hero_id = 0 for missing heroes).
    select
        '0',
        'unknown',
        'Unknown',
        null,
        null,
        null,
        null,
        null, null, null, null, null, null
),

hero_stats as (
    select
        hero_id,
        count(*)::int as match_picks,
        count(*) filter (where team_win)::int as match_wins,
        round(count(*) filter (where team_win)::numeric / nullif(count(*), 0), 4) as match_win_rate,
        round(avg(kda), 2) as match_avg_kda,
        round(avg(gold_per_min), 0) as match_avg_gpm,
        round(avg(xp_per_min), 0) as match_avg_xpm,
        round(avg(hero_damage), 0) as match_avg_hero_damage,
        round(avg(tower_damage), 0) as match_avg_tower_damage,
        round(avg(hero_healing), 0) as match_avg_hero_healing,
        round(avg(last_hits), 1) as match_avg_last_hits,
        round(avg(denies), 1) as match_avg_denies,
        round(avg(net_worth), 0) as match_avg_net_worth,
        round(avg(stuns), 2) as match_avg_stuns,
        round(avg(nullif(level, '')::numeric), 2) as match_avg_level,
        sum(kills)::int as match_total_kills,
        sum(deaths)::int as match_total_deaths,
        sum(assists)::int as match_total_assists,
        count(*) filter (where firstblood_claimed = 1)::int as match_firstbloods
    from {{ ref('fact_match_players') }}
    group by hero_id
),

draft_stats as (
    select
        hero_id,
        count(*) filter (where is_pick)::int as match_draft_picks,
        count(*) filter (where not is_pick)::int as match_draft_bans
    from {{ ref('fact_picks_bans') }}
    group by hero_id
)

select
    d.hero_id,
    d.hero_name,
    d.hero_localized_name,
    d.primary_attr,
    d.attack_type,
    d.roles,
    d.img,
    d.pro_pick,
    d.pro_win,
    d.pro_ban,
    d.pub_pick,
    d.pub_win,
    d.pub_win_rate,
    coalesce(hs.match_picks, 0) as match_picks,
    coalesce(hs.match_wins, 0) as match_wins,
    coalesce(hs.match_win_rate, 0) as match_win_rate,
    hs.match_avg_kda,
    hs.match_avg_gpm,
    hs.match_avg_xpm,
    hs.match_avg_hero_damage,
    hs.match_avg_tower_damage,
    hs.match_avg_hero_healing,
    hs.match_avg_last_hits,
    hs.match_avg_denies,
    hs.match_avg_net_worth,
    hs.match_avg_stuns,
    hs.match_avg_level,
    coalesce(hs.match_total_kills, 0) as match_total_kills,
    coalesce(hs.match_total_deaths, 0) as match_total_deaths,
    coalesce(hs.match_total_assists, 0) as match_total_assists,
    coalesce(hs.match_firstbloods, 0) as match_firstbloods,
    coalesce(ds.match_draft_picks, 0) as match_draft_picks,
    coalesce(ds.match_draft_bans, 0) as match_draft_bans
from hero_dim d
left join hero_stats hs on d.hero_id = hs.hero_id
left join draft_stats ds on d.hero_id = ds.hero_id
