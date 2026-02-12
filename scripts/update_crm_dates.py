#!/usr/bin/env python3
"""
Скрипт для обновления дат регистрации в crm.csv
Изменяет все даты на период с 1 сентября 2025 по 11 февраля 2026
"""

import csv
import random
from datetime import datetime, timedelta
from pathlib import Path


def generate_random_date(start_date: datetime, end_date: datetime) -> datetime:
    """Генерирует случайную дату в заданном диапазоне"""
    time_between = end_date - start_date
    days_between = time_between.days
    random_days = random.randrange(days_between)
    random_seconds = random.randrange(24 * 60 * 60)  # Случайное время в течение дня
    return start_date + timedelta(days=random_days, seconds=random_seconds)


def update_crm_dates(csv_file_path: str):
    """Обновляет даты регистрации в CSV файле"""
    # Диапазон дат: с 1 сентября 2025 по 11 февраля 2026
    start_date = datetime(2025, 9, 1)
    end_date = datetime(2026, 2, 11, 23, 59, 59)
    
    # Читаем исходный файл
    rows = []
    with open(csv_file_path, 'r', encoding='utf-8') as file:
        reader = csv.reader(file)
        header = next(reader)  # Читаем заголовок
        rows.append(header)
        
        # Находим индекс колонки registered_at
        registered_at_index = header.index('registered_at')
        
        # Обрабатываем каждую строку
        for row in reader:
            # Генерируем новую случайную дату
            new_date = generate_random_date(start_date, end_date)
            # Форматируем в том же формате, что и в исходном файле
            row[registered_at_index] = new_date.strftime('%Y-%m-%d %H:%M:%S')
            rows.append(row)
    
    # Записываем обновлённые данные обратно в файл
    with open(csv_file_path, 'w', encoding='utf-8', newline='') as file:
        writer = csv.writer(file)
        writer.writerows(rows)
    
    print(f"✅ Обновлено {len(rows) - 1} записей в {csv_file_path}")
    print(f"📅 Новый диапазон дат: {start_date.strftime('%Y-%m-%d')} - {end_date.strftime('%Y-%m-%d')}")


if __name__ == "__main__":
    # Путь к файлу CRM
    crm_file = Path(__file__).parent.parent / "crm_api" / "crm.csv"
    
    if not crm_file.exists():
        print(f"❌ Файл {crm_file} не найден!")
        exit(1)
    
    print(f"🔄 Обновление дат в файле: {crm_file}")
    update_crm_dates(str(crm_file))
