#!/usr/bin/env python3
"""
Скрипт для исправления user_uuid в signal_samples.csv.

Проблема: в signal_samples.csv для некоторых user_id указан неправильный user_uuid,
который не совпадает с user_uuid из crm.csv.

Решение: читаем crm.csv, создаём словарь user_id -> user_uuid, затем обновляем
signal_samples.csv, заменяя user_uuid на правильный из crm.csv.
"""

import csv
from pathlib import Path

# Пути к файлам
PROJECT_ROOT = Path(__file__).parent.parent
CRM_CSV = PROJECT_ROOT / "crm_api" / "crm.csv"
SIGNAL_SAMPLES_CSV = PROJECT_ROOT / "telemetry_api" / "signal_samples.csv"
SIGNAL_SAMPLES_BACKUP = PROJECT_ROOT / "telemetry_api" / "signal_samples.csv.backup"


def main():
    print("=" * 80)
    print("Исправление user_uuid в signal_samples.csv")
    print("=" * 80)

    # Шаг 1: Читаем crm.csv и создаём словарь user_id -> user_uuid
    print(f"\n1. Читаем {CRM_CSV}...")
    user_id_to_uuid = {}

    with open(CRM_CSV, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            user_id = int(row["id"])
            user_uuid = row["user_uuid"]
            user_id_to_uuid[user_id] = user_uuid

    print(f"   ✓ Загружено {len(user_id_to_uuid)} пользователей из crm.csv")

    # Шаг 2: Создаём резервную копию signal_samples.csv
    print(f"\n2. Создаём резервную копию {SIGNAL_SAMPLES_CSV}...")
    import shutil

    shutil.copy2(SIGNAL_SAMPLES_CSV, SIGNAL_SAMPLES_BACKUP)
    print(f"   ✓ Резервная копия создана: {SIGNAL_SAMPLES_BACKUP}")

    # Шаг 3: Читаем signal_samples.csv и исправляем user_uuid
    print(f"\n3. Исправляем user_uuid в {SIGNAL_SAMPLES_CSV}...")
    rows = []
    fixed_count = 0
    error_count = 0

    with open(SIGNAL_SAMPLES_CSV, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames

        for row in reader:
            user_id = int(row["user_id"])
            current_uuid = row["user_uuid"]

            # Проверяем, есть ли user_id в crm.csv
            if user_id not in user_id_to_uuid:
                print(f"   ⚠ user_id={user_id} не найден в crm.csv, пропускаем")
                error_count += 1
                rows.append(row)
                continue

            correct_uuid = user_id_to_uuid[user_id]

            # Если user_uuid не совпадает, исправляем
            if current_uuid != correct_uuid:
                print(f"   ✓ user_id={user_id}: {current_uuid} -> {correct_uuid}")
                row["user_uuid"] = correct_uuid
                fixed_count += 1

            rows.append(row)

    # Шаг 4: Записываем исправленные данные обратно в signal_samples.csv
    print(f"\n4. Записываем исправленные данные в {SIGNAL_SAMPLES_CSV}...")
    with open(SIGNAL_SAMPLES_CSV, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"   ✓ Записано {len(rows)} строк")

    # Итоги
    print("\n" + "=" * 80)
    print("Итоги:")
    print(f"  - Исправлено записей: {fixed_count}")
    print(f"  - Ошибок (user_id не найден в crm.csv): {error_count}")
    print(f"  - Резервная копия: {SIGNAL_SAMPLES_BACKUP}")
    print("=" * 80)


if __name__ == "__main__":
    main()
