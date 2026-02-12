#!/bin/bash

# Скрипт инициализации MinIO с автоматической настройкой OIDC и политик

echo "Запуск MinIO сервера..."

# Запускаем MinIO в фоне (используем статический ключ)
minio server --console-address ":9001" /data &
MINIO_PID=$!

# Ждём запуска MinIO
echo "Ожидание запуска MinIO..."
sleep 30

# Ждём полной инициализации MinIO
echo "Ожидание полной инициализации MinIO..."
for i in {1..30}; do
  if mc admin info local > /dev/null 2>&1; then
    echo "✓ MinIO полностью инициализирован (попытка $i)"
    break
  fi
  echo "Ожидание инициализации MinIO... (попытка $i/30)"
  sleep 2
done

# Настраиваем mc (MinIO Client)
echo "Настройка MinIO Client..."
mc alias set local http://localhost:9000 ${MINIO_ROOT_USER} ${MINIO_ROOT_PASSWORD}

# Создаём бакет reports если его нет
echo "Создание бакета reports..."
mc mb local/reports --ignore-existing

# Настраиваем публичный доступ к бакету reports (только для чтения)
echo "Настройка публичного доступа к бакету reports..."
mc anonymous set download local/reports

# Настраиваем TTL (lifecycle) для бакета reports: удаление файлов старше 7 дней
echo "Настройка TTL (7 дней) для бакета reports..."
cat > /tmp/lifecycle-reports.json <<EOF
{
  "Rules": [
    {
      "ID": "ExpireOldReports",
      "Status": "Enabled",
      "Expiration": {
        "Days": 7
      }
    }
  ]
}
EOF

mc ilm import local/reports < /tmp/lifecycle-reports.json
echo "✓ TTL настроен: файлы старше 7 дней будут автоматически удаляться"

echo "MinIO инициализация завершена"

# Ждём завершения процесса MinIO
wait $MINIO_PID
