#!/bin/bash
set -e

echo "Запуск Airflow Standalone..."

# Запускаем Airflow в standalone режиме
# Аутентификация отключена - все пользователи имеют права администратора
exec airflow standalone
