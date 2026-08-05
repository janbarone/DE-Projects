-- Singular test: the grain of fact_team_matches is one row per (match, side).
-- Fails if any (match_id, side) pair appears more than once.
select
    match_id,
    side,
    count(*) as row_count
from {{ ref('fact_team_matches') }}
group by match_id, side
having count(*) > 1
