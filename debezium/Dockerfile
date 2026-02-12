# Dockerfile для Debezium Connect с автоматической инициализацией коннекторов
# Наследуемся от официального образа Debezium Connect версии 2.7.3
FROM debezium/connect:2.7.3.Final

# Устанавливаем необходимые утилиты для проверки готовности и работы со скриптами
USER root
RUN microdnf install -y jq curl && microdnf clean all
USER kafka

# Копируем конфигурации коннекторов
COPY --chown=kafka:kafka crm-connector-config.json /tmp/crm-connector-config.json
COPY --chown=kafka:kafka telemetry-connector-config.json /tmp/telemetry-connector-config.json

# Копируем скрипт инициализации
COPY --chown=kafka:kafka init-connector.sh /usr/local/bin/init-connector.sh
RUN chmod +x /usr/local/bin/init-connector.sh

# Копируем entrypoint-скрипт, который запускает Kafka Connect и инициализирует коннекторы
COPY --chown=kafka:kafka docker-entrypoint-wrapper.sh /usr/local/bin/docker-entrypoint-wrapper.sh
RUN chmod +x /usr/local/bin/docker-entrypoint-wrapper.sh

# Используем wrapper как entrypoint
ENTRYPOINT ["/usr/local/bin/docker-entrypoint-wrapper.sh"]
CMD ["start"]
