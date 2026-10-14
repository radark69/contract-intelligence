-- Initialize pgvector and create enum types if needed
-- This runs once on first container start

CREATE EXTENSION IF NOT EXISTS vector;

-- Enum types are created by SQLAlchemy migrations (alembic)
-- This file ensures pgvector is available