#!/bin/bash

# Скрипт для настройки Debezium-коннекторов для crm_db и telemetry_db

set -e

echo "========================================="
echo "Настройка Debezium-коннекторов"
echo "========================================="

# Ожидаем запуска Debezium Kafka Connect
echo "Ожидание запуска Debezium Kafka Connect..."
for i in {1..60}; do
  if curl -s -f http://localhost:8083/ > /dev/null 2>&1; then
    echo "✓ Debezium Kafka Connect начал отвечать (попытка $i)"
    sleep 5
    echo "✓ Debezium Kafka Connect готов к работе"
    break
  fi
  echo "Ожидание Debezium... (попытка $i/60)"
  sleep 2
done

# Проверяем, что Debezium доступен
if ! curl -s -f http://localhost:8083/ > /dev/null 2>&1; then
  echo "✗ Debezium Kafka Connect не запустился"
  exit 1
fi

echo ""
echo "========================================="
echo "Создание коннектора для CRM DB"
echo "========================================="

# Создаём коннектор для crm_db (таблица users)
curl -i -X POST -H "Accept:application/json" -H "Content-Type:application/json" \
  http://localhost:8083/connectors/ -d '{
  "name": "crm-connector",
  "config": {
    "connector.class": "io.debezium.connector.postgresql.PostgresConnector",
    "database.hostname": "crm-db",
    "database.port": "5432",
    "database.user": "crm_user",
    "database.password": "crm_password",
    "database.dbname": "crm_db",
    "database.server.name": "crm",
    "table.include.list": "public.users",
    "topic.prefix": "crm",
    "plugin.name": "pgoutput",
    "slot.name": "debezium_crm",
    "publication.name": "dbz_publication_crm",
    "publication.autocreate.mode": "filtered",
    "snapshot.mode": "initial"
  }
}'

echo ""
echo ""
echo "========================================="
echo "Создание коннектора для Telemetry DB"
echo "========================================="

# Создаём коннектор для telemetry_db (таблица telemetry_events)
curl -i -X POST -H "Accept:application/json" -H "Content-Type:application/json" \
  http://localhost:8083/connectors/ -d '{
  "name": "telemetry-connector",
  "config": {
    "connector.class": "io.debezium.connector.postgresql.PostgresConnector",
    "database.hostname": "telemetry-db",
    "database.port": "5432",
    "database.user": "telemetry_user",
    "database.password": "telemetry_password",
    "database.dbname": "telemetry_db",
    "database.server.name": "telemetry",
    "table.include.list": "public.telemetry_events",
    "topic.prefix": "telemetry",
    "plugin.name": "pgoutput",
    "slot.name": "debezium_telemetry",
    "publication.name": "dbz_publication_telemetry",
    "publication.autocreate.mode": "filtered",
    "snapshot.mode": "initial"
  }
}'

echo ""
echo ""
echo "========================================="
echo "Проверка статуса коннекторов"
echo "========================================="

# Проверяем статус коннекторов
sleep 3
echo ""
echo "Статус CRM-коннектора:"
curl -s http://localhost:8083/connectors/crm-connector/status | jq '.'

echo ""
echo "Статус Telemetry-коннектора:"
curl -s http://localhost:8083/connectors/telemetry-connector/status | jq '.'

echo ""
echo "========================================="
echo "✓ Debezium-коннекторы настроены"
echo "========================================="
echo ""
echo "Kafka-топики:"
echo "  - crm.public.users (изменения в таблице users)"
echo "  - telemetry.public.telemetry_events (изменения в таблице telemetry_events)"
echo ""
echo "Веб-интерфейс Kafdrop: http://localhost:9100"
echo ""
