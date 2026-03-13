-- CopyTrade Pro — Database Initialization
-- This runs once when the PostgreSQL container is first created.

-- Enable extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- Performance indexes will be created by Alembic migrations
-- This file only handles extensions and initial setup

-- Create a read-only monitoring user
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'monitoring') THEN
        CREATE ROLE monitoring WITH LOGIN PASSWORD 'monitoring_readonly';
    END IF;
END
$$;

GRANT CONNECT ON DATABASE copytrade TO monitoring;
GRANT USAGE ON SCHEMA public TO monitoring;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO monitoring;
