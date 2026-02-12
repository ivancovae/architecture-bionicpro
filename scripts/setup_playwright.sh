#!/bin/bash
# Скрипт для установки Playwright браузеров с сохранением в проекте

# Переходим в корневую директорию проекта
cd "$(dirname "$0")/.." || exit 1

echo "Устанавливаем зависимости Python через uv..."
uv sync

echo ""
echo "Устанавливаем Playwright браузеры..."
echo "Браузеры будут установлены в ~/.cache/ms-playwright"
echo "Это позволит использовать их после перезагрузки системы"

# Устанавливаем браузеры Playwright
uv run playwright install chromium

echo ""
echo "✓ Playwright настроен и готов к использованию"
echo "  Браузеры сохранены в ~/.cache/ms-playwright"
echo "  При следующем запуске тестов установка не потребуется"
