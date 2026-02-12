"""Зависимости для проверки авторизации в FastAPI."""

import logging
import os
from typing import Optional

from fastapi import Depends, Header, HTTPException

from keycloak_jwt import verify_jwt_token, extract_user_info

logger = logging.getLogger(__name__)

# Получаем настройки из переменных окружения
KEYCLOAK_URL = os.getenv("KEYCLOAK_URL", "http://keycloak:8080")
KEYCLOAK_REALM = os.getenv("KEYCLOAK_REALM", "reports-realm")


async def get_current_user(authorization: Optional[str] = Header(None)):
    """
    Dependency для получения текущего пользователя из JWT токена.
    
    Args:
        authorization: Заголовок Authorization с Bearer токеном
    
    Returns:
        Информация о пользователе из токена
    
    Raises:
        HTTPException: Если токен отсутствует или невалиден
    """
    if not authorization:
        logger.warning("Authorization header missing")
        raise HTTPException(status_code=401, detail="Authorization header missing")
    
    # Проверяем формат заголовка
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        logger.warning(f"Invalid authorization header format: {authorization[:50]}")
        raise HTTPException(status_code=401, detail="Invalid authorization header format")
    
    token = parts[1]
    
    # Проверяем токен
    try:
        payload = await verify_jwt_token(token, KEYCLOAK_URL, KEYCLOAK_REALM)
        user_info = extract_user_info(payload)
        logger.info(f"User authenticated: {user_info.get('username')}")
        return user_info
    except Exception as e:
        logger.error(f"Token verification failed: {e}")
        raise HTTPException(status_code=401, detail=f"Invalid token: {str(e)}")


async def get_optional_user(authorization: Optional[str] = Header(None)):
    """
    Dependency для получения пользователя из JWT токена (опционально).
    
    Если токен отсутствует или невалиден, возвращает None вместо ошибки.
    
    Args:
        authorization: Заголовок Authorization с Bearer токеном
    
    Returns:
        Информация о пользователе из токена или None
    """
    if not authorization:
        return None
    
    try:
        return await get_current_user(authorization)
    except HTTPException:
        return None
