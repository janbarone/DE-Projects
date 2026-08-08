{{ config(materialized='table') }}

-- Conformed player dimension covering every account_id present in the facts.
-- Pro players carry metadata; non-pro match participants resolve to an
-- 'Unknown' row (name unavailable) so the Power BI relationship from
-- fact_match_players never fails validation. Statistics over the loaded
-- matches are precomputed as plain columns for DirectQuery leaderboards.
with player_dim as (
    select
        account_id,
        player_name,
        rank_tier,
        team_id,
        'pro' as player_type
    from {{ ref('stg_players') }}

    union all

    select distinct
        mp.account_id,
        null::text as player_name,
        null::text as rank_tier,
        null::text as team_id,
        'match_participant' as player_type
    from {{ ref('stg_match_players') }} mp
    where mp.account_id not in (select account_id from {{ ref('stg_players') }})
),

player_stats as (
    select
        account_id,
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
        count(*) filter (where firstblood_claimed = 1)::int as match_firstbloods,
        round(avg(rune_pickups), 2) as match_avg_rune_pickups,
        round(avg(buyback_count), 2) as match_avg_buybacks
    from {{ ref('fact_match_players') }}
    group by account_id
)

select
    d.account_id,
    d.player_name,
    d.rank_tier,
    d.team_id,
    d.player_type,
    coalesce(ps.match_picks, 0) as match_picks,
    coalesce(ps.match_wins, 0) as match_wins,
    coalesce(ps.match_win_rate, 0) as match_win_rate,
    ps.match_avg_kda,
    ps.match_avg_gpm,
    ps.match_avg_xpm,
    ps.match_avg_hero_damage,
    ps.match_avg_tower_damage,
    ps.match_avg_hero_healing,
    ps.match_avg_last_hits,
    ps.match_avg_denies,
    ps.match_avg_net_worth,
    ps.match_avg_stuns,
    ps.match_avg_level,
    coalesce(ps.match_total_kills, 0) as match_total_kills,
    coalesce(ps.match_total_deaths, 0) as match_total_deaths,
    coalesce(ps.match_total_assists, 0) as match_total_assists,
    coalesce(ps.match_firstbloods, 0) as match_firstbloods,
    ps.match_avg_rune_pickups,
    ps.match_avg_buybacks
from player_dim d
left join player_stats ps on d.account_id = ps.account_id
