-- Singular test: fact_draft_sequence must produce a slot for every pick/ban
-- position that exists in the source. Regression guard for the dynamic-slot
-- fix (bans per team grew 5 -> 7); fails if the slot count is ever capped
-- below the data's max picks/bans per team.
with max_slot as (
    select max(slot) as slot_max
    from {{ ref('fact_draft_sequence') }}
),
max_team_seq as (
    select max(team_seq) as seq_max
    from (
        select
            row_number() over (
                partition by match_id, active_team, is_pick
                order by order_no_int
            ) as team_seq
        from {{ ref('stg_picks_bans') }}
    ) t
)
select *
from max_slot, max_team_seq
where max_slot.slot_max < max_team_seq.seq_max
