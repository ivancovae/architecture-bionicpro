# Настройка TTL для отчётов в MinIO

## Изменения

### 1. MinIO: TTL 40 дней для бакета reports
**Файл**: `minio/init-minio.sh`

Добавлен lifecycle policy для автоматического удаления файлов старше 40 дней:
```bash
# Настраиваем TTL (lifecycle) для бакета reports: удаление файлов старше 40 дней
cat > /tmp/lifecycle-reports.json <<EOF
{
  "Rules": [
    {
      "ID": "ExpireOldReports",
      "Status": "Enabled",
      "Expiration": {
        "Days": 40
      }
    }
  ]
}
EOF

mc ilm import local/reports < /tmp/lifecycle-reports.json
```

### 2. Reports API: TTL 7 дней для отчётов
**Файл**: `reports_api/main.py`

При сохранении отчёта добавляются метаданные с информацией о TTL:
```python
# Вычисляем дату истечения (через 7 дней)
expiry_date = datetime.now() + timedelta(days=7)

# Добавляем метаданные с информацией о TTL
metadata = {
    "X-Amz-Meta-Ttl-Days": "7",
    "X-Amz-Meta-Created-At": datetime.now().isoformat(),
    "X-Amz-Meta-Expires-At": expiry_date.isoformat(),
}

minio.put_object(
    bucket_name=bucket_name,
    object_name=file_name,
    data=io.BytesIO(report_bytes),
    length=len(report_bytes),
    content_type="application/json",
    metadata=metadata,
)
```

## Применение изменений

### Шаг 1: Пересобрать образы
```bash
docker compose build minio reports-api
```

### Шаг 2: Перезапустить сервисы
```bash
docker compose down -v
docker compose up -d
```

### Шаг 3: Проверить lifecycle policy
```bash
# Подключиться к контейнеру MinIO
docker compose exec minio sh

# Проверить lifecycle policy
mc ilm ls local/reports
```

Ожидаемый вывод:
```
     ID     |  Prefix  |  Enabled   | Expiry |  Date/Days   |  Transition  |    Date/Days     |  Storage-Class   |       Tags
------------|----------|------------|--------|--------------|--------------|------------------|------------------|------------------
ExpireOldReports |          |    ✓       | Expiry |   40 day(s)  |              |                  |                  |
```

## Логика работы TTL

1. **Reports API** создаёт отчёт и сохраняет его в MinIO с метаданными:
   - `X-Amz-Meta-Ttl-Days: 7` — отчёт актуален 7 дней
   - `X-Amz-Meta-Expires-At` — дата истечения актуальности

2. **MinIO lifecycle policy** автоматически удаляет файлы старше 40 дней:
   - Файлы физически удаляются через 40 дней после создания
   - Это происходит автоматически, без участия приложения

3. **Период "устаревших отчётов"**:
   - С 8-го по 40-й день отчёт считается устаревшим, но всё ещё доступен
   - Приложение может использовать метаданные для отображения предупреждения
   - Через 40 дней файл удаляется автоматически

## Преимущества

- ✅ Автоматическая очистка старых отчётов
- ✅ Снижение использования дискового пространства
- ✅ Возможность отображать статус актуальности отчёта
- ✅ Гибкая настройка TTL на двух уровнях
