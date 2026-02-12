#!/bin/bash
# Скрипт инициализации Airflow: создание базы данных и администратора

set -e

echo "Ожидание готовности базы данных Airflow..."
# Ждём, пока PostgreSQL станет доступен
for i in {1..30}; do
  if airflow db check > /dev/null 2>&1; then
    echo "✓ База данных Airflow готова (попытка $i)"
    break
  fi
  if [ $i -eq 30 ]; then
    echo "✗ База данных Airflow не готова после 30 попыток"
    exit 1
  fi
  echo "Ожидание базы данных Airflow... (попытка $i/30)"
  sleep 2
done

echo "Инициализация базы данных Airflow..."
airflow db migrate

echo "Создание пользователя airflow_admin через FAB..."
# Создаём администратора через FAB, если он ещё не существует
airflow users create \
    --username airflow_admin \
    --firstname Airflow \
    --lastname Admin \
    --role Admin \
    --email admin@example.com \
    --password airflow_password 2>&1 || echo "Пользователь airflow_admin уже существует или ошибка создания"

# Проверяем, что пользователь создан
echo "Проверка созданных пользователей..."
airflow users list

echo "✓ Инициализация Airflow завершена"
