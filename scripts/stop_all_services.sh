#!/bin/bash
# Скрипт для остановки всех сервисов

# Переходим в корневую директорию проекта
cd "$(dirname "$0")/.." || exit 1

echo "=== Остановка всех сервисов ==="
echo ""

echo "1. Останавливаем reports_api..."
pkill -f "reports_backend.main"
echo "✓ reports_api остановлен"

echo ""
echo "2. Останавливаем auth_proxy..."
pkill -f "auth_proxy.main"
echo "✓ auth_proxy остановлен"

echo ""
echo "3. Останавливаем фронтенд..."
pkill -f "vite"
echo "✓ Фронтенд остановлен"

