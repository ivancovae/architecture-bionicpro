# Reports Backend API

Микросервис для генерации отчетов на основе данных из ClickHouse OLAP БД.

## Структура

- `main.py` - основной модуль FastAPI с эндпоинтами
- `olap_query_examples.py` - примеры запросов к ClickHouse через SQLAlchemy
- `import_olap_data.py` - скрипт для импорта данных из CRM и Telemetry БД в ClickHouse

## Зависимости

Для работы требуется:
- PostgreSQL (CRM DB на порту 5444, Telemetry DB на порту 5445)
- ClickHouse (на порту 8123)
- Python 3.12+

## Импорт данных в ClickHouse

### Полный импорт всех данных

```bash
uv run python reports_api/import_olap_data.py
```

### Импорт с фильтрацией по времени

```bash
# Импорт телеметрии только за январь 2026
uv run python reports_api/import_olap_data.py \
  --telemetry_start_ts="2026-01-01 00:00:00" \
  --telemetry_end_ts="2026-02-01 00:00:00"
```

### Использование как модуля

```python
from reports_api.import_olap_data import import_olap_data
from datetime import datetime

# Полный импорт
import_olap_data()

# Импорт с фильтрами
import_olap_data(
    telemetry_start_ts=datetime(2025, 9, 1),
    telemetry_end_ts=datetime(2026, 3, 31)
)
```

## Структура данных в ClickHouse

### Таблица `users` (Join Table Engine)

- `user_id` (Int32) - ID пользователя
- `user_uuid` (String) - UUID пользователя (формат Keycloak)
- `name` (String) - имя пользователя
- `email` (String) - email
- `age` (Nullable(Int32)) - возраст
- `gender` (Nullable(String)) - пол
- `country` (Nullable(String)) - страна
- `address` (Nullable(String)) - адрес
- `phone` (Nullable(String)) - телефон
- `registration_ts` (DateTime) - дата регистрации пользователя
- `registered_at` (DateTime) - дата добавления записи в БД

**Индексация**: PRIMARY KEY = `user_id`, индексы по `user_uuid` и `registration_ts`

### Таблица `telemetry_events` (MergeTree)

- `id` (Int64) - ID события
- `user_id` (Int32) - ID пользователя
- `prosthesis_type` (String) - тип протеза (arm, hand, leg)
- `muscle_group` (String) - группа мышц
- `signal_frequency` (Int32) - частота сигнала (Гц)
- `signal_duration` (Int32) - длительность сигнала (мс)
- `signal_amplitude` (Float64) - амплитуда сигнала
- `event_timestamp` (DateTime) - время снятия сигнала
- `saved_ts` (DateTime) - время сохранения в БД

**Партиционирование**: по году и месяцу `event_timestamp`  
**Сортировка**: `ORDER BY (user_id, event_timestamp)`

## API Эндпоинты

### POST /report

Генерирует отчет по пользователю за указанный период.

**Запрос:**

```json
{
  "user_id": 512,
  "start_ts": "2026-01-01T00:00:00",  // опционально
  "end_ts": "2026-03-01T23:59:59"     // опционально
}
```

**Ответ:**

```json
{
  "user_name": "Ivan Ivanov",
  "user_email": "ivan.ivanov@example.ru",
  "total_events": 150,
  "total_duration": 450000,
  "prosthesis_stats": [
    {
      "prosthesis_type": "hand",
      "events_count": 50,
      "total_duration": 1200000,
      "avg_amplitude": 2.31,
      "avg_frequency": 175.2
    },
    {
      "prosthesis_type": "arm",
      "events_count": 100,
      "total_duration": 350000,
      "avg_amplitude": 3.71,
      "avg_frequency": 177.5
    }
    
  ]
}
```

## Примеры запросов к OLAP БД

Запустить примеры:

```bash
uv run python reports_api/olap_query_examples.py
```

Примеры включают:
1. Общее количество пользователей
2. Общее количество событий
3. События по конкретному пользователю
4. События по месяцам
5. Средняя амплитуда и частота по типам протезов
6. Детальный отчет по пользователю
7. Топ самых активных пользователей
8. Распределение событий по группам мышц

## Запуск сервера

```bash
uv run python reports_api/main.py
```

Сервер будет доступен на `http://localhost:3003`

## Логика работы import_olap_data

1. **Подключение к ClickHouse** - проверка доступности OLAP БД
2. **Создание таблиц** - если таблицы не существуют, они создаются
3. **Импорт пользователей** - полная перезаливка данных из CRM DB
4. **Импорт телеметрии** - загрузка событий с учетом временных фильтров
5. **Удаление старых данных** - события из указанного интервала удаляются перед вставкой новых
6. **Очистка orphaned events** - удаление событий для пользователей, которых больше нет в БД

## Особенности реализации

- **Asyncio-подход**: все операции используют асинхронные вызовы
- **Партиционирование**: телеметрия партиционирована по году и месяцу для быстрого поиска
- **Join Table Engine**: таблица пользователей использует Join Engine для быстрых JOIN-операций
- **Инкрементальная загрузка**: поддержка загрузки только новых данных за период
- **Автоматическая очистка**: удаление orphaned events при каждом импорте
