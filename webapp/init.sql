-- BioAgent Database Initialization Script
-- This script runs when the PostgreSQL container is first created

-- Enable pgvector extension for future embedding support
CREATE EXTENSION IF NOT EXISTS vector;

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Create indexes for common queries (these will be created by SQLAlchemy,
-- but having them here ensures they exist even if alembic migrations haven't run)

-- Note: The actual tables are created by SQLAlchemy's init_db() function
-- This script sets up extensions and any database-level configuration

-- Grant permissions (adjust as needed for your security requirements)
-- GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO bioagent;
-- GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO bioagent;

-- Set default search path
-- SET search_path TO public;

-- Log that initialization is complete
DO $$
BEGIN
    RAISE NOTICE 'BioAgent database initialized successfully';
END $$;
