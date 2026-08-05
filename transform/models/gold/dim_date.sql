{{ config(materialized='table') }}

-- Calendar dimension covering a wide date range for any time-based analysis.
-- One row per day from 2000-01-01 through 2050-12-31. Joins to
-- fact_matches.start_date (and can join to any other date key).
with dates as (
    select generate_series(
        date '2000-01-01',
        date '2050-12-31',
        interval '1 day'
    )::date as date
)
select
    d.date,
    extract(day from d.date)::int                     as day_of_month,
    extract(dow from d.date)::int                     as day_of_week,          -- 0 = Sunday
    to_char(d.date, 'Day')                            as day_of_week_name,     -- e.g. 'Sunday'
    to_char(d.date, 'Dy')                             as day_of_week_short_name,
    extract(isodow from d.date)::int                  as iso_day_of_week,      -- 1 = Monday
    case when extract(dow from d.date)::int in (0, 6) then true else false end as is_weekend,
    extract(doy from d.date)::int                     as day_of_year,
    extract(week from d.date)::int                    as week_of_year,
    extract(week from d.date)::int                    as iso_week_of_year,     -- PG week extract is ISO-8601
    date_trunc('week', d.date)::date                  as week_start_date,      -- Monday-based
    extract(month from d.date)::int                   as month,
    to_char(d.date, 'Month')                          as month_name,           -- e.g. 'January'
    to_char(d.date, 'Mon')                            as month_short_name,     -- e.g. 'Jan'
    to_char(d.date, 'YYYY-MM')                        as year_month,           -- e.g. '2024-01'
    extract(quarter from d.date)::int                 as quarter,
    'Q' || extract(quarter from d.date)::int          as quarter_name,         -- e.g. 'Q1'
    to_char(d.date, 'YYYY') || '-Q' || extract(quarter from d.date)::int as year_quarter,
    extract(year from d.date)::int                    as year,
    to_char(d.date, 'YYYY') || '-' || to_char(d.date, 'Mon') as year_month_name, -- e.g. '2024-Jan'
    (extract(year from d.date)::int % 4 = 0
     and extract(year from d.date)::int % 100 <> 0)
     or extract(year from d.date)::int % 400 = 0      as is_leap_year
from dates d
