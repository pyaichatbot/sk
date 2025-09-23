-- ============================================================================
-- microservices/docker/init-db.sql
-- ============================================================================
-- Database initialization script for microservices architecture
-- Creates service-specific users, databases, and basic permissions

-- Create service-specific users
DO $$
BEGIN
    -- API Gateway Service User
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'api_gateway_user') THEN
        CREATE ROLE api_gateway_user WITH LOGIN PASSWORD 'api_gateway_password';
    END IF;
    
    -- Orchestration Service User
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'orchestration_user') THEN
        CREATE ROLE orchestration_user WITH LOGIN PASSWORD 'orchestration_password';
    END IF;
    
    -- RAG Agent Service User
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'rag_agent_user') THEN
        CREATE ROLE rag_agent_user WITH LOGIN PASSWORD 'rag_agent_password';
    END IF;
    
    -- Search Agent Service User
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'search_agent_user') THEN
        CREATE ROLE search_agent_user WITH LOGIN PASSWORD 'search_agent_password';
    END IF;
    
    -- JIRA Agent Service User
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'jira_agent_user') THEN
        CREATE ROLE jira_agent_user WITH LOGIN PASSWORD 'jira_agent_password';
    END IF;
    
    -- LLM Agent Service User
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'llm_agent_user') THEN
        CREATE ROLE llm_agent_user WITH LOGIN PASSWORD 'llm_agent_password';
    END IF;
    
    -- Shared Infrastructure User (for cross-service operations)
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'shared_infrastructure_user') THEN
        CREATE ROLE shared_infrastructure_user WITH LOGIN PASSWORD 'shared_infrastructure_password';
    END IF;
END
$$;

-- Create service-specific schemas
CREATE SCHEMA IF NOT EXISTS api_gateway;
CREATE SCHEMA IF NOT EXISTS orchestration;
CREATE SCHEMA IF NOT EXISTS rag_agent;
CREATE SCHEMA IF NOT EXISTS search_agent;
CREATE SCHEMA IF NOT EXISTS jira_agent;
CREATE SCHEMA IF NOT EXISTS llm_agent;
CREATE SCHEMA IF NOT EXISTS shared_infrastructure;

-- Grant schema permissions to service users
GRANT USAGE ON SCHEMA api_gateway TO api_gateway_user;
GRANT CREATE ON SCHEMA api_gateway TO api_gateway_user;
GRANT ALL ON ALL TABLES IN SCHEMA api_gateway TO api_gateway_user;
GRANT ALL ON ALL SEQUENCES IN SCHEMA api_gateway TO api_gateway_user;

GRANT USAGE ON SCHEMA orchestration TO orchestration_user;
GRANT CREATE ON SCHEMA orchestration TO orchestration_user;
GRANT ALL ON ALL TABLES IN SCHEMA orchestration TO orchestration_user;
GRANT ALL ON ALL SEQUENCES IN SCHEMA orchestration TO orchestration_user;

GRANT USAGE ON SCHEMA rag_agent TO rag_agent_user;
GRANT CREATE ON SCHEMA rag_agent TO rag_agent_user;
GRANT ALL ON ALL TABLES IN SCHEMA rag_agent TO rag_agent_user;
GRANT ALL ON ALL SEQUENCES IN SCHEMA rag_agent TO rag_agent_user;

GRANT USAGE ON SCHEMA search_agent TO search_agent_user;
GRANT CREATE ON SCHEMA search_agent TO search_agent_user;
GRANT ALL ON ALL TABLES IN SCHEMA search_agent TO search_agent_user;
GRANT ALL ON ALL SEQUENCES IN SCHEMA search_agent TO search_agent_user;

GRANT USAGE ON SCHEMA jira_agent TO jira_agent_user;
GRANT CREATE ON SCHEMA jira_agent TO jira_agent_user;
GRANT ALL ON ALL TABLES IN SCHEMA jira_agent TO jira_agent_user;
GRANT ALL ON ALL SEQUENCES IN SCHEMA jira_agent TO jira_agent_user;

