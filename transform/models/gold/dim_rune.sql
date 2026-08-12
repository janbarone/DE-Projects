{{ config(materialized='table') }}

-- Rune decode lookup: rune type id -> display name. Seeded from
-- seeds/rune_lookup.csv (OpenDota rune type ids 0-9).
select
    rune_key::int  as rune_key,
    rune_name      as rune_name
from {{ ref('rune_lookup') }}
