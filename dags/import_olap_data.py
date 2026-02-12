"""Скрипт для импорта данных из CRM и Telemetry БД в ClickHouse OLAP."""

import argparse
import logging
from datetime import datetime, timezone
from typing import Optional
from dateutil.relativedelta import relativedelta

import clickhouse_connect
from sqlmodel import Session, create_engine, select

# Импортируем ORM-модели из других микросервисов
import sys
from pathlib import Path

# Добавляем пути к модулям
sys.path.insert(0, str(Path(__file__).parent.parent))

from crm_api.main import User as CRMUser
from telemetry_api.main import TelemetryEvent

# Настраиваем логирование
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


# Настройки подключения к БД (из переменных окружения или значения по умолчанию)
import os

CRM_DB_HOST = os.getenv("CRM_DB_HOST", "localhost")
CRM_DB_PORT = os.getenv("CRM_DB_PORT", "5444")
CRM_DB_NAME = os.getenv("CRM_DB_NAME", "crm_db")
CRM_DB_USER = os.getenv("CRM_DB_USER", "crm_user")
CRM_DB_PASSWORD = os.getenv("CRM_DB_PASSWORD", "crm_password")
CRM_DB_URL = f"postgresql://{CRM_DB_USER}:{CRM_DB_PASSWORD}@{CRM_DB_HOST}:{CRM_DB_PORT}/{CRM_DB_NAME}"

TELEMETRY_DB_HOST = os.getenv("TELEMETRY_DB_HOST", "localhost")
TELEMETRY_DB_PORT = os.getenv("TELEMETRY_DB_PORT", "5445")
TELEMETRY_DB_NAME = os.getenv("TELEMETRY_DB_NAME", "telemetry_db")
TELEMETRY_DB_USER = os.getenv("TELEMETRY_DB_USER", "telemetry_user")
TELEMETRY_DB_PASSWORD = os.getenv("TELEMETRY_DB_PASSWORD", "telemetry_password")
TELEMETRY_DB_URL = f"postgresql://{TELEMETRY_DB_USER}:{TELEMETRY_DB_PASSWORD}@{TELEMETRY_DB_HOST}:{TELEMETRY_DB_PORT}/{TELEMETRY_DB_NAME}"

CLICKHOUSE_HOST = os.getenv("CLICKHOUSE_HOST", "localhost")
CLICKHOUSE_PORT = int(os.getenv("CLICKHOUSE_PORT", "8123"))
CLICKHOUSE_USER = os.getenv("CLICKHOUSE_USER", "default")
CLICKHOUSE_PASSWORD = os.getenv("CLICKHOUSE_PASSWORD", "clickhouse_password")  # Пароль для ClickHouse


def get_clickhouse_client():
    """Создает подключение к ClickHouse."""
    return clickhouse_connect.get_client(
        host=CLICKHOUSE_HOST, port=CLICKHOUSE_PORT, username=CLICKHOUSE_USER, password=CLICKHOUSE_PASSWORD
    )


