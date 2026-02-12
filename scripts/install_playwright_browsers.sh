#!/bin/bash
# Скрипт для установки браузеров Playwright
# Используется для подготовки окружения к запуску E2E тестов

set -e  # Останавливаем выполнение при ошибке

echo "=== Установка браузеров Playwright ==="

# Проверяем, установлен ли playwright
if ! uv run python -c "import playwright" 2>/dev/null; then
    echo "✗ Playwright не установлен"
    echo "Установите зависимости: uv sync"
    exit 1
fi

echo "✓ Playwright установлен"

# Устанавливаем браузеры (только chromium для экономии места)
echo "Устанавливаем браузер Chromium..."
uv run playwright install chromium

echo "✓ Браузер Chromium установлен"
echo "=== Установка завершена ==="
