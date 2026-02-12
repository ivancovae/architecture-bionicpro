#!/bin/bash
# Скрипт инициализации Debezium-коннекторов
# Ожидает готовности Kafka Connect и создаёт коннекторы

set -e

DEBEZIUM_URL="http://localhost:8083"
MAX_ATTEMPTS=60
WAIT_SECONDS=2

# Список конфигураций коннекторов
CONNECTOR_CONFIGS=(
    "/tmp/crm-connector-config.json"
    "/tmp/telemetry-connector-config.json"
)

echo "=========================================="
echo "Инициализация Debezium-коннекторов"
echo "=========================================="

# Ожидание готовности Kafka Connect
echo "⏳ Ожидание готовности Kafka Connect..."
for i in $(seq 1 $MAX_ATTEMPTS); do
    if curl -sf "${DEBEZIUM_URL}/" > /dev/null 2>&1; then
        echo "✓ Kafka Connect готов (попытка $i)"
        break
    fi
    
    if [ $i -eq $MAX_ATTEMPTS ]; then
        echo "✗ Kafka Connect не запустился за отведённое время"
        exit 1
    fi
    
    echo "  Ожидание... (попытка $i/$MAX_ATTEMPTS)"
    sleep $WAIT_SECONDS
done

# Функция для инициализации одного коннектора
init_connector() {
    local CONNECTOR_CONFIG="$1"
    local CONNECTOR_NAME=$(jq -r '.name' "$CONNECTOR_CONFIG")
    
    echo ""
    echo "=========================================="
    echo "Инициализация коннектора: $CONNECTOR_NAME"
    echo "=========================================="
    
    # Проверка существования коннектора
    echo "Проверка существования коннектора '$CONNECTOR_NAME'..."
    if curl -sf "${DEBEZIUM_URL}/connectors/${CONNECTOR_NAME}" > /dev/null 2>&1; then
        echo "⚠ Коннектор уже существует. Удаляем старый коннектор..."
        
        if curl -sf -X DELETE "${DEBEZIUM_URL}/connectors/${CONNECTOR_NAME}"; then
            echo "✓ Старый коннектор удалён"
            sleep 3
        else
            echo "✗ Не удалось удалить старый коннектор"
            return 1
        fi
    fi
    
    # Создание коннектора
    echo ""
    echo "Создание Debezium-коннектора..."
    RESPONSE=$(curl -sf -X POST \
        -H "Content-Type: application/json" \
        --data @"${CONNECTOR_CONFIG}" \
        "${DEBEZIUM_URL}/connectors" 2>&1)
    
    if [ $? -eq 0 ]; then
        echo "✓ Коннектор создан успешно"
        echo ""
        echo "Конфигурация коннектора:"
        echo "$RESPONSE" | jq '.' 2>/dev/null || echo "$RESPONSE"
    else
        echo "✗ Ошибка при создании коннектора"
        echo "Ответ: $RESPONSE"
        return 1
    fi
    
    # Ожидание запуска коннектора
    echo ""
    echo "⏳ Ожидание запуска коннектора..."
    sleep 5
    
    # Проверка статуса коннектора
    echo "Проверка статуса коннектора..."
    for i in $(seq 1 20); do
        STATUS=$(curl -sf "${DEBEZIUM_URL}/connectors/${CONNECTOR_NAME}/status" 2>&1)
        
        if [ $? -eq 0 ]; then
            CONNECTOR_STATE=$(echo "$STATUS" | jq -r '.connector.state' 2>/dev/null)
            
            if [ "$CONNECTOR_STATE" = "RUNNING" ]; then
                echo "✓ Коннектор работает (статус: RUNNING)"
                echo ""
                echo "Полный статус:"
                echo "$STATUS" | jq '.' 2>/dev/null || echo "$STATUS"
                return 0
            elif [ "$CONNECTOR_STATE" = "FAILED" ]; then
                echo "✗ Коннектор в статусе FAILED"
                echo "Статус:"
                echo "$STATUS" | jq '.' 2>/dev/null || echo "$STATUS"
                return 1
            else
                echo "  Статус коннектора: $CONNECTOR_STATE (попытка $i/20)"
            fi
        else
            echo "  Не удалось получить статус (попытка $i/20)"
        fi
        
        sleep 2
    done
    
    echo "✗ Коннектор не перешёл в статус RUNNING за отведённое время"
    return 1
}

# Инициализация всех коннекторов
FAILED=0
for CONNECTOR_CONFIG in "${CONNECTOR_CONFIGS[@]}"; do
    if ! init_connector "$CONNECTOR_CONFIG"; then
        FAILED=$((FAILED + 1))
    fi
done

echo ""
echo "=========================================="
if [ $FAILED -eq 0 ]; then
    echo "✓ Все коннекторы инициализированы успешно!"
    echo "=========================================="
    echo ""
    echo "Kafka-топики:"
    echo "  - crm.public.users (изменения в таблице users)"
    echo "  - telemetry.public.telemetry_events (изменения в таблице telemetry_events)"
    echo ""
    echo "Веб-интерфейс Kafdrop: http://localhost:9100"
    echo ""
    exit 0
else
    echo "✗ Не удалось инициализировать $FAILED коннектор(ов)"
    echo "=========================================="
    exit 1
fi