GRANT USAGE ON SCHEMA llm_agent TO llm_agent_user;
GRANT CREATE ON SCHEMA llm_agent TO llm_agent_user;
GRANT ALL ON ALL TABLES IN SCHEMA llm_agent TO llm_agent_user;
GRANT ALL ON ALL SEQUENCES IN SCHEMA llm_agent TO llm_agent_user;

GRANT USAGE ON SCHEMA shared_infrastructure TO shared_infrastructure_user;
GRANT CREATE ON SCHEMA shared_infrastructure TO shared_infrastructure_user;
GRANT ALL ON ALL TABLES IN SCHEMA shared_infrastructure TO shared_infrastructure_user;
GRANT ALL ON ALL SEQUENCES IN SCHEMA shared_infrastructure TO shared_infrastructure_user;

-- Grant cross-schema read permissions for service discovery and monitoring
GRANT USAGE ON SCHEMA api_gateway TO shared_infrastructure_user;
GRANT USAGE ON SCHEMA orchestration TO shared_infrastructure_user;
GRANT USAGE ON SCHEMA rag_agent TO shared_infrastructure_user;
GRANT USAGE ON SCHEMA search_agent TO shared_infrastructure_user;
GRANT USAGE ON SCHEMA jira_agent TO shared_infrastructure_user;
GRANT USAGE ON SCHEMA llm_agent TO shared_infrastructure_user;

-- Create shared infrastructure tables
CREATE TABLE IF NOT EXISTS shared_infrastructure.schema_migrations (
    service_name VARCHAR(50) NOT NULL,
    version VARCHAR(20) NOT NULL,
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (service_name, version)
);

CREATE TABLE IF NOT EXISTS shared_infrastructure.service_health (
    service_name VARCHAR(50) NOT NULL,
    status VARCHAR(20) NOT NULL,
    last_check TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    details JSONB,
    PRIMARY KEY (service_name)
);

CREATE TABLE IF NOT EXISTS shared_infrastructure.service_metrics (
    service_name VARCHAR(50) NOT NULL,
    metric_name VARCHAR(100) NOT NULL,
    metric_value NUMERIC NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    metadata JSONB
);

-- Create indexes for shared infrastructure
CREATE INDEX IF NOT EXISTS idx_service_health_last_check ON shared_infrastructure.service_health(last_check);
CREATE INDEX IF NOT EXISTS idx_service_metrics_timestamp ON shared_infrastructure.service_metrics(timestamp);
CREATE INDEX IF NOT EXISTS idx_service_metrics_service ON shared_infrastructure.service_metrics(service_name, metric_name);

-- Grant permissions on shared infrastructure tables
GRANT ALL ON ALL TABLES IN SCHEMA shared_infrastructure TO shared_infrastructure_user;
GRANT ALL ON ALL SEQUENCES IN SCHEMA shared_infrastructure TO shared_infrastructure_user;

-- Grant read permissions to all service users for shared infrastructure
GRANT SELECT ON shared_infrastructure.service_health TO api_gateway_user, orchestration_user, rag_agent_user, search_agent_user, jira_agent_user, llm_agent_user;
GRANT SELECT ON shared_infrastructure.service_metrics TO api_gateway_user, orchestration_user, rag_agent_user, search_agent_user, jira_agent_user, llm_agent_user;

-- Create extension for UUID generation
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Create extension for vector operations (for RAG agent)
CREATE EXTENSION IF NOT EXISTS vector;

-- Create extension for JSON operations
CREATE EXTENSION IF NOT EXISTS "btree_gin";

-- Set default privileges for future objects
ALTER DEFAULT PRIVILEGES IN SCHEMA api_gateway GRANT ALL ON TABLES TO api_gateway_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA api_gateway GRANT ALL ON SEQUENCES TO api_gateway_user;

ALTER DEFAULT PRIVILEGES IN SCHEMA orchestration GRANT ALL ON TABLES TO orchestration_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA orchestration GRANT ALL ON SEQUENCES TO orchestration_user;

ALTER DEFAULT PRIVILEGES IN SCHEMA rag_agent GRANT ALL ON TABLES TO rag_agent_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA rag_agent GRANT ALL ON SEQUENCES TO rag_agent_user;

