"""Модуль для проверки JWT-токенов от Keycloak."""

import json
import logging
from typing import Any, Dict, Optional

import httpx
import jwt
from jwt.algorithms import RSAAlgorithm

logger = logging.getLogger(__name__)

# Кэш для JWKS (публичные ключи)
_jwks_cache: Optional[Dict[str, Any]] = None


async def get_jwks(keycloak_url: str, realm: str) -> Dict[str, Any]:
    """
    Получение JWKS (JSON Web Key Set) от Keycloak.
    
    Args:
        keycloak_url: URL Keycloak сервера
        realm: Имя realm
    
    Returns:
        JWKS (набор публичных ключей)
    """
    global _jwks_cache
    
    # Если кэш пуст, загружаем JWKS
    if _jwks_cache is None:
        jwks_url = f"{keycloak_url}/realms/{realm}/protocol/openid-connect/certs"
        
        async with httpx.AsyncClient() as client:
            response = await client.get(jwks_url)
            response.raise_for_status()
            
            _jwks_cache = response.json()
    
    return _jwks_cache


async def verify_jwt_token(
    token: str,
    keycloak_url: str,
    realm: str,
    expected_issuers: Optional[list[str]] = None
) -> Dict[str, Any]:
    """
    Проверка и декодирование JWT токена от Keycloak.
    
    Args:
        token: JWT access token
        keycloak_url: URL Keycloak сервера
        realm: Имя realm
        expected_issuers: Список допустимых issuer (если None, проверяется автоматически)
    
    Returns:
        Декодированный payload токена
    
    Raises:
        Exception: Если токен невалиден
    """
    # Получаем JWKS
    jwks = await get_jwks(keycloak_url, realm)
    
    # Получаем заголовок токена
    try:
        header = jwt.get_unverified_header(token)
    except Exception as e:
        logger.error(f"Failed to get token header: {e}")
        raise Exception("Invalid token header")
    
    # Находим ключ по kid
    kid = header.get("kid")
    key_dict = next((k for k in jwks.get("keys", []) if k.get("kid") == kid), None)
    
    if not key_dict:
        logger.error(f"Public key not found for kid: {kid}")
        raise Exception("Token signature key not found")
    
    # Преобразуем JWK в RSA ключ
    public_key = RSAAlgorithm.from_jwk(json.dumps(key_dict))
    
    # Формируем список возможных issuer
    if expected_issuers is None:
        expected_issuers = [
            f"{keycloak_url}/realms/{realm}",  # Внутренний URL
            f"http://localhost:8080/realms/{realm}",  # Публичный URL
        ]
    
    # Декодируем и проверяем токен с разными issuer
    for issuer in expected_issuers:
        try:
            payload = jwt.decode(
                token,
                public_key,
                algorithms=["RS256"],
                issuer=issuer,
                options={"verify_aud": False},  # Не проверяем audience для публичных клиентов
            )
            logger.info(f"Token verified successfully with issuer: {issuer}")
            return payload
        except jwt.InvalidIssuerError:
            continue  # Пробуем следующий issuer
        except jwt.ExpiredSignatureError:
            logger.error("Token expired")
            raise Exception("Token expired")
        except jwt.InvalidTokenError as e:
            logger.error(f"Invalid token: {e}")
            raise Exception("Invalid token")
    
    # Если ни один issuer не подошёл
    logger.error(f"Invalid token: no valid issuer found (tried: {expected_issuers})")
    raise Exception("Invalid token: invalid issuer")


def extract_user_info(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Извлечение информации о пользователе из payload токена.
    
    Args:
        payload: Декодированный payload JWT токена
    
    Returns:
        Словарь с информацией о пользователе
    """
    return {
        "sub": payload.get("sub"),
        "username": payload.get("preferred_username"),
        "email": payload.get("email"),
        "first_name": payload.get("given_name"),
        "last_name": payload.get("family_name"),
        "realm_roles": payload.get("realm_roles") or payload.get("realm_access", {}).get("roles", []),
        "client_roles": payload.get("resource_access", {}),
    }
