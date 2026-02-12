"""Основной модуль API для отчетов с проверкой JWT-токенов Keycloak."""

# Импортируем модуль json для сериализации словарей в строки
import json

# Импортируем модуль logging для вывода диагностических сообщений
import logging

# Импортируем типы Any и Dict для аннотаций типов функций
from datetime import datetime
from typing import Any, Dict, List, Optional

# Импортируем httpx для выполнения HTTP-запросов к Keycloak
import httpx

# Импортируем Depends, FastAPI, Header и HTTPException для построения API
from fastapi import Depends, FastAPI, Header, HTTPException

# Импортируем CORSMiddleware для настройки CORS-политики
from fastapi.middleware.cors import CORSMiddleware

# Импортируем Pydantic для валидации данных
from pydantic import BaseModel, Field

# Импортируем библиотеку PyJWT для работы с JWT-токенами
import jwt

# Импортируем RSAAlgorithm для преобразования открытых ключей из JWK в формат RSA
from jwt.algorithms import RSAAlgorithm

# Импортируем набор исключений PyJWT для обработки ошибок проверки токена
from jwt import exceptions as jwt_exceptions

# Импортируем ClickHouse клиент
import clickhouse_connect

# Импортируем MinIO клиент для хранения отчетов
from minio import Minio
import io

# Импортируем contextlib для lifespan
from contextlib import asynccontextmanager

# Настраиваем базовый уровень логирования на INFO
logging.basicConfig(level=logging.INFO)

# Глобальная переменная для MinIO-клиента
minio_client: Minio | None = None

