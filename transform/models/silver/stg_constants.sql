{{ config(materialized='view') }}

-- One row per constants resource, exposing all static lookup data in silver.
-- payload keeps the full resource jsonb (object or array) for flexible use.
select
    resource,
    payload as resource_payload,
    jsonb_typeof(payload) as payload_type,
    loaded_at
from {{ source('bronze', 'constants') }}
