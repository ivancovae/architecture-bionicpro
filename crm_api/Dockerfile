# Используем официальный образ Python 3.12 slim
FROM python:3.12-slim

# Устанавливаем рабочую директорию
WORKDIR /app

# Устанавливаем curl для healthcheck и uv для управления зависимостями
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir uv

# Копируем файл с зависимостями
COPY pyproject.toml .

# Устанавливаем зависимости через uv
RUN uv pip install --system -r pyproject.toml

# Копируем весь код микросервиса
COPY . .

# Открываем порт 3001 (порт из README.md)
EXPOSE 3001

# Запускаем приложение
CMD ["python", "main.py"]
