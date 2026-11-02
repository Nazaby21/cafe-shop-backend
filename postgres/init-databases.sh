#!/bin/bash
set -e

# Creates the isolated databases for each microservice upon initial PostgreSQL container startup
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    SELECT 'CREATE DATABASE user_service_db'
    WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'user_service_db')\gexec

    SELECT 'CREATE DATABASE operation_service_db'
    WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'operation_service_db')\gexec

    SELECT 'CREATE DATABASE report_service_db'
    WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'report_service_db')\gexec
EOSQL

echo "[INIT] PostgreSQL databases initialized: user_service_db, operation_service_db, report_service_db."
