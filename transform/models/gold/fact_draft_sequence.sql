{{ config(
    materialized='table',
    post_hook=[
        "drop index if exists {{ this.schema }}.{{ this.schema }}_fact_ds_match_idx",
        "create index {{ this.schema }}_fact_ds_match_idx on {{ this }}(match_id)",
        "drop index if exists {{ this.schema }}.{{ this.schema }}_fact_ds_slot_idx",
        "create index {{ this.schema }}_fact_ds_slot_idx on {{ this }}(slot)"
    ]) }}

-- One row per (match, slot 1-5): each team's pick and ban for that draft
-- slot, denormalized to hero names + images for DirectQuery rendering.
-- slot = the team's own pick order (1-5) and ban order (1-5), both derived
-- from the global draft order_no. The displayed *_seq columns are continuous
-- 1-10: they count picks and bans across BOTH teams in global draft order.
-- Every match with at least one draft event is included; matches with an
-- incomplete draft just leave the missing slots blank (only 201 matches have
-- no picks_bans rows at all).
with pb as (
    select
        match_id,
        order_no_int,
        is_pick,
        active_team,
        hero_id,
        row_number() over (
            partition by match_id, active_team, is_pick
            order by order_no_int
        ) as team_seq,
        row_number() over (
            partition by match_id, is_pick
            order by order_no_int
        ) as global_seq
    from {{ ref('stg_picks_bans') }}
),
dire_pick as (
    select match_id, team_seq, global_seq, hero_id
    from pb
    where active_team = 'Dire' and is_pick
),
dire_ban as (
    select match_id, team_seq, global_seq, hero_id
    from pb
    where active_team = 'Dire' and not is_pick
),
radiant_pick as (
    select match_id, team_seq, global_seq, hero_id
    from pb
    where active_team = 'Radiant' and is_pick
),
radiant_ban as (
    select match_id, team_seq, global_seq, hero_id
    from pb
    where active_team = 'Radiant' and not is_pick
),
matches as (
    select distinct match_id from pb
),
slots as (
    select generate_series(1, 5) as slot
),
grid as (
    select m.match_id, s.slot
    from matches m
    cross join slots s
),
base as (
    select
        g.match_id,
        g.slot,
        dp.hero_id as dire_pick_hero_id,
        dp.global_seq as dire_pick_seq,
        db.hero_id as dire_ban_hero_id,
        db.global_seq as dire_ban_seq,
        rp.hero_id as radiant_pick_hero_id,
        rp.global_seq as radiant_pick_seq,
        rb.hero_id as radiant_ban_hero_id,
        rb.global_seq as radiant_ban_seq
    from grid g
    left join dire_pick dp on dp.match_id = g.match_id and dp.team_seq = g.slot
    left join dire_ban db on db.match_id = g.match_id and db.team_seq = g.slot
    left join radiant_pick rp on rp.match_id = g.match_id and rp.team_seq = g.slot
    left join radiant_ban rb on rb.match_id = g.match_id and rb.team_seq = g.slot
)
select
    b.match_id,
    b.slot,
    dh_dp.hero_localized_name as dire_pick_hero,
    dh_dp.img as dire_pick_hero_img,
    b.dire_pick_seq,
    dh_db.hero_localized_name as dire_ban_hero,
    dh_db.img as dire_ban_hero_img,
    b.dire_ban_seq,
    dh_rp.hero_localized_name as radiant_pick_hero,
    dh_rp.img as radiant_pick_hero_img,
    b.radiant_pick_seq,
    dh_rb.hero_localized_name as radiant_ban_hero,
    dh_rb.img as radiant_ban_hero_img,
    b.radiant_ban_seq
from base b
left join {{ ref('dim_hero') }} dh_dp on dh_dp.hero_id = b.dire_pick_hero_id
left join {{ ref('dim_hero') }} dh_db on dh_db.hero_id = b.dire_ban_hero_id
left join {{ ref('dim_hero') }} dh_rp on dh_rp.hero_id = b.radiant_pick_hero_id
left join {{ ref('dim_hero') }} dh_rb on dh_rb.hero_id = b.radiant_ban_hero_id
order by b.match_id, b.slot