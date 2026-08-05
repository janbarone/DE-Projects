-- 02_bronze_tables.sql
-- Raw tables. Each stores the untouched JSON payload for one source record,
-- plus its natural key and a load-time stamp. No cleaning is done at this layer.

-- Matches: one row per proMatches/<match_id>.json -> one row per match.
CREATE TABLE IF NOT EXISTS bronze.matches (
    match_id      bigint PRIMARY KEY,
    payload       jsonb  NOT NULL,
    loaded_at     timestamptz NOT NULL DEFAULT now()
);

-- Leagues: one row per league entry in leagues.json.
CREATE TABLE IF NOT EXISTS bronze.leagues (
    leagueid      integer PRIMARY KEY,
    payload       jsonb  NOT NULL,
    loaded_at     timestamptz NOT NULL DEFAULT now()
);

-- Players: one row per pro player in proPlayers.json.
CREATE TABLE IF NOT EXISTS bronze.players (
    account_id    integer PRIMARY KEY,
    payload       jsonb  NOT NULL,
    loaded_at     timestamptz NOT NULL DEFAULT now()
);

-- Teams: one row per team in teams.json.
CREATE TABLE IF NOT EXISTS bronze.teams (
    team_id       integer PRIMARY KEY,
    payload       jsonb  NOT NULL,
    loaded_at     timestamptz NOT NULL DEFAULT now()
);

-- Hero stats: one row per hero aggregate in heroStats.json.
CREATE TABLE IF NOT EXISTS bronze.hero_stats (
    id            integer PRIMARY KEY,
    payload       jsonb  NOT NULL,
    loaded_at     timestamptz NOT NULL DEFAULT now()
);

-- Constants: one row per constants/*.json resource, keyed by resource name.
CREATE TABLE IF NOT EXISTS bronze.constants (
    resource      text PRIMARY KEY,
    payload       jsonb  NOT NULL,
    loaded_at     timestamptz NOT NULL DEFAULT now()
);

-- Keep the loader from scanning files with nothing to do.
CREATE INDEX IF NOT EXISTS idx_bronze_matches_loaded_at ON bronze.matches (loaded_at);
CREATE INDEX IF NOT EXISTS idx_bronze_leagues_loaded_at  ON bronze.leagues  (loaded_at);
CREATE INDEX IF NOT EXISTS idx_bronze_players_loaded_at  ON bronze.players  (loaded_at);
CREATE INDEX IF NOT EXISTS idx_bronze_teams_loaded_at    ON bronze.teams    (loaded_at);
CREATE INDEX IF NOT EXISTS idx_bronze_hero_stats_loaded  ON bronze.hero_stats (loaded_at);