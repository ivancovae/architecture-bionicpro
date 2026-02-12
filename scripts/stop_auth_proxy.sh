#!/bin/bash
# Скрипт для остановки auth_proxy

echo "Останавливаем auth_proxy..."
pkill -f "auth_proxy.main"
echo "✓ auth_proxy остановлен"
