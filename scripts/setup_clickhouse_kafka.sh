#!/bin/bash

# Скрипт для настройки ClickHouse с Kafka Engine таблицами для чтения из Debezium-топиков

set -e

echo "========================================="
echo "Настройка ClickHouse Kafka Engine"
echo "========================================="

# Параметры подключения к ClickHouse
CLICKHOUSE_HOST="localhost"
CLICKHOUSE_PORT="8123"
CLICKHOUSE_USER="default"
CLICKHOUSE_PASSWORD="clickhouse_password"

# Функция для выполнения SQL-запросов в ClickHouse
clickhouse_query() {
    local query="$1"
    curl -s "http://${CLICKHOUSE_HOST}:${CLICKHOUSE_PORT}/" \
        --user "${CLICKHOUSE_USER}:${CLICKHOUSE_PASSWORD}" \
        --data-binary "${query}"
}

echo ""
echo "Создание базы данных debezium..."
clickhouse_query "CREATE DATABASE IF NOT EXISTS debezium"
echo "✓ База данных debezium создана"

echo ""
echo "========================================="
echo "Настройка таблиц для CRM (users)"
echo "========================================="

# Kafka Engine таблица для чтения из топика crm.public.users
echo "Создание Kafka Engine таблицы для users..."
clickhouse_query "
CREATE TABLE IF NOT EXISTS debezium.users_kafka (
    payload String
) ENGINE = Kafka
SETTINGS
    kafka_broker_list = 'kafka:9092',
    kafka_topic_list = 'crm.public.users',
    kafka_group_name = 'clickhouse_crm_consumer',
    kafka_format = 'JSONAsString',
    kafka_num_consumers = 1,
    kafka_thread_per_consumer = 1,
    kafka_skip_broken_messages = 1000,
    kafka_max_block_size = 1048576
"
echo "✓ Kafka Engine таблица users_kafka создана"

# Materialized View для парсинга JSON и записи в Join таблицу
echo "Создание Materialized View для users..."
clickhouse_query "
CREATE TABLE IF NOT EXISTS debezium.users_join (
    user_id Int32,
    user_uuid String,
    name String,
    email String,
    age Nullable(Int32),
    gender Nullable(String),
    country Nullable(String),
    address Nullable(String),
    phone Nullable(String),
    registered_at DateTime
) ENGINE = Join(ANY, LEFT, user_id)
"
echo "✓ Join таблица users_join создана"

clickhouse_query "
CREATE MATERIALIZED VIEW IF NOT EXISTS debezium.users_mv TO debezium.users_join AS
SELECT
    JSONExtractInt(JSONExtractString(payload, 'after'), 'id') AS user_id,
    JSONExtractString(JSONExtractString(payload, 'after'), 'user_uuid') AS user_uuid,
    JSONExtractString(JSONExtractString(payload, 'after'), 'name') AS name,
    JSONExtractString(JSONExtractString(payload, 'after'), 'email') AS email,
    JSONExtractInt(JSONExtractString(payload, 'after'), 'age') AS age,
    JSONExtractString(JSONExtractString(payload, 'after'), 'gender') AS gender,
    JSONExtractString(JSONExtractString(payload, 'after'), 'country') AS country,
    JSONExtractString(JSONExtractString(payload, 'after'), 'address') AS address,
    JSONExtractString(JSONExtractString(payload, 'after'), 'phone') AS phone,
    fromUnixTimestamp64Micro(JSONExtractInt(JSONExtractString(payload, 'after'), 'registered_at')) AS registered_at
FROM debezium.users_kafka
WHERE JSONExtractString(payload, 'op') IN ('c', 'u', 'r')
"
echo "✓ Materialized View users_mv создана"

echo ""
echo "========================================="
echo "Настройка таблиц для Telemetry (events)"
echo "========================================="

