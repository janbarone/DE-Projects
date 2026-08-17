{% test seq_in_range(model, column_name) %}
    select *
    from {{ model }}
    where {{ column_name }} is not null
      and ({{ column_name }} < 1 or {{ column_name }} > 10)
{% endtest %}