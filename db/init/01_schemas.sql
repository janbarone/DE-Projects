-- 01_schemas.sql
-- Creates the bronze layer schema for the DOTA 2 medallion architecture.
CREATE SCHEMA IF NOT EXISTS bronze;

COMMENT ON SCHEMA bronze IS 'Bronze layer: raw payloads as jsonb, unchanged from source, with load-time stamps.';