ALTER DEFAULT PRIVILEGES IN SCHEMA search_agent GRANT ALL ON TABLES TO search_agent_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA search_agent GRANT ALL ON SEQUENCES TO search_agent_user;

ALTER DEFAULT PRIVILEGES IN SCHEMA jira_agent GRANT ALL ON TABLES TO jira_agent_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA jira_agent GRANT ALL ON SEQUENCES TO jira_agent_user;

ALTER DEFAULT PRIVILEGES IN SCHEMA llm_agent GRANT ALL ON TABLES TO llm_agent_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA llm_agent GRANT ALL ON SEQUENCES TO llm_agent_user;

ALTER DEFAULT PRIVILEGES IN SCHEMA shared_infrastructure GRANT ALL ON TABLES TO shared_infrastructure_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA shared_infrastructure GRANT ALL ON SEQUENCES TO shared_infrastructure_user;

-- Insert initial service health records
INSERT INTO shared_infrastructure.service_health (service_name, status, details) VALUES
    ('api_gateway', 'unknown', '{"initialized": true}'),
    ('orchestration', 'unknown', '{"initialized": true}'),
    ('rag_agent', 'unknown', '{"initialized": true}'),
    ('search_agent', 'unknown', '{"initialized": true}'),
    ('jira_agent', 'unknown', '{"initialized": true}'),
    ('llm_agent', 'unknown', '{"initialized": true}')
ON CONFLICT (service_name) DO NOTHING;

-- Create a function to update service health
CREATE OR REPLACE FUNCTION shared_infrastructure.update_service_health(
    p_service_name VARCHAR(50),
    p_status VARCHAR(20),
    p_details JSONB DEFAULT NULL
) RETURNS VOID AS $$
BEGIN
    INSERT INTO shared_infrastructure.service_health (service_name, status, last_check, details)
    VALUES (p_service_name, p_status, CURRENT_TIMESTAMP, p_details)
    ON CONFLICT (service_name) 
    DO UPDATE SET 
        status = EXCLUDED.status,
        last_check = EXCLUDED.last_check,
        details = COALESCE(EXCLUDED.details, service_health.details);
END;
$$ LANGUAGE plpgsql;

-- Create a function to record service metrics
CREATE OR REPLACE FUNCTION shared_infrastructure.record_service_metric(
    p_service_name VARCHAR(50),
    p_metric_name VARCHAR(100),
    p_metric_value NUMERIC,
    p_metadata JSONB DEFAULT NULL
) RETURNS VOID AS $$
BEGIN
    INSERT INTO shared_infrastructure.service_metrics (service_name, metric_name, metric_value, metadata)
    VALUES (p_service_name, p_metric_name, p_metric_value, p_metadata);
END;
$$ LANGUAGE plpgsql;

-- Grant execute permissions on shared functions
GRANT EXECUTE ON FUNCTION shared_infrastructure.update_service_health TO api_gateway_user, orchestration_user, rag_agent_user, search_agent_user, jira_agent_user, llm_agent_user;
GRANT EXECUTE ON FUNCTION shared_infrastructure.record_service_metric TO api_gateway_user, orchestration_user, rag_agent_user, search_agent_user, jira_agent_user, llm_agent_user;

-- Create a view for service overview
CREATE OR REPLACE VIEW shared_infrastructure.service_overview AS
SELECT 
    sh.service_name,
    sh.status,
    sh.last_check,
    sh.details,
    COUNT(sm.metric_name) as metric_count,
    MAX(sm.timestamp) as last_metric_update
FROM shared_infrastructure.service_health sh
LEFT JOIN shared_infrastructure.service_metrics sm ON sh.service_name = sm.service_name
GROUP BY sh.service_name, sh.status, sh.last_check, sh.details;

-- Grant read permissions on the view
GRANT SELECT ON shared_infrastructure.service_overview TO api_gateway_user, orchestration_user, rag_agent_user, search_agent_user, jira_agent_user, llm_agent_user;

-- Log successful initialization
INSERT INTO shared_infrastructure.service_metrics (service_name, metric_name, metric_value, metadata)
VALUES ('database', 'initialization_completed', 1, '{"timestamp": "' || CURRENT_TIMESTAMP || '", "version": "1.0.0"}');
