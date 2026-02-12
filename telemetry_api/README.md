# Telemetry API

Микросервис для сбора телеметрии с бионических протезов.

## Описание

Telemetry API предоставляет REST API для приема и хранения телеметрических данных с EMG-сенсоров бионических протезов. Микросервис построен на FastAPI и использует PostgreSQL для хранения данных.

## Технологический стек

- **Python 3.12+**
- **FastAPI** — веб-фреймворк
- **SQLModel** — ORM для работы с БД (объединяет SQLAlchemy и Pydantic)
- **PostgreSQL 14** — база данных
- **pytest** — фреймворк для тестирования

## Структура проекта

```
telemetry_api/
├── __init__.py
├── main.py                  # Основной модуль API
└── README.md                # Этот файл
```

## API Endpoints

### POST /telemetry

Добавление списка телеметрических событий в БД.

**Request Body:**
```json
{
  "events": [
    {
      "user_id": 512,
      "prosthesis_type": "arm",
      "muscle_group": "Hamstrings",
      "signal_frequency": 193,
      "signal_duration": 4250,
      "signal_amplitude": 3.89,
      "created_ts": "2025-03-13T06:01:09Z"
    },
    {
      "user_id": 887,
      "prosthesis_type": "hand",
      "muscle_group": "Biceps",
      "signal_frequency": 489,
      "signal_duration": 3702,
      "signal_amplitude": 4.46,
      "created_ts": "2025-03-04T23:12:31Z"
    }
  ]
}
```

**Response (201 Created):**
```json
[
  {
    "id": 1,
    "user_id": 512,
    "prosthesis_type": "arm",
    "muscle_group": "Hamstrings",
    "signal_frequency": 193,
    "signal_duration": 4250,
    "signal_amplitude": 3.89,
    "event_timestamp": "2025-03-13T06:01:09Z",
    "saved_ts": "2025-11-18T11:30:00.000000Z"
  },
  {
    "id": 2,
    "user_id": 887,
    "prosthesis_type": "hand",
    "muscle_group": "Biceps",
    "signal_frequency": 489,
    "signal_duration": 3702,
    "signal_amplitude": 4.46,
    "event_timestamp": "2025-03-04T23:12:31Z",
    "saved_ts": "2025-11-18T11:30:00.000000Z"
  }
]
```

**Обязательные поля события:**
- `user_id` — идентификатор пользователя протеза
- `prosthesis_type` — тип протеза (arm, hand, leg и т.д.)
- `muscle_group` — группа мышц (Biceps, Hamstrings, Gastrocnemius и т.д.)
- `signal_frequency` — частота сигнала в Гц
- `signal_duration` — длительность сигнала в миллисекундах
- `signal_amplitude` — амплитуда сигнала
- `created_ts` — время создания события на стороне протеза (ISO 8601)

**Автоматически добавляемые поля:**
- `id` — уникальный идентификатор записи
- `saved_ts` — время сохранения в БД на стороне сервера (UTC)

**Ошибки:**
- `400 Bad Request` — если список событий пустой
- `422 Unprocessable Entity` — если не переданы обязательные поля

### GET /health

Проверка работоспособности API.

**Response (200 OK):**
```json
{
  "status": "healthy",
  "service": "Telemetry API"
}
```

## Модель данных

### EmgSensorData (emg_sensor_data)

| Поле | Тип | Описание |
|------|-----|----------|
| id | INTEGER | Уникальный идентификатор (автоинкремент) |
| user_id | INTEGER | Идентификатор пользователя протеза |
| prosthesis_type | VARCHAR(50) | Тип протеза |
| muscle_group | VARCHAR(100) | Группа мышц |
| signal_frequency | INTEGER | Частота сигнала в Гц |
| signal_duration | INTEGER | Длительность сигнала в мс |
| signal_amplitude | FLOAT | Амплитуда сигнала |
| event_timestamp | TIMESTAMP | Время снятия сигнала (created_ts) |
| saved_ts | TIMESTAMP | Время сохранения в БД (UTC) |

## Настройка и запуск

### Предварительные требования

