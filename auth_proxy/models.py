"""Data models for auth_proxy service."""

from typing import Optional
from pydantic import BaseModel


class UserInfo(BaseModel):
    """Информация о пользователе из Keycloak access token."""
    
    has_session_cookie: bool                    # Есть ли session cookie
    is_authorized: bool                         # Авторизован ли пользователь
    username: Optional[str] = None              # Имя пользователя (preferred_username)
    email: Optional[str] = None                 # Email пользователя
    first_name: Optional[str] = None            # Имя (given_name)
    last_name: Optional[str] = None             # Фамилия (family_name)
    realm_roles: Optional[list[str]] = None     # Realm roles пользователя
    permissions: Optional[dict] = None          # Permissions (resource_access)
    sub: Optional[str] = None                   # Subject (user ID)
    external_uuid: Optional[str] = None         # UUID из LDAP (для LDAP-пользователей)


class SessionData(BaseModel):
    """Данные сессии пользователя, хранящиеся в Redis."""
    
    session_id: str                             # ID сессии
    user_id: str                                # ID пользователя (sub из JWT)
    username: str                               # Имя пользователя
    access_token: str                           # Access token от Keycloak
    refresh_token: str                          # Refresh token от Keycloak
    expires_at: int                             # Время истечения access token (Unix timestamp)
    created_at: int                             # Время создания сессии (Unix timestamp)
    last_used_at: int                           # Время последнего использования сессии (Unix timestamp)


class ProxyRequest(BaseModel):
    """Запрос для проксирования к upstream сервису."""
    
    upstream_uri: str                           # URL upstream сервиса, к которому проксируем запрос
    method: str = "GET"                         # HTTP метод для upstream запроса (по умолчанию GET)
    redirect_to_sign_in: bool = False           # Редиректить ли на /sign_in при отсутствии авторизации
    body: Optional[dict] = None                 # Тело запроса для POST/PUT/PATCH (опционально)
