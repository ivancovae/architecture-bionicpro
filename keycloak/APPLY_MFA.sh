#!/bin/bash

# Скрипт для применения настроек MFA в Keycloak

set -e

echo "=========================================="
echo "Применение настроек MFA в Keycloak"
echo "=========================================="

echo ""
echo "1. Остановка Keycloak..."
docker compose stop keycloak

echo ""
echo "2. Удаление старого контейнера Keycloak..."
docker compose rm -f keycloak

echo ""
echo "3. Удаление данных Keycloak (для чистого импорта)..."
docker volume rm architecture-bionicpro_keycloak_data 2>/dev/null || echo "Volume не существует, пропускаем"

echo ""
echo "4. Запуск Keycloak с новыми настройками..."
docker compose up -d keycloak

echo ""
echo "5. Ожидание запуска Keycloak..."
for i in {1..30}; do
  if docker exec keycloak curl -s -f http://localhost:8080/realms/reports-realm > /dev/null 2>&1; then
    echo "✓ Keycloak запущен (попытка $i)"
    sleep 5
    echo "✓ Keycloak готов к работе"
    break
  fi
  echo "Ожидание Keycloak... (попытка $i/30)"
  sleep 2
done

echo ""
echo "=========================================="
echo "✓ MFA успешно применён!"
echo "=========================================="
echo ""
echo "Следующие шаги:"
echo "1. Откройте http://localhost:3000"
echo "2. Войдите под любым пользователем (например, prosthetic1:prosthetic123)"
echo "3. Вам будет предложено настроить OTP"
echo "4. Используйте Google Authenticator или другое приложение для сканирования QR-кода"
echo "5. Введите 6-значный код из приложения"
echo ""
echo "Документация: keycloak/MFA_SETUP.md"
echo ""