1. Python 3.12+
2. uv (установлен в корне проекта)
3. PostgreSQL 14 (запускается через docker-compose)

### Запуск базы данных

```bash
# Из корня проекта architecture-bionicpro
docker compose up -d telemetry_db
```

База данных будет доступна на `localhost:5445`.

**Параметры подключения:**
- Host: `localhost`
- Port: `5445`
- Database: `telemetry_db`
- User: `telemetry_user`
- Password: `telemetry_password`

### Запуск API

```bash
# Из корня проекта architecture-bionicpro
uv run python telemetry_api/main.py
```

API будет доступен на `http://localhost:3002`.

## Примеры использования

### Отправка телеметрии (curl)

```bash
curl -X POST http://localhost:3002/telemetry \
  -H "Content-Type: application/json" \
  -d '{
    "events": [
      {
        "user_id": 512,
        "prosthesis_type": "arm",
        "muscle_group": "Biceps",
        "signal_frequency": 200,
        "signal_duration": 1000,
        "signal_amplitude": 3.5,
        "created_ts": "2025-01-01T12:00:00Z"
      }
    ]
  }'
```

### Отправка телеметрии (Python)

```python
import httpx
from datetime import datetime, timezone

# Подготовка данных
events = [
    {
        "user_id": 100,
        "prosthesis_type": "arm",
        "muscle_group": "Biceps",
        "signal_frequency": 200,
        "signal_duration": 1000,
        "signal_amplitude": 3.5,
        "created_ts": datetime.now(timezone.utc).isoformat()
    },
    {
        "user_id": 100,
        "prosthesis_type": "arm",
        "muscle_group": "Triceps",
        "signal_frequency": 250,
        "signal_duration": 1500,
        "signal_amplitude": 4.0,
        "created_ts": datetime.now(timezone.utc).isoformat()
    }
]

# Отправка
response = httpx.post(
    "http://localhost:3002/telemetry",
    json={"events": events}
)

if response.status_code == 201:
    saved_events = response.json()
    print(f"Сохранено {len(saved_events)} событий")
    for event in saved_events:
        print(f"  - ID: {event['id']}, saved_ts: {event['saved_ts']}")
else:
    print(f"Ошибка: {response.json()['detail']}")
```

## Особенности реализации

- **Пакетная обработка** — API принимает массив событий и сохраняет их одной транзакцией
- **SQLModel** используется для минимизации дублирования кода между Pydantic-моделями и SQLAlchemy ORM
- Все временные метки хранятся в **UTC**
- **Два временных поля**:
  - `signal_time` (created_ts) — когда событие создано на стороне протеза
  - `saved_ts` — когда событие сохранено в БД на стороне сервера
- API поддерживает **CORS** для интеграции с фронтендом
- Все SQL-запросы **логируются** (echo=True)
- Подробные **комментарии на русском языке** во всем коде

## Интеграция с протезами

Протезы должны отправлять телеметрию пакетами для оптимизации сетевого трафика:

```python
# Пример кода на стороне протеза
class ProsthesisTelemetry:
    def __init__(self):
        self.buffer = []
        self.api_url = "http://telemetry-api:3003/telemetry"
    
    def record_signal(self, muscle_group, frequency, duration, amplitude):
        """Записывает сигнал в буфер."""
        self.buffer.append({
            "user_id": self.user_id,
            "prosthesis_type": "arm",
            "muscle_group": muscle_group,
            "signal_frequency": frequency,
            "signal_duration": duration,
            "signal_amplitude": amplitude,
            "created_ts": datetime.now(timezone.utc).isoformat()
        })
        
        # Отправляем, если буфер заполнен
        if len(self.buffer) >= 100:
            self.flush()
    
    def flush(self):
        """Отправляет накопленные события на сервер."""
        if not self.buffer:
            return
        
        try:
            response = httpx.post(
                self.api_url,
                json={"events": self.buffer},
                timeout=10.0
            )
            response.raise_for_status()
            self.buffer.clear()
        except Exception as e:
            print(f"Ошибка отправки телеметрии: {e}")
```
