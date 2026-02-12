"""Entry point for running auth_proxy service."""

import asyncio
import logging

from uvicorn import Config, Server

from app import app
from config import settings

# Настройка логирования
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

logger = logging.getLogger(__name__)


if __name__ == "__main__":
    logger.info(f"Starting auth_proxy on {settings.auth_proxy_host}:{settings.auth_proxy_port}")
    logger.info(f"Expected Keycloak at: {settings.keycloak_url}")
    logger.info(f"Expected Keycloak Realm: {settings.keycloak_realm}")
    logger.info(f"Expected Redis: {settings.redis_host}:{settings.redis_port}")
    logger.info(f"Session lifetime: {settings.session_lifetime_seconds} seconds")
    logger.info(f"Session rotation: {settings.enable_session_rotation}")
    logger.info(f"Single session per user: {settings.single_session_per_user}")

    # Создаем конфигурацию сервера
    config = Config(app, host=settings.auth_proxy_host, port=settings.auth_proxy_port, log_level="info")

    # Создаем и запускаем сервер
    server = Server(config)
    asyncio.run(server.serve())
