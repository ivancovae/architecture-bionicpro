# Dockerfile для MinIO с автоматической настройкой политик
FROM minio/minio:latest

# Устанавливаем mc (MinIO Client) для настройки политик
RUN curl -L https://dl.min.io/client/mc/release/linux-amd64/mc -o /usr/local/bin/mc && \
    chmod +x /usr/local/bin/mc

# Копируем скрипт инициализации
COPY init-minio.sh /usr/local/bin/init-minio.sh
RUN chmod +x /usr/local/bin/init-minio.sh

# Копируем политику и OIDC конфигурацию
COPY reports-policy.json /etc/minio/reports-policy.json

# Устанавливаем переменные окружения по умолчанию
ENV MINIO_ROOT_USER=minio_user
ENV MINIO_ROOT_PASSWORD=minio_password

# Запускаем MinIO с инициализацией
ENTRYPOINT ["/usr/local/bin/init-minio.sh"]
