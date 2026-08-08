{{ config(materialized='table') }}

-- Minute dimension 0..max-minutes across the per-minute / progression facts
-- so the Play Axis has a single shared minute to scrub the Itemization and
-- Skill levelling tables. Each fact's minute column is related here in the
-- semantic model.
select
    generate_series(0, greatest(
        coalesce((select max(minute) from {{ ref('fact_match_player_minute') }}), 0),
        coalesce((select max(minute) from {{ ref('fact_match_player_skills') }}), 0),
        coalesce((select max(minute) from {{ ref('fact_match_player_item_purchases') }}), 0)
    )) as minute
