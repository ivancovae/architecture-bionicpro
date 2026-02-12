#!/bin/bash
# Обёртка для docker-entrypoint Debezium Connect
# Запускает оригинальный entrypoint и инициализирует коннекторы

set -e

echo "=========================================="
echo "Запуск Debezium Connect с инициализацией"
echo "=========================================="

# Запускаем оригинальный docker-entrypoint в фоне
/docker-entrypoint.sh "$@" &
KAFKA_CONNECT_PID=$!

# Функция для корректной остановки при получении сигнала
cleanup() {
    echo "Получен сигнал остановки, завершаем Kafka Connect..."
    kill -TERM $KAFKA_CONNECT_PID 2>/dev/null || true
    wait $KAFKA_CONNECT_PID
    exit 0
}

trap cleanup SIGTERM SIGINT

# Ожидаем инициализацию коннекторов
echo "Ожидание запуска Kafka Connect перед инициализацией коннекторов..."
sleep 10

# Запускаем инициализацию коннекторов
if /usr/local/bin/init-connector.sh; then
    echo "✓ Коннекторы инициализированы успешно"
else
    echo "✗ Ошибка инициализации коннекторов"
    kill -TERM $KAFKA_CONNECT_PID 2>/dev/null || true
    exit 1
fi

# Ждём завершения основного процесса
wait $KAFKA_CONNECT_PID
