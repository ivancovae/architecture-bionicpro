# Dockerfile для Apache Airflow 3.1.3 в standalone режиме
FROM apache/airflow:3.1.3-python3.12

USER root
# Установка системных зависимостей
RUN apt-get update && apt-get install -y \
    curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

USER airflow

# Установка всех необходимых Python-зависимостей для ETL-процесса
RUN pip install --no-cache-dir \
    clickhouse-connect==0.7.19 \
    sqlmodel==0.0.22 \
    psycopg2-binary==2.9.9 \
    python-dateutil==2.9.0

# Создаём директорию для DAG'ов
RUN mkdir -p ~/airflow/dags

# Устанавливаем переменные окружения для standalone режима
ENV AIRFLOW_HOME=/home/airflow/airflow
ENV AIRFLOW__CORE__LOAD_EXAMPLES=false
ENV AIRFLOW__CORE__DAGS_FOLDER=/home/airflow/airflow/dags
ENV AIRFLOW__CORE__SIMPLE_AUTH_MANAGER_ALL_ADMINS=True

# Отключаем аутентификацию - все пользователи становятся администраторами
#ENV AIRFLOW__CORE__AUTH_MANAGER=airflow.auth.managers.simple_auth_manager.SimpleAuthManager
#ENV AIRFLOW__SIMPLE_AUTH_MANAGER__AUTH_ROLE=Admin

RUN airflow db migrate