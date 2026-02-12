#!/bin/bash
# Скрипт для инициализации всех баз данных проекта

set -e  # Прерывать выполнение при ошибке

echo "=========================================="
echo "Инициализация баз данных"
echo "=========================================="

# Цвета для вывода
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Функция для проверки доступности HTTP-сервиса
wait_for_http() {
    local url=$1
    local max_attempts=30
    local attempt=1
    
    echo -e "${YELLOW}Ожидание доступности $url...${NC}"
    
    while [ $attempt -le $max_attempts ]; do
        if curl -s -f "$url" > /dev/null 2>&1; then
            echo -e "${GREEN}✓ Сервис доступен (попытка $attempt)${NC}"
            return 0
        fi
        echo "Ожидание... (попытка $attempt/$max_attempts)"
        sleep 2
        attempt=$((attempt + 1))
    done
    
    echo -e "${RED}✗ Сервис не запустился за $((max_attempts * 2)) секунд${NC}"
    return 1
}

# Функция для остановки фоновых процессов при выходе
cleanup() {
    echo -e "\n${YELLOW}Остановка API-сервисов...${NC}"
    if [ ! -z "$CRM_PID" ]; then
        kill $CRM_PID 2>/dev/null || true
    fi
    if [ ! -z "$TELEMETRY_PID" ]; then
        kill $TELEMETRY_PID 2>/dev/null || true
    fi
    echo -e "${GREEN}✓ API-сервисы остановлены${NC}"
}

trap cleanup EXIT

# 1. Запуск CRM API для создания таблиц и загрузки данных
echo -e "\n${YELLOW}1. Запуск CRM API...${NC}"
uv run uvicorn crm_api.main:app --host 0.0.0.0 --port 8001 > /tmp/crm_api.log 2>&1 &
CRM_PID=$!
echo -e "${GREEN}✓ CRM API запущен (PID: $CRM_PID)${NC}"

# Ожидание запуска CRM API
wait_for_http "http://localhost:8001/health"

# Загрузка данных в CRM БД
echo -e "\n${YELLOW}2. Загрузка данных в CRM БД...${NC}"
response=$(curl -s -X POST http://localhost:8001/populate_base)
echo "Ответ: $response"
echo -e "${GREEN}✓ Данные CRM загружены${NC}"

# 2. Запуск Telemetry API для создания таблиц и загрузки данных
echo -e "\n${YELLOW}3. Запуск Telemetry API...${NC}"
uv run uvicorn telemetry_api.main:app --host 0.0.0.0 --port 8002 > /tmp/telemetry_api.log 2>&1 &
TELEMETRY_PID=$!
echo -e "${GREEN}✓ Telemetry API запущен (PID: $TELEMETRY_PID)${NC}"

# Ожидание запуска Telemetry API
wait_for_http "http://localhost:8002/health"

# Загрузка данных в Telemetry БД
echo -e "\n${YELLOW}4. Загрузка данных в Telemetry БД...${NC}"
response=$(curl -s -X POST http://localhost:8002/populate_base)
echo "Ответ: $response"
echo -e "${GREEN}✓ Данные Telemetry загружены${NC}"

# 3. Импорт данных в ClickHouse OLAP БД
echo -e "\n${YELLOW}5. Импорт данных в ClickHouse OLAP БД...${NC}"
uv run python -m dags.import_olap_data
echo -e "${GREEN}✓ Данные импортированы в ClickHouse${NC}"

echo -e "\n${GREEN}=========================================="
echo "Инициализация завершена успешно!"
echo "==========================================${NC}"
