{% test seq_in_range(model, column_name) %}
    -- The upper bound is data-driven: pick and ban counts change across Dota
    -- patches (e.g. bans went from 5 to 7 per team), so we only assert the
    -- sequence is a positive integer. The model derives its own range.
    select *
    from {{ model }}
    where {{ column_name }} is not null
      and {{ column_name }} < 1
{% endtest %}
