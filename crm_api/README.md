# CRM API

Микросервис для регистрации пользователей интернет-магазина бионических протезов.

## Описание

CRM API предоставляет REST API для регистрации новых клиентов в системе. Микросервис построен на FastAPI и использует PostgreSQL для хранения данных.

## Технологический стек

- **Python 3.12+**
- **FastAPI** — веб-фреймворк
- **SQLModel** — ORM для работы с БД (объединяет SQLAlchemy и Pydantic)
- **PostgreSQL 14** — база данных
- **pytest** — фреймворк для тестирования

## API Endpoints

### POST /register

Регистрация нового клиента в системе.

**Request Body:**
```json
{
  "name": "Ivan Ivanov",
  "email": "ivan.ivanov@example.ru",
  "age": 33,
  "gender": "Male",
  "country": "Russia",
  "address": "Russia, Orsk, Molodezhnaya St., 18 apartment 6",
  "phone": "+7(921)345-19-48"
}
```

**Response (201 Created):**
```json
{
  "id": 1,
  "name": "Ivan Ivanov",
  "email": "ivan.ivanov@example.ru",
  "age": 33,
  "gender": "Male",
  "country": "Russia",
  "address": "Russia, Orsk, Molodezhnaya St., 18 apartment 6",
  "phone": "+7(921)345-19-48",
  "registered_at": "2026-02-11T13:45:00.000000Z"
}
```

**Обязательные поля:**
- `name` — полное имя клиента
- `email` — email клиента (должен быть уникальным)

**Опциональные поля:**
- `age` — возраст
- `gender` — пол
- `country` — страна
- `address` — адрес
- `phone` — телефон

**Ошибки:**
- `400 Bad Request` — если email уже зарегистрирован
- `422 Unprocessable Entity` — если не переданы обязательные поля

### GET /health

Проверка работоспособности API.

**Response (200 OK):**
```json
{
  "status": "healthy",
  "service": "CRM API"
}
```

## Модель данных

### Customer (customers)

| Поле | Тип | Описание |
|------|-----|----------|
| id | INTEGER | Уникальный идентификатор (автоинкремент) |
| name | VARCHAR(100) | Полное имя клиента |
| email | VARCHAR(100) | Email (уникальный, индексируется) |
| age | INTEGER | Возраст клиента |
| gender | VARCHAR(10) | Пол клиента |
| country | VARCHAR(100) | Страна проживания |
| address | VARCHAR(255) | Адрес клиента |
| phone | VARCHAR(25) | Номер телефона |
| registered_at | TIMESTAMP | Дата и время регистрации (UTC) |

## Настройка и запуск

### Предварительные требования

1. Python 3.12+
2. uv (установлен в корне проекта)
3. PostgreSQL 14 (запускается через docker-compose)

### Запуск базы данных

```bash
# Из корня проекта architecture-bionicpro
docker compose up -d crm_db
```

База данных будет доступна на `localhost:5444`.

**Параметры подключения:**
- Host: `localhost`
- Port: `5444`
- Database: `crm_db`
- User: `crm_user`
- Password: `crm_password`

### Запуск API

```bash
# Из корня проекта architecture-bionicpro
uv run python crm_api/main.py
```

API будет доступен на `http://localhost:3001`.

## Примеры использования

### Регистрация клиента (curl)

```bash
curl -X POST http://localhost:3001/register \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Ivan Ivanov",
    "email": "ivan.ivanov@example.ru",
    "age": 33,
    "gender": "Male",
    "country": "Russia"
  }'
```

### Регистрация клиента (Python)

```python
import httpx

response = httpx.post(
    "http://localhost:3001/register",
    json={
        "name": "Alban Ceray",
        "email": "alban.ceray@example.fr",
        "age": 76,
        "gender": "Male",
        "country": "France"
    }
)

if response.status_code == 201:
    customer = response.json()
    print(f"Клиент зарегистрирован с ID: {customer['id']}")
else:
    print(f"Ошибка: {response.json()['detail']}")
```

## Особенности реализации

- **SQLModel** используется для минимизации дублирования кода между Pydantic-моделями и SQLAlchemy ORM
- Все временные метки хранятся в **UTC**
- Email является **уникальным** и **индексируется** для быстрого поиска
- API поддерживает **CORS** для интеграции с фронтендом
- Все SQL-запросы **логируются** (echo=True)
- Подробные **комментарии на русском языке** во всем коде
