{{ config(materialized='table') }}

-- Conformed team dimension.
-- Teams registered in /teams plus any team_ids that appear only in matches
-- (registered as 'Unknown') so radiant/dire_team_id joins always resolve.
-- Statistics over the loaded matches (fact_team_matches) are precomputed as
-- plain columns for DirectQuery leaderboards. The /teams API columns (rating,
-- wins, losses) are kept as-is; the match_* columns reflect our own matches.
with team_dim as (
    select
        team_id,
        team_name,
        team_tag,
        rating,
        wins,
        losses,
        logo_url
    from {{ ref('stg_teams') }}

    union

    -- Team ids seen in matches but not in the /teams endpoint. The union also
    -- deduplicates teams that appear on both the radiant and dire side.
    select distinct
        t.team_id,
        'Unknown' as team_name,
        null::text as team_tag,
        null::numeric as rating,
        null::int as wins,
        null::int as losses,
        null::text as logo_url
    from (
        select radiant_team_id as team_id from {{ ref('stg_matches') }} where radiant_team_id is not null
        union
        select dire_team_id as team_id from {{ ref('stg_matches') }} where dire_team_id is not null
    ) t
    where t.team_id not in (select team_id from {{ ref('stg_teams') }})
),

team_stats as (
    select
        team_id,
        count(*)::int as match_appearances,
        count(*) filter (where team_win)::int as match_wins,
        count(*) filter (where not team_win)::int as match_losses,
        round(count(*) filter (where team_win)::numeric / nullif(count(*), 0), 4) as match_win_rate,
        round(avg(team_score), 1) as match_avg_score,
        round(avg(opponent_score), 1) as match_avg_opponent_score,
        round(avg(team_score - opponent_score), 2) as match_avg_score_differential,
        sum(team_score)::int as match_total_score
    from {{ ref('fact_team_matches') }}
    group by team_id
)

select
    d.team_id,
    d.team_name,
    d.team_tag,
    d.rating,
    d.wins,
    d.losses,
    d.logo_url,
    coalesce(ts.match_appearances, 0) as match_appearances,
    coalesce(ts.match_wins, 0) as match_wins,
    coalesce(ts.match_losses, 0) as match_losses,
    coalesce(ts.match_win_rate, 0) as match_win_rate,
    ts.match_avg_score,
    ts.match_avg_opponent_score,
    ts.match_avg_score_differential,
    coalesce(ts.match_total_score, 0) as match_total_score
from team_dim d
left join team_stats ts on d.team_id = ts.team_id
