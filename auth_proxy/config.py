"""Configuration for auth_proxy service."""

from typing import Optional
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Настройки auth_proxy сервиса."""
    
    # Redis settings
    redis_host: str = "localhost"  # Хост Redis сервера
    redis_port: int = 6379  # Порт Redis сервера
    redis_db: int = 0  # Номер базы данных Redis
    redis_password: Optional[str] = None  # Пароль для Redis (если требуется)
    
    # Encryption settings
    encryption_key: Optional[str] = None  # Ключ шифрования для токенов в Redis (base64, 32 байта)
    
    # Keycloak OIDC settings
    keycloak_url: str = "http://localhost:8080"  # URL Keycloak сервера (внутренний, для server-to-server запросов)
    keycloak_public_url: str = "http://localhost:8080"  # Публичный URL Keycloak для браузера
    keycloak_realm: str = "reports-realm"  # Имя realm в Keycloak
    client_id: str = "auth-proxy"  # Client ID для OIDC
    client_secret: Optional[str] = "auth-proxy-secret-key-12345"  # Client secret (для confidential clients)
    
    # Session settings
    session_cookie_name: str = "session_id"  # Имя cookie для session ID
    session_lifetime_seconds: int = 3600  # Время жизни сессии (по умолчанию 1 час)
    session_cookie_secure: bool = False  # Использовать Secure flag для cookie (True для HTTPS)
    session_cookie_samesite: str = "strict"  # SameSite policy: strict (теперь фронтенд на том же домене)
    session_cookie_httponly: bool = True  # HttpOnly flag для cookie
    session_cookie_path: str = "/"  # Path для cookie
    
    # Session rotation settings
    enable_session_rotation: bool = True  # Включить ротацию session ID при каждом запросе
    
    # Single session per user settings
    single_session_per_user: bool = True  # Разрешить только одну активную сессию на пользователя
    single_session_for_roles: list[str] = ["administrators"]  # Роли, для которых действует ограничение (если не для всех)
    
    # Auth proxy settings
    auth_proxy_host: str = "0.0.0.0"  # Хост для запуска auth_proxy
    auth_proxy_port: int = 3000  # Порт для запуска auth_proxy
    
    # Frontend URLs
    frontend_url: str = "http://bionicpro-frontend:5173"  # Внутренний URL фронтенда (Vite dev server) - используем имя сервиса в Docker
    frontend_public_url: str = "http://localhost:3000"  # Публичный URL фронтенда (через auth_proxy)
    
    class Config:
        env_file = ".env"  # Загружать настройки из .env файла
        env_prefix = "AUTH_PROXY_"  # Префикс для переменных окружения


# Создаем глобальный экземпляр настроек
settings = Settings()
