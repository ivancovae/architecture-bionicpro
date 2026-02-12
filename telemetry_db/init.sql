-- Скрипт инициализации PostgreSQL для работы с Debezium
-- Выполняется автоматически при первом запуске контейнера

-- Создаём пользователя для Debezium с правами репликации
CREATE USER debezium_user WITH PASSWORD 'debezium_password' REPLICATION;

-- Даём права на использование базы данных
GRANT CONNECT ON DATABASE telemetry_db TO debezium_user;

-- Даём права на использование схемы public
GRANT USAGE ON SCHEMA public TO debezium_user;

-- Даём права на чтение всех таблиц в схеме public
GRANT SELECT ON ALL TABLES IN SCHEMA public TO debezium_user;

-- Даём права на чтение будущих таблиц в схеме public
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO debezium_user;

-- Создаём публикацию для логической репликации (для всех таблиц)
-- Это необходимо для работы Debezium с PostgreSQL
CREATE PUBLICATION telemetry_debezium_publication FOR ALL TABLES;
