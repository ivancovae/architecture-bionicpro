# Используем официальный образ Python
FROM python:3.12-slim

# Устанавливаем рабочую директорию
WORKDIR /app

# Устанавливаем curl для healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

# Устанавливаем uv для управления зависимостями
RUN pip install --no-cache-dir uv

# Копируем pyproject.toml для установки зависимостей
COPY pyproject.toml .

# Устанавливаем зависимости через uv
RUN uv pip install --system -r pyproject.toml

# Копируем весь код приложения
COPY . .

# Открываем порт для auth_proxy
EXPOSE 3000

# Запускаем приложение
CMD ["python", "main.py"]