def create_olap_tables(client):
    """Создает таблицы в ClickHouse, если они не существуют."""

    # Таблица пользователей (Join Table Engine для быстрых JOIN-операций)
    # Join по user_uuid (String для совместимости с Join Engine)
    users_table_sql = """
    CREATE TABLE IF NOT EXISTS users (
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

    # Таблица телеметрических событий (ReplacingMergeTree для соответствия схеме debezium)
    telemetry_table_sql = """
    CREATE TABLE IF NOT EXISTS telemetry_events (
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

    logger.info("Создание таблицы users...")
    client.command(users_table_sql)
    logger.info("Таблица users создана/проверена")

    logger.info("Создание таблицы telemetry_events...")
    client.command(telemetry_table_sql)
    logger.info("Таблица telemetry_events создана/проверена")


def import_users_data(client):
    """Импортирует данные пользователей из CRM БД в ClickHouse."""

    logger.info("Подключение к CRM БД...")
    crm_engine = create_engine(CRM_DB_URL)

    with Session(crm_engine) as session:
        # Читаем всех пользователей из CRM БД
        statement = select(CRMUser)
        users = session.exec(statement).all()

        logger.info(f"Найдено {len(users)} пользователей в CRM БД")

        if not users:
            logger.warning("Нет пользователей для импорта")
            return

        # Очищаем таблицу users в ClickHouse (для полной перезаливки)
        logger.info("Очистка таблицы users в ClickHouse...")
        client.command("TRUNCATE TABLE users")

        # Подготавливаем данные для вставки (список списков)
        # Важно: ClickHouse хранит DateTime в UTC, поэтому конвертируем naive datetime в UTC
        column_names = [
            "user_id",
            "user_uuid",
            "name",
            "email",
            "age",
            "gender",
            "country",
            "address",
            "phone",
            "registered_at",
        ]
        users_data = []
        for user in users:
            # Если datetime naive (без timezone), считаем его UTC
            reg_at = user.registered_at
            if reg_at and reg_at.tzinfo is None:
                from datetime import timezone

                reg_at = reg_at.replace(tzinfo=timezone.utc)

            users_data.append(
                [
                    user.id,
                    user.user_uuid,
                    user.name,
                    user.email,
                    user.age,
                    user.gender,
                    user.country,
                    user.address,
                    user.phone,
                    reg_at,
                ]
            )

        # Вставляем данные в ClickHouse
        logger.info(f"Вставка {len(users_data)} пользователей в ClickHouse...")
        client.insert("users", users_data, column_names=column_names)
        logger.info("Данные пользователей успешно импортированы")


def import_telemetry_data(
    client, telemetry_start_ts: Optional[datetime] = None, telemetry_end_ts: Optional[datetime] = None
):
    """
    Импортирует телеметрические данные из Telemetry БД в ClickHouse.

    Args:
        client: Клиент ClickHouse
        telemetry_start_ts: Начало интервала времени (включительно)
        telemetry_end_ts: Конец интервала времени (не включительно)
    """

    logger.info("Подключение к Telemetry БД...")
    telemetry_engine = create_engine(TELEMETRY_DB_URL)

    with Session(telemetry_engine) as session:
        # Формируем запрос с учетом временных границ
        statement = select(TelemetryEvent)

        if telemetry_start_ts is not None:
            statement = statement.where(TelemetryEvent.created_ts >= telemetry_start_ts)
            logger.info(f"Фильтр: created_ts >= {telemetry_start_ts}")

        if telemetry_end_ts is not None:
            statement = statement.where(TelemetryEvent.created_ts < telemetry_end_ts)
            logger.info(f"Фильтр: created_ts < {telemetry_end_ts}")

        # Читаем события из Telemetry БД
        events = session.exec(statement).all()

        logger.info(f"Найдено {len(events)} телеметрических событий")

        if not events:
            logger.warning("Нет событий для импорта")
            return

        # Удаляем старые события из этого интервала в ClickHouse
        if telemetry_start_ts is None and telemetry_end_ts is None:
            # Если фильтры не указаны, очищаем всю таблицу
            logger.info("Очистка таблицы telemetry_events в ClickHouse...")
            client.command("TRUNCATE TABLE telemetry_events")
            logger.info("Таблица очищена")
        else:
            # Если указаны фильтры, удаляем только события из этого интервала
            logger.info("Удаление старых событий из интервала в ClickHouse...")
            delete_conditions = []

            if telemetry_start_ts is not None:
                delete_conditions.append(f"created_ts >= '{telemetry_start_ts.strftime('%Y-%m-%d %H:%M:%S')}'")

            if telemetry_end_ts is not None:
                delete_conditions.append(f"created_ts < '{telemetry_end_ts.strftime('%Y-%m-%d %H:%M:%S')}'")

            if delete_conditions:
                delete_sql = f"ALTER TABLE telemetry_events DELETE WHERE {' AND '.join(delete_conditions)}"
                client.command(delete_sql)
                logger.info("Старые события удалены")

        # Подготавливаем данные для вставки (список списков)
        # Важно: ClickHouse хранит DateTime в UTC, поэтому конвертируем naive datetime в UTC
        column_names = [
            "id",
            "event_uuid",
            "user_uuid",
            "prosthesis_type",
            "muscle_group",
            "signal_frequency",
            "signal_duration",
            "signal_amplitude",
            "created_ts",
            "saved_ts",
        ]
        events_data = []
        for event in events:
            # Если datetime naive (без timezone), считаем его UTC
            created = event.created_ts
            if created and created.tzinfo is None:
                from datetime import timezone

                created = created.replace(tzinfo=timezone.utc)

            sav_ts = event.saved_ts
            if sav_ts and sav_ts.tzinfo is None:
                from datetime import timezone

                sav_ts = sav_ts.replace(tzinfo=timezone.utc)

            events_data.append(
                [
                    event.id,
                    event.event_uuid,
                    event.user_uuid,
                    event.prosthesis_type,
                    event.muscle_group,
                    event.signal_frequency,
                    event.signal_duration,
                    event.signal_amplitude,
                    created,
                    sav_ts,
                ]
            )

        # Вставляем данные в ClickHouse
        logger.info(f"Вставка {len(events_data)} событий в ClickHouse...")
        client.insert("telemetry_events", events_data, column_names=column_names)
        logger.info("Телеметрические данные успешно импортированы")


def cleanup_orphaned_events(client):
    """Удаляет события телеметрии для пользователей, которых больше нет в БД."""

    logger.info("Проверка и удаление событий для несуществующих пользователей...")

    # Получаем список всех user_uuid из таблицы users
    result = client.query("SELECT user_uuid FROM users")
    existing_user_uuids = {row[0] for row in result.result_rows}

    logger.info(f"Найдено {len(existing_user_uuids)} пользователей в OLAP БД")

    if not existing_user_uuids:
        logger.warning("Нет пользователей в OLAP БД, удаляем все события")
        client.command("TRUNCATE TABLE telemetry_events")
        return

    # Удаляем события для пользователей, которых нет в списке
    # Для ClickHouse используем NOT IN с подзапросом
    delete_sql = """
    ALTER TABLE telemetry_events DELETE 
    WHERE user_uuid NOT IN (SELECT user_uuid FROM users)
    """
    client.command(delete_sql)
    logger.info("Удалены события для несуществующих пользователей")


def import_olap_data(telemetry_start_ts: Optional[datetime] = None, telemetry_end_ts: Optional[datetime] = None):
    """
    Основная функция импорта данных в OLAP БД.

    Args:
        telemetry_start_ts: Начало интервала времени для телеметрии
        telemetry_end_ts: Конец интервала времени для телеметрии
    """

    logger.info("=" * 60)
    logger.info("Начало импорта данных в ClickHouse OLAP БД")
    logger.info("=" * 60)

    try:
        # Подключаемся к ClickHouse
        client = get_clickhouse_client()
        logger.info("Подключение к ClickHouse установлено")

        # Создаем таблицы, если их нет
        create_olap_tables(client)

        # Импортируем данные пользователей
        import_users_data(client)

        # Импортируем телеметрические данные
        import_telemetry_data(client, telemetry_start_ts, telemetry_end_ts)

        # Примечание: cleanup_orphaned_events закомментирован, так как он удаляет валидные события
        # Все события в Telemetry DB должны быть импортированы в ClickHouse
        # cleanup_orphaned_events(client)

        logger.info("=" * 60)
        logger.info("Импорт данных завершен успешно")
        logger.info("=" * 60)

    except Exception as e:
        logger.error(f"Ошибка при импорте данных: {e}", exc_info=True)
        raise


# ===== Airflow DAG =====

try:
    from airflow import DAG

    # В Airflow 3.x используем новый импорт из провайдеров
    try:
        from airflow.providers.standard.operators.python import PythonOperator
    except ImportError:
        # Fallback для Airflow 2.x
        from airflow.operators.python import PythonOperator

    # Функция-обёртка для Airflow оператора
    def import_previous_month(**context):
        """
        Импортирует данные телеметрии за предыдущий месяц.
        Вызывается Airflow DAG 1 числа каждого месяца в 01:00 UTC.
        """
        # Получаем дату выполнения DAG (execution_date)
        execution_date = context.get("execution_date")

        # Если execution_date не передан (например, при ручном запуске), используем текущую дату
        if execution_date is None:
            execution_date = datetime.now(timezone.utc)

        # Вычисляем начало предыдущего месяца (00:00:00 UTC)
        start_of_previous_month = execution_date.replace(
            day=1, hour=0, minute=0, second=0, microsecond=0
        ) - relativedelta(months=1)

        # Вычисляем начало текущего месяца (00:00:00 UTC) = конец периода импорта
        start_of_current_month = execution_date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        logger.info(f"Импорт данных за период: {start_of_previous_month} - {start_of_current_month}")

        # Вызываем функцию импорта с указанными временными границами
        import_olap_data(telemetry_start_ts=start_of_previous_month, telemetry_end_ts=start_of_current_month)

    # Определяем DAG
    default_args = {
        "owner": "airflow",  # Владелец DAG
        "depends_on_past": False,  # DAG не зависит от успешности предыдущих запусков
        "email_on_failure": False,  # Не отправлять email при ошибке
        "email_on_retry": False,  # Не отправлять email при повторной попытке
        "retries": 1,  # Количество повторных попыток при ошибке
    }

    # Создаём DAG с расписанием: 1 число каждого месяца в 01:00 UTC
    dag = DAG(
        "import_olap_data_monthly",  # ID DAG
        default_args=default_args,  # Параметры по умолчанию
        description="Ежемесячный импорт данных телеметрии в ClickHouse OLAP",  # Описание DAG
        schedule_interval="0 1 1 * *",  # Cron-выражение (в Airflow 2.x используется schedule_interval)
        start_date=datetime(2025, 1, 1, tzinfo=timezone.utc),  # Дата начала работы DAG: 1 января 2025 года
        catchup=True,  # Запускать пропущенные запуски (для загрузки исторических данных за 2025 год)
        tags=["olap", "clickhouse", "monthly"],  # Теги для фильтрации в UI
    )

    # Определяем единственный оператор в DAG
    import_task = PythonOperator(
        task_id="import_previous_month_data",  # ID задачи
        python_callable=import_previous_month,  # Функция для выполнения
        # provide_context удалён в Airflow 3.x (контекст передаётся автоматически)
        dag=dag,  # Привязываем к DAG
    )

except ImportError:
    # Если Airflow не установлен, DAG не создаётся
    logger.warning("Airflow не установлен, DAG не будет создан")
    dag = None


if __name__ == "__main__":
    # Если запускаем напрямую (не через Airflow), используем argparse для ручного запуска
    parser = argparse.ArgumentParser(description="Импорт данных в ClickHouse OLAP БД")
    parser.add_argument(
        "--telemetry_start_ts", type=str, help="Начало интервала времени для телеметрии (формат: YYYY-MM-DD HH:MM:SS)"
    )
    parser.add_argument(
        "--telemetry_end_ts", type=str, help="Конец интервала времени для телеметрии (формат: YYYY-MM-DD HH:MM:SS)"
    )

    args = parser.parse_args()

    # Парсим даты, если они указаны
    start_ts = None
    end_ts = None

    if args.telemetry_start_ts:
        start_ts = datetime.strptime(args.telemetry_start_ts, "%Y-%m-%d %H:%M:%S")
        logger.info(f"Установлен telemetry_start_ts: {start_ts}")

    if args.telemetry_end_ts:
        end_ts = datetime.strptime(args.telemetry_end_ts, "%Y-%m-%d %H:%M:%S")
        logger.info(f"Установлен telemetry_end_ts: {end_ts}")

    import_olap_data(telemetry_start_ts=start_ts, telemetry_end_ts=end_ts)
