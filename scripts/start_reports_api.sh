#!/bin/bash
# Скрипт для запуска reports_api из локального uv

# Переходим в корневую директорию проекта
cd "$(dirname "$0")/.." || exit 1

echo "Запускаем reports_api..."
echo "Используем uv для запуска Python модуля"

# Запускаем reports_api через uv
uv run python -m reports_backend.main &

echo "✓ reports_api запущен (PID: $!)"
echo "  Доступен на http://0.0.0.0:3003"
