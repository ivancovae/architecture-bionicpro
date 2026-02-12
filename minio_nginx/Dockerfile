# Dockerfile для nginx reverse proxy с поддержкой Lua (OpenResty)
# OpenResty - это nginx с встроенной поддержкой Lua для расширенной логики

FROM openresty/openresty:alpine

# Копируем конфигурацию nginx
COPY nginx.conf /usr/local/openresty/nginx/conf/nginx.conf

# Создаём директории для логов
RUN mkdir -p /var/log/nginx

# Открываем порт 9001 (порт для доступа к reverse proxy)
EXPOSE 9001

# Запускаем nginx в foreground-режиме
CMD ["/usr/local/openresty/bin/openresty", "-g", "daemon off;"]
