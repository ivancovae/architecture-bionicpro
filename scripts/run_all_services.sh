#!/bin/bash
# Скрипт для запуска всех сервисов (docker-compose + reports_api + auth_proxy + frontend)

# Переходим в корневую директорию проекта
cd "$(dirname "$0")/.." || exit 1

echo "=== Запуск всех сервисов ==="
echo ""

# Останавливаем старые процессы
echo "1. Останавливаем старые процессы..."
pkill -f "reports_backend.main" 2>/dev/null
pkill -f "auth_proxy.main" 2>/dev/null
pkill -f "vite" 2>/dev/null

# Останавливаем и удаляем старые контейнеры Docker
echo "2. Останавливаем Docker Compose (с удалением volumes)..."
docker compose down -v

echo ""
echo "3. Запускаем Docker Compose (Keycloak, Redis, LDAP)..."
docker compose up -d

echo ""
echo "4. Ожидаем готовности Keycloak..."
for i in {1..30}; do
  if curl -s -f http://localhost:8080/realms/reports-realm > /dev/null 2>&1; then
    echo "✓ Keycloak начал отвечать (попытка $i)"
    sleep 5
    echo "✓ Keycloak готов к работе"
    break
  fi
  echo "Ожидание Keycloak... (попытка $i/30)"
  sleep 2
done

echo ""
echo "5. Ожидаем готовности Redis..."
for i in {1..15}; do
  if docker compose exec -T redis redis-cli ping > /dev/null 2>&1; then
    echo "✓ Redis готов к работе (попытка $i)"
    break
  fi
  echo "Ожидание Redis... (попытка $i/15)"
  sleep 1
done

echo ""
echo "6. Запускаем reports_api..."
uv run python -m reports_api.main > /tmp/reports_api.log 2>&1 &
REPORTS_PID=$!
echo "✓ reports_api запущен (PID: $REPORTS_PID)"
echo "  Логи: /tmp/reports_api.log"

echo ""
echo "7. Запускаем auth_proxy..."
uv run python -m auth_proxy.main > /tmp/auth_proxy.log 2>&1 &
AUTH_PROXY_PID=$!
echo "✓ auth_proxy запущен (PID: $AUTH_PROXY_PID)"
echo "  Логи: /tmp/auth_proxy.log"

echo ""
echo "8. Ожидаем готовности reports_api..."
for i in {1..15}; do
  if curl -s -f http://localhost:3002/jwt > /dev/null 2>&1; then
    echo "✓ reports_api готов к работе (попытка $i)"
    break
  fi
  echo "Ожидание reports_api... (попытка $i/15)"
  sleep 1
done

echo ""
echo "9. Ожидаем готовности auth_proxy..."
for i in {1..15}; do
  if curl -s -f http://localhost:3000/health > /dev/null 2>&1; then
    echo "✓ auth_proxy готов к работе (попытка $i)"
    break
  fi
  echo "Ожидание auth_proxy... (попытка $i/15)"
  sleep 1
done

echo ""
echo "10. Запускаем фронтенд (Vite)..."
cd bionicpro_frontend || exit 1

npm run dev > /tmp/frontend.log 2>&1 &
FRONTEND_PID=$!
cd ..
echo "✓ Фронтенд запущен (PID: $FRONTEND_PID)"
echo "  Логи: /tmp/frontend.log"

echo ""
echo "11. Ожидаем готовности фронтенда..."
for i in {1..20}; do
  if curl -s -f http://localhost:5173 > /dev/null 2>&1; then
    echo "✓ Фронтенд готов к работе (попытка $i)"
    break
  fi
  echo "Ожидание фронтенда... (попытка $i/20)"
  sleep 1
done

echo ""
echo "=== Все сервисы запущены ==="
echo ""
echo "Доступные сервисы:"
echo "  - Keycloak:     http://localhost:8080"
echo "  - Redis:        localhost:6379"
echo "  - reports_api:  http://localhost:3002"
echo "  - auth_proxy:   http://localhost:3000"
echo "  - Frontend:     http://localhost:5173"
echo ""
echo "Для остановки всех сервисов используйте: ./scripts/stop_all_services.sh"