# Флаг для отслеживания инициализации схемы debezium
debezium_schema_initialized: bool = False


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager для инициализации и очистки ресурсов."""
    # Startup: инициализация MinIO
    logging.info("Инициализация MinIO-клиента...")
    init_minio()
    logging.info("MinIO-клиент успешно инициализирован")

    # Startup: инициализация схемы default в ClickHouse
    logging.info("Инициализация схемы default в ClickHouse...")
    init_default_schema()
    logging.info("Схема default успешно инициализирована")

    # Startup: инициализация схемы debezium в ClickHouse
    logging.info("Инициализация схемы debezium в ClickHouse...")
    init_debezium_schema()
    logging.info("Схема debezium успешно инициализирована")

    # Startup: пересоздание Debezium-коннекторов для snapshot существующих данных
    logging.info("Инициализация Debezium-коннекторов...")
    init_debezium_connectors()
    logging.info("Debezium-коннекторы успешно инициализированы")

    # Startup: импорт данных из PostgreSQL в ClickHouse (схема default)
    logging.info("Импорт данных из PostgreSQL в ClickHouse...")
    import_olap_data()
    logging.info("Данные успешно импортированы")

    yield

    # Shutdown: очистка ресурсов (если необходимо)
    logging.info("Завершение работы приложения")


# Создаем экземпляр FastAPI с lifespan
app = FastAPI(lifespan=lifespan)

# Добавляем промежуточное ПО для поддержки CORS-запросов с фронтенда
app.add_middleware(
    # Указываем класс промежуточного ПО, который добавляем
    CORSMiddleware,
    # Определяем список доменов, которым разрешен доступ к API
    allow_origins=["http://localhost:3000", "http://localhost:5173", "*"],
    # Разрешаем передачу cookies и авторизационных заголовков
    allow_credentials=True,
    # Разрешаем все HTTP-методы для запросов
    allow_methods=["*"],
    # Разрешаем любые заголовки в запросах
    allow_headers=["*"],
)


def get_minio_client():
    """Получает глобальный MinIO-клиент."""
    global minio_client
    if minio_client is None:
        raise RuntimeError("MinIO-клиент не инициализирован")
    return minio_client


def init_minio():
    """Инициализирует MinIO-клиент и создает бакет reports."""
    import os

    global minio_client

    # Создаем MinIO-клиент с учетом креденшиалов из docker-compose или переменных окружения
    minio_host = os.getenv("MINIO_HOST", "localhost:9000")  # Адрес MinIO-сервера (из переменной окружения)
    minio_access_key = os.getenv("MINIO_ACCESS_KEY", "minio_user")  # Логин из переменной окружения
    minio_secret_key = os.getenv("MINIO_SECRET_KEY", "minio_password")  # Пароль из переменной окружения

    minio_client = Minio(
        endpoint=minio_host,  # Адрес MinIO-сервера
        access_key=minio_access_key,  # Логин
        secret_key=minio_secret_key,  # Пароль
        secure=False,  # Используем HTTP, а не HTTPS
    )

    bucket_name = "reports"

    # Проверяем, существует ли бакет
    if not minio_client.bucket_exists(bucket_name=bucket_name):
        logging.info(f"Бакет {bucket_name} не найден, создаем...")
        # Создаем бакет
        minio_client.make_bucket(bucket_name=bucket_name)
        logging.info(f"Бакет {bucket_name} успешно создан")
    else:
        logging.info(f"Бакет {bucket_name} уже существует")

    # Lifecycle policy (TTL 7 дней) настроена на уровне контейнера MinIO через init-minio.sh
    logging.info(f"Бакет {bucket_name} готов к использованию (TTL настроен в MinIO)")


def init_default_schema():
    """Инициализирует схему default в ClickHouse с таблицами для OLAP-данных."""
    import os
    import time

    # Пытаемся подключиться к ClickHouse с retry-логикой
    max_attempts = 30
    client = None

    for attempt in range(1, max_attempts + 1):
        try:
            client = get_clickhouse_client()
            # Проверяем подключение простым запросом
            client.command("SELECT 1")
            logging.info(f"✓ Подключение к ClickHouse установлено (попытка {attempt})")
            break
        except Exception as e:
            if attempt == max_attempts:
                logging.error(f"✗ Не удалось подключиться к ClickHouse после {max_attempts} попыток: {e}")
                raise RuntimeError(f"Не удалось подключиться к ClickHouse для инициализации схемы default: {e}")

            logging.info(f"Ожидание готовности ClickHouse... (попытка {attempt}/{max_attempts})")
            time.sleep(2)

    # Создаем базу данных default (она обычно уже существует, но проверим)
    logging.info("Проверка наличия базы данных default...")
    # База default создаётся автоматически в ClickHouse, но явно проверим
    client.command("CREATE DATABASE IF NOT EXISTS default")
    logging.info("✓ База данных default создана или уже существует")

    # Проверяем, существуют ли таблицы
    existing_tables = client.query("SHOW TABLES FROM default").result_rows
    existing_table_names = {row[0] for row in existing_tables}

    # Создаем таблицу users, если её нет
    if "users" not in existing_table_names:
        logging.info("Создание таблицы default.users...")
        client.command(
            """
            CREATE TABLE default.users (
                user_id Int32,
                user_uuid String,
                name String,
                email String,
                age Nullable(Int32),
                gender Nullable(String),
                country Nullable(String),
                address Nullable(String),
                phone Nullable(String),
                registered_at DateTime
            ) ENGINE = Join(ANY, LEFT, user_uuid)
        """
        )
        logging.info("✓ Таблица default.users создана")
    else:
        logging.info("✓ Таблица default.users уже существует")

    # Создаем таблицу telemetry_events, если её нет
    if "telemetry_events" not in existing_table_names:
        logging.info("Создание таблицы default.telemetry_events...")
        client.command(
            """
            CREATE TABLE default.telemetry_events (
                id Int64,
                event_uuid String,
                user_uuid String,
                prosthesis_type String,
                muscle_group String,
                signal_frequency Int32,
                signal_duration Int32,
                signal_amplitude Float64,
                created_ts DateTime,
                saved_ts DateTime
            ) ENGINE = ReplacingMergeTree(saved_ts)
            PARTITION BY (toYear(created_ts), toMonth(created_ts))
            ORDER BY (user_uuid, event_uuid, created_ts)
        """
        )
        logging.info("✓ Таблица default.telemetry_events создана")
    else:
        logging.info("✓ Таблица default.telemetry_events уже существует")

    logging.info("✓ Схема default полностью инициализирована")


def import_olap_data():
    """Импортирует данные из PostgreSQL в ClickHouse (схема default)."""
    # Примечание: импорт данных выполняется через отдельный скрипт dags/import_olap_data.py
    # В Docker-контейнере этот скрипт недоступен, поэтому импорт нужно выполнять вручную
    # или через отдельный сервис
    logging.info(
        "Импорт данных из PostgreSQL в ClickHouse пропущен (выполняется вручную через dags/import_olap_data.py)"
    )


def init_debezium_connectors():
    """
    Инициализирует Debezium-коннекторы для репликации данных из PostgreSQL в Kafka.

    Удаляет существующие коннекторы и создаёт новые с snapshot.mode=always,
    чтобы сделать snapshot существующих данных.
    """
    import os
    import time

    # Получаем адрес Debezium из переменной окружения
    debezium_url = os.getenv("DEBEZIUM_URL", "http://debezium:8083")

    # Конфигурации коннекторов
    connectors_config = [
        {
            "name": "crm-connector",
            "config": {
                "connector.class": "io.debezium.connector.postgresql.PostgresConnector",
                "database.hostname": os.getenv("CRM_DB_HOST", "crm-db"),
                "database.port": "5432",
                "database.user": os.getenv("CRM_DB_USER", "crm_user"),
                "database.password": os.getenv("CRM_DB_PASSWORD", "crm_password"),
                "database.dbname": os.getenv("CRM_DB_NAME", "crm_db"),
                "database.server.name": "crm",
                "table.include.list": "public.users",
                "topic.prefix": "crm",
                "plugin.name": "pgoutput",
                "slot.name": "debezium_crm",
                "publication.name": "dbz_publication_crm",
                "publication.autocreate.mode": "filtered",
                "snapshot.mode": "always",  # Всегда делать snapshot
            },
        },
        {
            "name": "telemetry-connector",
            "config": {
                "connector.class": "io.debezium.connector.postgresql.PostgresConnector",
                "database.hostname": os.getenv("TELEMETRY_DB_HOST", "telemetry-db"),
                "database.port": "5432",
                "database.user": os.getenv("TELEMETRY_DB_USER", "telemetry_user"),
                "database.password": os.getenv("TELEMETRY_DB_PASSWORD", "telemetry_password"),
                "database.dbname": os.getenv("TELEMETRY_DB_NAME", "telemetry_db"),
                "database.server.name": "telemetry",
                "table.include.list": "public.telemetry_events",
                "topic.prefix": "telemetry",
                "plugin.name": "pgoutput",
                "slot.name": "debezium_telemetry",
                "publication.name": "dbz_publication_telemetry",
                "publication.autocreate.mode": "filtered",
                "snapshot.mode": "always",  # Всегда делать snapshot
            },
        },
    ]

    try:
        # Проверяем, что Debezium доступен
        logging.info("Проверка доступности Debezium...")
        for attempt in range(1, 31):
            try:
                response = httpx.get(f"{debezium_url}/", timeout=5)
                if response.status_code == 200:
                    logging.info(f"✓ Debezium доступен (попытка {attempt})")
                    break
            except Exception:
                pass

            if attempt == 30:
                logging.warning("✗ Debezium не доступен после 30 попыток, пропускаем инициализацию коннекторов")
                return

            logging.info(f"Ожидание Debezium... (попытка {attempt}/30)")
            time.sleep(2)

        # Удаляем существующие коннекторы
        logging.info("Удаление существующих Debezium-коннекторов...")
        for connector_config in connectors_config:
            connector_name = connector_config["name"]
            try:
                response = httpx.delete(f"{debezium_url}/connectors/{connector_name}", timeout=10)
                if response.status_code in [200, 204]:
                    logging.info(f"✓ Коннектор {connector_name} удалён")
                elif response.status_code == 404:
                    logging.info(f"ℹ Коннектор {connector_name} не существует")
            except Exception as e:
                logging.warning(f"⚠ Ошибка при удалении коннектора {connector_name}: {e}")

        # Ждём удаления
        time.sleep(3)

        # Создаём новые коннекторы
        logging.info("Создание Debezium-коннекторов...")
        for connector_config in connectors_config:
            connector_name = connector_config["name"]
            try:
                response = httpx.post(
                    f"{debezium_url}/connectors/",
                    json=connector_config,
                    timeout=10,
                    headers={"Content-Type": "application/json"},
                )
                if response.status_code in [200, 201]:
                    logging.info(f"✓ Коннектор {connector_name} создан")
                else:
                    logging.error(
                        f"✗ Ошибка при создании коннектора {connector_name}: {response.status_code} {response.text}"
                    )
            except Exception as e:
                logging.error(f"✗ Ошибка при создании коннектора {connector_name}: {e}")

        # Ждём, пока коннекторы запустятся и сделают snapshot
        logging.info("Ожидание завершения snapshot (10 секунд)...")
        time.sleep(10)

        # Проверяем статус коннекторов
        logging.info("Проверка статуса Debezium-коннекторов...")
        for connector_config in connectors_config:
            connector_name = connector_config["name"]
            try:
                response = httpx.get(f"{debezium_url}/connectors/{connector_name}/status", timeout=5)
                if response.status_code == 200:
                    status_data = response.json()
                    connector_state = status_data.get("connector", {}).get("state", "UNKNOWN")
                    logging.info(f"✓ Коннектор {connector_name}: состояние={connector_state}")
                else:
                    logging.warning(f"⚠ Не удалось получить статус коннектора {connector_name}")
            except Exception as e:
                logging.warning(f"⚠ Ошибка при получении статуса коннектора {connector_name}: {e}")

        logging.info("✓ Debezium-коннекторы инициализированы")

    except Exception as e:
        logging.error(f"✗ Ошибка при инициализации Debezium-коннекторов: {e}")


def init_debezium_schema():
    """Инициализирует схему debezium в ClickHouse с Kafka Engine таблицами."""
    import os
    import time

    global debezium_schema_initialized

    # Проверяем, была ли уже выполнена инициализация
    if debezium_schema_initialized:
        logging.info("Схема debezium уже инициализирована, пропускаем")
        return

    # Пытаемся подключиться к ClickHouse с retry-логикой
    max_attempts = 30
    client = None

    for attempt in range(1, max_attempts + 1):
        try:
            client = get_clickhouse_client()
            # Проверяем подключение простым запросом
            client.command("SELECT 1")
            logging.info(f"✓ Подключение к ClickHouse установлено (попытка {attempt})")
            break
        except Exception as e:
            if attempt == max_attempts:
                logging.error(f"✗ Не удалось подключиться к ClickHouse после {max_attempts} попыток: {e}")
                raise RuntimeError(f"Не удалось подключиться к ClickHouse для инициализации схемы debezium: {e}")

            logging.info(f"Ожидание готовности ClickHouse... (попытка {attempt}/{max_attempts})")
            time.sleep(2)

    # Получаем адрес Kafka-брокера из переменной окружения
    # Используем порт 9093 (INTERNAL listener) вместо 9092 (EXTERNAL listener)
    # т.к. EXTERNAL listener advertised как localhost:9092, что не работает в Docker-сети
    kafka_broker = os.getenv("KAFKA_BROKER", "kafka:9093")

    # Создаем базу данных debezium, если её нет
    logging.info("Проверка наличия базы данных debezium...")
    client.command("CREATE DATABASE IF NOT EXISTS debezium")
    logging.info("✓ База данных debezium создана или уже существует")

    # Проверяем, существуют ли таблицы
    existing_tables = client.query("SHOW TABLES FROM debezium").result_rows
    existing_table_names = {row[0] for row in existing_tables}

    # Создаем Kafka Engine таблицу для users, если её нет
    if "users_kafka" not in existing_table_names:
        logging.info("Создание Kafka Engine таблицы для users...")
        client.command(
            f"""
            CREATE TABLE debezium.users_kafka (
                payload String
            ) ENGINE = Kafka
            SETTINGS
                kafka_broker_list = '{kafka_broker}',
                kafka_topic_list = 'crm.public.users',
                kafka_group_name = 'clickhouse_crm_consumer',
                kafka_format = 'JSONAsString',
                kafka_num_consumers = 1,
                kafka_thread_per_consumer = 1,
                kafka_skip_broken_messages = 1000,
                kafka_max_block_size = 1048576
        """
        )
        logging.info("✓ Kafka Engine таблица users_kafka создана")
    else:
        logging.info("✓ Kafka Engine таблица users_kafka уже существует")

    # Создаем ReplacingMergeTree таблицу для users, если её нет
    if "users" not in existing_table_names:
        logging.info("Создание Join таблицы для users...")
        client.command(
            """
            CREATE TABLE debezium.users (
                user_id Int32,
                user_uuid String,
                name String,
                email String,
                age Nullable(Int32),
                gender Nullable(String),
                country Nullable(String),
                address Nullable(String),
                phone Nullable(String),
                registered_at DateTime
            ) ENGINE = Join(ANY, LEFT, user_uuid)
        """
        )
        logging.info("✓ ReplacingMergeTree таблица users создана")
    else:
        logging.info("✓ ReplacingMergeTree таблица users уже существует")

    # Создаем Materialized View для users, если её нет
    if "users_mv" not in existing_table_names:
        logging.info("Создание Materialized View для users...")
        client.command(
            """
            CREATE MATERIALIZED VIEW debezium.users_mv TO debezium.users AS
            SELECT
                JSONExtractInt(JSONExtractString(JSONExtractString(payload, 'payload'), 'after'), 'id') AS user_id,
                JSONExtractString(JSONExtractString(JSONExtractString(payload, 'payload'), 'after'), 'user_uuid') AS user_uuid,
                JSONExtractString(JSONExtractString(JSONExtractString(payload, 'payload'), 'after'), 'name') AS name,
                JSONExtractString(JSONExtractString(JSONExtractString(payload, 'payload'), 'after'), 'email') AS email,
                JSONExtractInt(JSONExtractString(JSONExtractString(payload, 'payload'), 'after'), 'age') AS age,
                JSONExtractString(JSONExtractString(JSONExtractString(payload, 'payload'), 'after'), 'gender') AS gender,
                JSONExtractString(JSONExtractString(JSONExtractString(payload, 'payload'), 'after'), 'country') AS country,
                JSONExtractString(JSONExtractString(JSONExtractString(payload, 'payload'), 'after'), 'address') AS address,
                JSONExtractString(JSONExtractString(JSONExtractString(payload, 'payload'), 'after'), 'phone') AS phone,
                fromUnixTimestamp64Micro(JSONExtractUInt(JSONExtractString(JSONExtractString(payload, 'payload'), 'after'), 'registered_at')) AS registered_at
            FROM debezium.users_kafka
            WHERE JSONExtractString(JSONExtractString(payload, 'payload'), 'op') IN ('c', 'u', 'r')
        """
        )
        logging.info("✓ Materialized View users_mv создана")
    else:
        logging.info("✓ Materialized View users_mv уже существует")

    # Создаем Kafka Engine таблицу для telemetry_events, если её нет
    if "telemetry_events_kafka" not in existing_table_names:
        logging.info("Создание Kafka Engine таблицы для telemetry_events...")
        client.command(
            f"""
            CREATE TABLE debezium.telemetry_events_kafka (
                payload String
            ) ENGINE = Kafka
            SETTINGS
                kafka_broker_list = '{kafka_broker}',
                kafka_topic_list = 'telemetry.public.telemetry_events',
                kafka_group_name = 'clickhouse_telemetry_consumer',
                kafka_format = 'JSONAsString',
                kafka_num_consumers = 1,
                kafka_thread_per_consumer = 1,
                kafka_skip_broken_messages = 1000,
                kafka_max_block_size = 1048576
        """
        )
        logging.info("✓ Kafka Engine таблица telemetry_events_kafka создана")
    else:
        logging.info("✓ Kafka Engine таблица telemetry_events_kafka уже существует")

    # Создаем ReplacingMergeTree таблицу для telemetry_events, если её нет
    if "telemetry_events" not in existing_table_names:
        logging.info("Создание ReplacingMergeTree таблицы для telemetry_events...")
        client.command(
            """
            CREATE TABLE debezium.telemetry_events (
                id Int64,
                event_uuid String,
                user_uuid String,
                prosthesis_type String,
                muscle_group String,
                signal_frequency Int32,
                signal_duration Int32,
                signal_amplitude Float64,
                created_ts DateTime,
                saved_ts DateTime
            ) ENGINE = ReplacingMergeTree(saved_ts)
            PARTITION BY (toYear(created_ts), toMonth(created_ts))
            ORDER BY (user_uuid, event_uuid, created_ts)
        """
        )
        logging.info("✓ ReplacingMergeTree таблица telemetry_events создана")
    else:
        logging.info("✓ ReplacingMergeTree таблица telemetry_events уже существует")

    # Создаем Materialized View для telemetry_events, если её нет
    if "telemetry_events_mv" not in existing_table_names:
        logging.info("Создание Materialized View для telemetry_events...")
        client.command(
            """
            CREATE MATERIALIZED VIEW debezium.telemetry_events_mv TO debezium.telemetry_events AS
            SELECT
                JSONExtractInt(JSONExtractString(JSONExtractString(payload, 'payload'), 'after'), 'id') AS id,
                JSONExtractString(JSONExtractString(JSONExtractString(payload, 'payload'), 'after'), 'event_uuid') AS event_uuid,
                JSONExtractString(JSONExtractString(JSONExtractString(payload, 'payload'), 'after'), 'user_uuid') AS user_uuid,
                JSONExtractString(JSONExtractString(JSONExtractString(payload, 'payload'), 'after'), 'prosthesis_type') AS prosthesis_type,
                JSONExtractString(JSONExtractString(JSONExtractString(payload, 'payload'), 'after'), 'muscle_group') AS muscle_group,
                JSONExtractInt(JSONExtractString(JSONExtractString(payload, 'payload'), 'after'), 'signal_frequency') AS signal_frequency,
                JSONExtractInt(JSONExtractString(JSONExtractString(payload, 'payload'), 'after'), 'signal_duration') AS signal_duration,
                JSONExtractFloat(JSONExtractString(JSONExtractString(payload, 'payload'), 'after'), 'signal_amplitude') AS signal_amplitude,
                fromUnixTimestamp64Micro(JSONExtractUInt(JSONExtractString(JSONExtractString(payload, 'payload'), 'after'), 'created_ts')) AS created_ts,
                fromUnixTimestamp64Micro(JSONExtractUInt(JSONExtractString(JSONExtractString(payload, 'payload'), 'after'), 'saved_ts')) AS saved_ts
            FROM debezium.telemetry_events_kafka
            WHERE JSONExtractString(JSONExtractString(payload, 'payload'), 'op') IN ('c', 'u', 'r')
        """
        )
        logging.info("✓ Materialized View telemetry_events_mv создана")
    else:
        logging.info("✓ Materialized View telemetry_events_mv уже существует")

    debezium_schema_initialized = True
    logging.info("✓ Схема debezium полностью инициализирована")


# Определяем класс конфигурации для параметров Keycloak
class KeycloakConfig:
    import os

    # Указываем адрес издателя токенов (realm) в Keycloak (из переменной окружения или localhost)
    keycloak_base_url: str = os.getenv("KEYCLOAK_URL", "http://localhost:8080")
    issuer: str = f"{keycloak_base_url}/realms/reports-realm"
    # Формируем URL для получения открытых ключей (JWKS) Keycloak
    jwks_url: str = f"{issuer}/protocol/openid-connect/certs"
    # Указываем ожидаемую аудиторию (client_id) токена для backend-а
    audience: str | None = "reports-api"
    # Указываем допустимые алгоритмы подписи токена
    algorithms: tuple[str, ...] = ("RS256",)


# Определяем асинхронную функцию для получения JWKS с сервера Keycloak
async def get_jwks() -> Dict[str, Any]:
    # Создаем асинхронный HTTP-клиент с таймаутом в 5 секунд
    async with httpx.AsyncClient(timeout=5) as client:
        # Выполняем GET-запрос на получение набора ключей
        response = await client.get(KeycloakConfig.jwks_url)
        # Бросаем исключение, если Keycloak вернул ошибку
        response.raise_for_status()
        # Возвращаем тело ответа в виде словаря
        return response.json()


# Определяем зависимость FastAPI для проверки JWT-токена в заголовке Authorization
async def verify_jwt(
    authorization: str = Header(default=None), jwks: Dict[str, Any] = Depends(get_jwks)
) -> Dict[str, Any]:
    # Проверяем, что заголовок Authorization присутствует и содержит схему Bearer
    if not authorization or not authorization.lower().startswith("bearer "):
        # Возвращаем ошибку 401, если токен отсутствует
        raise HTTPException(status_code=401, detail="Missing Bearer token")

    # Извлекаем сам токен из заголовка Authorization
    token = authorization.split(" ", 1)[1]
    # Пытаемся получить заголовок токена без проверки подписи
    try:
        header = jwt.get_unverified_header(token)
    # Обрабатываем любые ошибки парсинга заголовка токена
    except jwt_exceptions.PyJWTError as exc:
        # Возвращаем ошибку 401, если заголовок токена некорректен
        raise HTTPException(status_code=401, detail="Invalid token header") from exc

    logging.info("Token header kid: %s", header.get("kid"))

    # Ищем подходящий ключ в JWKS по идентификатору ключа (kid)
    key_dict = next((k for k in jwks.get("keys", []) if k.get("kid") == header.get("kid")), None)
    # Проверяем, что ключ найден
    if not key_dict:
        # Возвращаем ошибку 401, если публичный ключ не найден
        logging.error("Public key not found for kid: %s", header.get("kid"))
        raise HTTPException(status_code=401, detail="Token signature key not found")

    logging.info("Key found for kid: %s", header.get("kid"))

    # Преобразуем найденный JWK в объект RSA-ключа
    public_key = RSAAlgorithm.from_jwk(json.dumps(key_dict))

    # Пытаемся декодировать и проверить токен с использованием публичного ключа
    try:
        # Получаем payload без проверки для диагностики
        unverified_payload = jwt.decode(token, options={"verify_signature": False})
        logging.info("Token payload audience: %s", unverified_payload.get("aud"))
        logging.info("Token payload issuer: %s", unverified_payload.get("iss"))
        logging.info("Token payload azp (authorized party): %s", unverified_payload.get("azp"))

        # Пробуем разные варианты issuer (внутренний и публичный)
        possible_issuers = [
            KeycloakConfig.issuer,  # Внутренний URL (http://keycloak:8080/realms/reports-realm)
            "http://localhost:8080/realms/reports-realm",  # Публичный URL
        ]

        payload = None
        last_error = None

        for issuer in possible_issuers:
            try:
                logging.info("Trying to decode token with issuer=%s", issuer)
                # Декодируем токен БЕЗ проверки audience, так как публичный клиент reports-frontend
                # не включает audience в токен по умолчанию
                payload = jwt.decode(
                    token,
                    public_key,
                    algorithms=list(KeycloakConfig.algorithms),
                    # Не проверяем audience для публичных клиентов
                    options={"verify_aud": False},
                    issuer=issuer,
                )
                logging.info("Token decoded successfully with issuer=%s", issuer)
                break
            except jwt_exceptions.InvalidIssuerError as e:
                last_error = e
                continue  # Пробуем следующий issuer

        if payload is None:
            logging.error("Failed to decode token with any issuer. Last error: %s", last_error)
            raise HTTPException(status_code=401, detail="Invalid token issuer")

        # Дополнительная проверка: токен должен быть выдан для reports-frontend
        if payload.get("azp") not in ["reports-frontend", "reports-api"]:
            logging.error("Token not issued for expected client. azp=%s", payload.get("azp"))
            raise HTTPException(status_code=401, detail="Token not issued for this application")
    # Обрабатываем ошибку истечения срока действия токена
    except jwt_exceptions.ExpiredSignatureError as exc:
        # Возвращаем ошибку 401 при просроченном токене
        logging.error("Token expired: %s", exc)
        raise HTTPException(status_code=401, detail="Token expired") from exc
    # Обрабатываем ошибки, связанные с аудиториями или издателем токена
    except (jwt_exceptions.InvalidAudienceError, jwt_exceptions.InvalidIssuerError) as exc:
        # Возвращаем ошибку 401 при неверных параметрах токена
        logging.error("Invalid token claims: %s", exc)
        logging.error("Token issuer from token: %s", jwt.decode(token, options={"verify_signature": False}).get("iss"))
        logging.error("Expected issuer: %s", KeycloakConfig.issuer)
        raise HTTPException(status_code=401, detail="Invalid token claims") from exc
    # Обрабатываем любые другие ошибки валидации токена
    except jwt_exceptions.PyJWTError as exc:
        # Возвращаем ошибку 401, если токен некорректен по другим причинам
        logging.error("Invalid token: %s", exc)
        raise HTTPException(status_code=401, detail="Invalid token") from exc

    # Возвращаем полезную нагрузку токена, если проверка успешно прошла
    return payload


@app.get("/")
async def root():
    """Корневой эндпоинт, возвращающий имя сервиса."""
    return {"service": "reports_api"}


# Описываем маршрут GET /reports, который требует валидный JWT
@app.get("/reports")
async def get_reports(payload: Dict[str, Any] = Depends(verify_jwt)) -> Dict[str, Any]:
    # Логируем полезную нагрузку токена в формате JSON
    logging.info("JWT payload: %s", json.dumps(payload))
    # Возвращаем полезную нагрузку в ответе API
    return {"payload": payload}


# Описываем маршрут GET /jwt, который возвращает содержимое JWT токена
@app.get("/jwt")
async def get_jwt(authorization: str = Header(default=None)) -> Dict[str, Any]:
    # Проверяем наличие заголовка Authorization
    if not authorization:
        # Если заголовок отсутствует, возвращаем null
        return {"jwt": None}

    # Проверяем, что заголовок содержит схему Bearer
    if not authorization.lower().startswith("bearer "):
        # Если схема неверная, возвращаем null
        return {"jwt": None}

    # Извлекаем токен из заголовка
    token = authorization.split(" ", 1)[1]

    # Пытаемся декодировать токен без проверки подписи (для отображения содержимого)
    try:
        # Декодируем токен без проверки подписи
        payload = jwt.decode(token, options={"verify_signature": False})

        # Возвращаем содержимое токена
        return {"jwt": payload}
    except jwt_exceptions.PyJWTError as exc:
        # Если токен некорректен, возвращаем ошибку
        logging.error("Failed to decode JWT: %s", exc)
        return {"jwt": None, "error": str(exc)}


# ===== Модели данных для эндпоинта /report =====


class ReportRequest(BaseModel):
    """Модель запроса для генерации отчета."""

    model_config = {"populate_by_name": True}  # Позволяет использовать как schema, так и data_schema

    user_uuid: Optional[str] = Field(default=None, description="UUID пользователя (если не указан, берётся из JWT)")
    start_ts: Optional[datetime] = Field(default=None, description="Начало отчетного периода")
    end_ts: Optional[datetime] = Field(default=None, description="Конец отчетного периода")
    data_schema: str = Field(
        default="default", description="Схема для чтения данных: 'default' или 'debezium'", alias="schema"
    )


class ProsthesisStats(BaseModel):
    """Статистика по одному протезу."""

    prosthesis_type: str = Field(description="Тип протеза")
    events_count: int = Field(description="Количество событий")
    total_duration: int = Field(description="Общая длительность сигналов (мс)")
    avg_amplitude: float = Field(description="Средняя амплитуда сигнала")
    avg_frequency: float = Field(description="Средняя частота сигнала (Гц)")


class ReportResponse(BaseModel):
    """Модель ответа с отчетом по пользователю."""

    user_name: str = Field(description="Имя пользователя")
    user_email: str = Field(description="Email пользователя")
    total_events: int = Field(description="Всего событий за период")
    total_duration: int = Field(description="Общая длительность сигналов (мс)")
    prosthesis_stats: List[ProsthesisStats] = Field(description="Статистика по каждому протезу")


def get_clickhouse_client():
    """Создает подключение к ClickHouse."""
    import os

    # Получаем параметры подключения из переменных окружения
    clickhouse_host = os.getenv("CLICKHOUSE_HOST", "localhost")
    clickhouse_port = int(os.getenv("CLICKHOUSE_PORT", "8123"))
    clickhouse_user = os.getenv("CLICKHOUSE_USER", "default")
    clickhouse_password = os.getenv("CLICKHOUSE_PASSWORD", "clickhouse_password")

    return clickhouse_connect.get_client(
        host=clickhouse_host, port=clickhouse_port, username=clickhouse_user, password=clickhouse_password
    )


async def generate_report_data(
    user_uuid: str, start_ts: Optional[datetime], end_ts: Optional[datetime], schema: str
) -> ReportResponse:
    """
    Генерирует отчёт по пользователю за указанный период.

    Args:
        user_uuid: UUID пользователя
        start_ts: Начало отчётного периода
        end_ts: Конец отчётного периода
        schema: Схема для чтения данных ('default' или 'debezium')

    Returns:
        ReportResponse: Отчёт с статистикой по пользователю
    """
    # Валидация параметра schema
    if schema not in ["default", "debezium"]:
        raise HTTPException(status_code=400, detail="Параметр schema должен быть 'default' или 'debezium'")

    minio = get_minio_client()
    bucket_name = "reports"

    # Формируем имя папки для пользователя с учётом схемы
    user_folder = f"{schema}/{user_uuid}"

    # Формируем имя файла на основе временных параметров
    if start_ts and end_ts:
        start_str = start_ts.strftime("%Y-%m-%dT%H-%M-%S")
        end_str = end_ts.strftime("%Y-%m-%dT%H-%M-%S")
        file_name = f"{user_folder}/{start_str}__{end_str}.json"
    elif start_ts:
        start_str = start_ts.strftime("%Y-%m-%dT%H-%M-%S")
        file_name = f"{user_folder}/{start_str}__none.json"
    elif end_ts:
        end_str = end_ts.strftime("%Y-%m-%dT%H-%M-%S")
        file_name = f"{user_folder}/none__{end_str}.json"
    else:
        file_name = f"{user_folder}/all_time.json"

    # Больше не проверяем кэш - всегда генерируем новый отчёт
    # Проверка кэша теперь выполняется на фронтенде через nginx reverse proxy

    # Генерируем отчёт из ClickHouse
    client = get_clickhouse_client()

    # Определяем таблицы в зависимости от схемы
    if schema == "debezium":
        users_table = "debezium.users"
        telemetry_table = "debezium.telemetry_events"
        time_field = "created_ts"
        user_id_field = "user_uuid"  # В debezium используется user_uuid
    else:
        users_table = "default.users"  # Явно указываем схему default
        telemetry_table = "default.telemetry_events"  # Явно указываем схему default
        time_field = "created_ts"  # В default тоже используется created_ts
        user_id_field = "user_uuid"  # В default тоже используем user_uuid

    # Получаем информацию о пользователе
    user_query = f"""
    SELECT name, email
    FROM {users_table}
    WHERE {user_id_field} = {{user_uuid:String}}
    """

    user_result = client.query(user_query, parameters={"user_uuid": user_uuid})

    if not user_result.result_rows:
        raise HTTPException(status_code=404, detail=f"Пользователь с UUID {user_uuid} не найден в схеме {schema}")

    user_name, user_email = user_result.result_rows[0]

    # Формируем запрос для общей статистики
    total_query = f"""
    SELECT 
        COUNT(*) as total_events,
        SUM(signal_duration) as total_duration
    FROM {telemetry_table}
    WHERE {user_id_field} = {{user_uuid:String}}
    """

    params = {"user_uuid": user_uuid}

    if start_ts:
        total_query += f" AND {time_field} >= {{start_ts:DateTime}}"
        params["start_ts"] = start_ts

    if end_ts:
        total_query += f" AND {time_field} < {{end_ts:DateTime}}"
        params["end_ts"] = end_ts

    total_result = client.query(total_query, parameters=params)
    total_events, total_duration = total_result.result_rows[0]

    # Если нет событий, возвращаем пустой отчёт
    if total_events == 0:
        report = ReportResponse(
            user_name=user_name, user_email=user_email, total_events=0, total_duration=0, prosthesis_stats=[]
        )
    else:
        # Получаем статистику по каждому протезу
        prosthesis_query = f"""
        SELECT 
            prosthesis_type,
            COUNT(*) as events_count,
            SUM(signal_duration) as total_duration,
            AVG(signal_amplitude) as avg_amplitude,
            AVG(signal_frequency) as avg_frequency
        FROM {telemetry_table}
        WHERE {user_id_field} = {{user_uuid:String}}
        """

        if start_ts:
            prosthesis_query += f" AND {time_field} >= {{start_ts:DateTime}}"

        if end_ts:
            prosthesis_query += f" AND {time_field} < {{end_ts:DateTime}}"

        prosthesis_query += " GROUP BY prosthesis_type ORDER BY events_count DESC"

        prosthesis_result = client.query(prosthesis_query, parameters=params)

        # Формируем список статистики по протезам
        prosthesis_stats = []
        for prosthesis_type, events_count, duration, avg_amplitude, avg_frequency in prosthesis_result.result_rows:
            prosthesis_stats.append(
                ProsthesisStats(
                    prosthesis_type=prosthesis_type,
                    events_count=events_count,
                    total_duration=int(duration),
                    avg_amplitude=float(avg_amplitude),
                    avg_frequency=float(avg_frequency),
                )
            )

        report = ReportResponse(
            user_name=user_name,
            user_email=user_email,
            total_events=total_events,
            total_duration=int(total_duration or 0),
            prosthesis_stats=prosthesis_stats,
        )

    # Сохраняем отчёт в MinIO
    # TTL настроен на уровне бакета (7 дней) через lifecycle policy в init-minio.sh
    try:
        report_json = report.model_dump_json(indent=2)
        report_bytes = report_json.encode("utf-8")

        minio.put_object(
            bucket_name=bucket_name,
            object_name=file_name,
            data=io.BytesIO(report_bytes),
            length=len(report_bytes),
            content_type="application/json",
        )
        logging.info(f"Отчёт сохранён в MinIO: {file_name}")
    except Exception as e:
        logging.error(f"Ошибка при сохранении отчёта в MinIO: {e}")

    return report


@app.post("/reports", response_model=ReportResponse)
async def create_report(request: ReportRequest, jwt_payload: Dict[str, Any] = Depends(verify_jwt)):
    """
    Генерирует отчёт по пользователю за указанный период с кешированием в MinIO.

    Требует JWT-токен в заголовке Authorization.

    Права доступа:
    - administrators: может смотреть любые отчёты
    - prosthetic_users: может смотреть только свой отчёт
    - остальные: доступ запрещён

    Args:
        request: Параметры запроса (user_uuid, start_ts, end_ts, schema)
        jwt_payload: Декодированный JWT-токен (автоматически проверяется через Depends)

    Returns:
        ReportResponse: Отчёт с статистикой по пользователю
    """
    # Получаем роли пользователя
    # Сначала пробуем новое поле realm_roles, затем старое realm_access.roles
    roles = jwt_payload.get("realm_roles", [])
    if not roles:
        realm_access = jwt_payload.get("realm_access", {})
        roles = realm_access.get("roles", [])

    # Получаем UUID пользователя из JWT
    # Сначала проверяем external_uuid (для LDAP-пользователей), затем sub (для локальных пользователей)
    jwt_user_uuid = jwt_payload.get("external_uuid") or jwt_payload.get("sub")

    if not jwt_user_uuid:
        raise HTTPException(status_code=401, detail="JWT-токен не содержит UUID пользователя (external_uuid или sub)")

    # Определяем user_uuid для отчёта
    if request.user_uuid:
        # Если user_uuid указан в запросе, проверяем права
        if "administrators" in roles:
            # Администратор может смотреть любые отчёты
            target_user_uuid = request.user_uuid
        elif "prosthetic_users" in roles:
            # prosthetic_users может смотреть только свой отчёт
            if request.user_uuid != jwt_user_uuid:
                raise HTTPException(status_code=403, detail="У вас нет прав для просмотра отчёта другого пользователя")
            target_user_uuid = request.user_uuid
        else:
            # Нет ни administrators, ни prosthetic_users
            raise HTTPException(status_code=403, detail="У вас нет прав для просмотра отчётов")
    else:
        # Если user_uuid не указан, используем UUID из JWT
        if "administrators" in roles or "prosthetic_users" in roles:
            target_user_uuid = jwt_user_uuid
        else:
            raise HTTPException(status_code=403, detail="У вас нет прав для просмотра отчётов")

    # Генерируем отчёт
    report = await generate_report_data(
        user_uuid=target_user_uuid, start_ts=request.start_ts, end_ts=request.end_ts, schema=request.data_schema
    )

    return report


# Запускаем приложение, если файл выполняется напрямую
if __name__ == "__main__":
    # Импортируем asyncio и uvicorn для запуска сервера
    import asyncio
    from uvicorn import Config, Server

    # Создаем конфигурацию сервера
    config = Config(app, host="0.0.0.0", port=3003)
    # Создаем экземпляр сервера
    server = Server(config)
    # Запускаем сервер с asyncio.run
    asyncio.run(server.serve())