# Kafka Engine таблица для чтения из топика telemetry.public.telemetry_events
echo "Создание Kafka Engine таблицы для telemetry_events..."
clickhouse_query "
CREATE TABLE IF NOT EXISTS debezium.telemetry_events_kafka (
    payload String
) ENGINE = Kafka
SETTINGS
    kafka_broker_list = 'kafka:9092',
    kafka_topic_list = 'telemetry.public.telemetry_events',
    kafka_group_name = 'clickhouse_telemetry_consumer',
    kafka_format = 'JSONAsString',
    kafka_num_consumers = 1,
    kafka_thread_per_consumer = 1,
    kafka_skip_broken_messages = 1000,
    kafka_max_block_size = 1048576
"
echo "✓ Kafka Engine таблица telemetry_events_kafka создана"

# ReplacingMergeTree таблица для хранения событий телеметрии с дедупликацией по event_uuid
echo "Создание ReplacingMergeTree таблицы для telemetry_events..."
clickhouse_query "
CREATE TABLE IF NOT EXISTS debezium.telemetry_events_merge (
    id Int64,
    event_uuid String,
    user_id Int32,
    prosthesis_type String,
    muscle_group String,
    signal_frequency Int32,
    signal_duration Int32,
    signal_amplitude Float64,
    created_ts DateTime,
    saved_ts DateTime
) ENGINE = ReplacingMergeTree(saved_ts)
PARTITION BY (toYear(created_ts), toMonth(created_ts))
ORDER BY (event_uuid, user_id, created_ts)
"
echo "✓ ReplacingMergeTree таблица telemetry_events_merge создана"

# Materialized View для парсинга JSON и записи в MergeTree
echo "Создание Materialized View для telemetry_events..."
clickhouse_query "
CREATE MATERIALIZED VIEW IF NOT EXISTS debezium.telemetry_events_mv TO debezium.telemetry_events_merge AS
SELECT
    JSONExtractInt(JSONExtractString(payload, 'after'), 'id') AS id,
    JSONExtractString(JSONExtractString(payload, 'after'), 'event_uuid') AS event_uuid,
    JSONExtractInt(JSONExtractString(payload, 'after'), 'user_id') AS user_id,
    JSONExtractString(JSONExtractString(payload, 'after'), 'prosthesis_type') AS prosthesis_type,
    JSONExtractString(JSONExtractString(payload, 'after'), 'muscle_group') AS muscle_group,
    JSONExtractInt(JSONExtractString(payload, 'after'), 'signal_frequency') AS signal_frequency,
    JSONExtractInt(JSONExtractString(payload, 'after'), 'signal_duration') AS signal_duration,
    JSONExtractFloat(JSONExtractString(payload, 'after'), 'signal_amplitude') AS signal_amplitude,
    fromUnixTimestamp64Micro(JSONExtractInt(JSONExtractString(payload, 'after'), 'created_ts')) AS created_ts,
    fromUnixTimestamp64Micro(JSONExtractInt(JSONExtractString(payload, 'after'), 'saved_ts')) AS saved_ts
FROM debezium.telemetry_events_kafka
WHERE JSONExtractString(payload, 'op') IN ('c', 'u', 'r')
"
echo "✓ Materialized View telemetry_events_mv создана"

echo ""
echo "========================================="
echo "✓ ClickHouse Kafka Engine настроен"
echo "========================================="
echo ""
echo "Созданные таблицы в схеме debezium:"
echo "  - users_kafka (Kafka Engine)"
echo "  - users_join (Join Engine)"
echo "  - users_mv (Materialized View)"
echo "  - telemetry_events_kafka (Kafka Engine)"
echo "  - telemetry_events_merge (MergeTree)"
echo "  - telemetry_events_mv (Materialized View)"
echo ""
echo "Проверка данных:"
echo "  SELECT * FROM debezium.users_join LIMIT 10;"
echo "  SELECT * FROM debezium.telemetry_events_merge LIMIT 10;"
echo ""
