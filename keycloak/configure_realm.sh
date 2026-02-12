#!/bin/bash

# Скрипт для настройки Frontend URL в Keycloak realm через Admin REST API

set -e

echo "Ожидание готовности Keycloak..."
for i in {1..30}; do
  if curl -s -f http://localhost:8080/realms/reports-realm > /dev/null 2>&1; then
    echo "✓ Keycloak готов (попытка $i)"
    break
  fi
  if [ $i -eq 30 ]; then
    echo "✗ Keycloak не запустился за 60 секунд"
    exit 1
  fi
  echo "Ожидание Keycloak... (попытка $i/30)"
  sleep 2
done

echo "Получение admin access token..."
ADMIN_TOKEN=$(curl -s -X POST "http://localhost:8080/realms/master/protocol/openid-connect/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin" \
  -d "password=admin" \
  -d "grant_type=password" \
  -d "client_id=admin-cli" | jq -r '.access_token')

if [ -z "$ADMIN_TOKEN" ] || [ "$ADMIN_TOKEN" = "null" ]; then
  echo "✗ Не удалось получить admin token"
  exit 1
fi

echo "✓ Admin token получен"

echo "Настройка Frontend URL для reports-realm..."
curl -s -X PUT "http://localhost:8080/admin/realms/reports-realm" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "realm": "reports-realm",
    "attributes": {
      "frontendUrl": "http://localhost:8080"
    }
  }'

echo ""
echo "✓ Frontend URL настроен для reports-realm"
echo "✓ Keycloak realm настроен успешно"
