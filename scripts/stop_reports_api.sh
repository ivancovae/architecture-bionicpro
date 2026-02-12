#!/bin/bash
# Скрипт для остановки reports_api

echo "Останавливаем reports_api..."
pkill -f "reports_backend.main"
echo "✓ reports_api остановлен"
