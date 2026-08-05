{{ config(materialized='table') }}

-- Conformed team dimension.
-- Teams registered in /teams plus any team_ids that appear only in matches
-- (registered as 'Unknown') so radiant/dire_team_id joins always resolve.
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
