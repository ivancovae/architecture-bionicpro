# Проектная работа по спринту 9: Объединение сервисов через SSO и работа с данными для аналитики 

## Оглавление

1. [Задание 1: Повышение безопасности системы](Task1/README.md)
   - Архитектурное решение и доработайте диаграмму C4 для управления учётными данными пользователя
   - Улучшите безопасность существующего приложения, заменив Code Grant на PKCE
   - Обеспечьте безопасное получение и хранение access-и refresh-токенов.
   - Добавьте LDAP для возможности получения данных о пользователях представительства BionicPRO в другой стране.
   - Настройка MFA
   - Добавление OAuth 2.0 от Яндекс ID

2. [Задание 2: Разработка сервиса отчётов](Task2/README.md)
   - Архитектура решения для подготовки и получения отчётов
   - Разработка Airflow DAG для ETL-процесса
   - Создание бэкенд-части Reports API
   - Ограничение доступа к эндпоинту отчётности
   - Добавление UI для получения отчётов

3. [Задание 3: Снижение нагрузки на базу данных](Task3/README.md)
   - Структура хранения отчётов в MinIO
   - Настройка MinIO и nginx-прокси
   - Доработки в Reports API и фронтенде
   - Настройка TTL для кэша отчётов

4. [Задание 4: Повышение оперативности и стабильности работы CRM](Task4/README.md)
   - Kafka + Kafka Connect + Debezium для переноса данных
   - Настройки PostgreSQL для CDC
   - Настройки ClickHouse и схема debezium
   - Доработки в Reports API

## Как запуститься

Если не хотите тестировать MFA -- переименуйте `realm-export-no-mfa.json` в `realm-export.json`

Если хотите тестировать MFA -- переименуйте `realm-export-mfa.json` в `realm-export.json`


```bash
docker compose down -v
docker compose up -d
```
http://localhost:3000, юзер `prosthetic1`, пароль `prosthetic123`

## Основные сервисы

### Фронтенд и прокси
- **`bionicpro_frontend`** — фронтенд-приложение на React + TypeScript
  - Через прокси: http://localhost:3000
  - Напрямую (для разработки): http://localhost:5173
- **`auth_proxy`** — аутентифицирующее прокси на FastAPI
  - Инкапсулирует работу с Keycloak
  - Обеспечивает ротацию сессий
  - Проксирует запросы к микросервисам

### Микросервисы бэкенда
- **`crm_api`** — API для работы с CRM-данными (пользователи)
  - Порт: http://localhost:3001
  - База данных: PostgreSQL (`crm_db`)
- **`telemetry_api`** — API для работы с телеметрией протезов
  - Порт: http://localhost:3002
  - База данных: PostgreSQL (`telemetry_db`)
- **`reports_api`** — API для генерации отчётов
  - Порт: http://localhost:3003
  - Источники данных: ClickHouse (`default` и `debezium` схемы)
  - Кэширование: MinIO

### Инфраструктура
- **`keycloak`** — Identity Provider (SSO)
  - Веб-интерфейс: http://localhost:8080
  - Realm: `reports-realm`
  - Интеграция: LDAP, Yandex OAuth, Google Authenticator (MFA)
- **`openldap-china`** — LDAP-сервер для внешних пользователей
- **`minio`** — S3-совместимое хранилище для кэша отчётов
  - Веб-интерфейс: http://localhost:9001
  - Учётные данные: `minio_user` / `minio_password`
- **`minio-nginx`** — nginx-прокси с Lua для контроля доступа к MinIO
- **`olap-db`** — ClickHouse для OLAP-аналитики
  - Порт: http://localhost:8123
  - Схемы: `default` (ETL), `debezium` (CDC)
- **`kafka`** + **`zookeeper`** — брокер сообщений для CDC
  - Kafka UI: http://localhost:8084
- **`debezium`** — Kafka Connect с Debezium для CDC из PostgreSQL
  - Debezium UI: http://localhost:8088
- **`airflow`** — оркестратор для ETL-процессов
  - Веб-интерфейс: http://localhost:8082
  - DAG: `import_olap_data_monthly`
