#!/usr/bin/env python3
"""Скрипт для импорта данных из PostgreSQL в ClickHouse.

Этот скрипт использует логику из Airflow DAG для импорта данных.
"""

import sys
from pathlib import Path

# Добавляем пути к модулям проекта
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "airflow" / "dags"))

# Импортируем функции из DAG
from import_olap_data import (
    get_clickhouse_client,
    create_olap_tables,
    import_users_data,
    import_telemetry_data,
    logger,
)


def import_data():
    """Импортирует данные из PostgreSQL в ClickHouse, используя логику из Airflow DAG."""

    print("=" * 80)
    print("Импорт данных в ClickHouse")
    print("=" * 80)

    # Получаем клиент ClickHouse
    print("\n1. Подключение к ClickHouse...")
    client = get_clickhouse_client()
    print("✓ Подключение к ClickHouse установлено")

    # Создаём таблицы
    print("\n2. Создание таблиц в ClickHouse...")
    create_olap_tables(client)
    print("✓ Таблицы созданы/проверены")

    # Импортируем пользователей (без временных фильтров - все пользователи)
    print("\n3. Импорт пользователей из CRM БД...")
    import_users_data(client, user_start_ts=None, user_end_ts=None)
    print("✓ Пользователи импортированы")

    # Импортируем телеметрию (без временных фильтров - все события)
    print("\n4. Импорт событий телеметрии из Telemetry БД...")
    import_telemetry_data(client, telemetry_start_ts=None, telemetry_end_ts=None)
    print("✓ События телеметрии импортированы")

    print("\n" + "=" * 80)
    print("✓ Импорт завершён успешно!")
    print("=" * 80)


if __name__ == "__main__":
    import_data()
