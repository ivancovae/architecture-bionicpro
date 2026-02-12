#!/bin/bash
# Скрипт для запуска auth_proxy из локального uv

# Переходим в корневую директорию проекта
cd "$(dirname "$0")/.." || exit 1

echo "Запускаем auth_proxy..."
echo "Используем uv для запуска Python модуля"

# Запускаем auth_proxy через uv
uv run python -m auth_proxy.main &

echo "✓ auth_proxy запущен (PID: $!)"
echo "  Доступен на http://0.0.0.0:3000"
