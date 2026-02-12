"""Keycloak OIDC client for authentication."""

import base64
import hashlib
import json
import logging
import secrets
from typing import Any, Dict, Optional, Tuple
from urllib.parse import urlencode

import httpx
import jwt
from jwt.algorithms import RSAAlgorithm

from config import settings

logger = logging.getLogger(__name__)


class KeycloakClient:
    """Клиент для работы с Keycloak OIDC."""
    
    def __init__(self):
        """Инициализация клиента Keycloak."""
        # Внутренний URL для server-to-server запросов
        self.realm_url = f"{settings.keycloak_url}/realms/{settings.keycloak_realm}"
        self.token_endpoint = f"{self.realm_url}/protocol/openid-connect/token"
        self.userinfo_endpoint = f"{self.realm_url}/protocol/openid-connect/userinfo"
        self.jwks_url = f"{self.realm_url}/protocol/openid-connect/certs"
        # ВАЖНО: logout_endpoint использует внутренний URL, так как это server-to-server запрос
        # frontendUrl в Keycloak realm настроен на публичный URL, поэтому issuer в токенах будет корректным
        self.logout_endpoint = f"{self.realm_url}/protocol/openid-connect/logout"
        
        # Публичный URL для браузера (authorization endpoint)
        self.public_realm_url = f"{settings.keycloak_public_url}/realms/{settings.keycloak_realm}"
        self.auth_endpoint = f"{self.public_realm_url}/protocol/openid-connect/auth"
        
        # Кэш для JWKS (публичные ключи)
        self._jwks_cache: Optional[Dict[str, Any]] = None
    
    def _generate_pkce_pair(self) -> Tuple[str, str]:
        """
        Генерация PKCE code_verifier и code_challenge.
        
        Returns:
            Tuple[code_verifier, code_challenge]
        """
        # Генерируем code_verifier (43-128 символов)
        code_verifier = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode('utf-8').rstrip('=')
        
        # Вычисляем code_challenge = BASE64URL(SHA256(code_verifier))
        code_challenge_bytes = hashlib.sha256(code_verifier.encode('utf-8')).digest()
        code_challenge = base64.urlsafe_b64encode(code_challenge_bytes).decode('utf-8').rstrip('=')
        
        return code_verifier, code_challenge
    
    def get_authorization_url(
        self,
        redirect_uri: str,
        state: Optional[str] = None,
        scope: str = "openid profile email",
    ) -> Tuple[str, str]:
        """
        Получение URL для авторизации через Keycloak с PKCE.
        
        Args:
            redirect_uri: URL для редиректа после авторизации (callback URL)
            state: State параметр для защиты от CSRF
            scope: Запрашиваемые scope (по умолчанию: openid profile email)
        
        Returns:
            Tuple[URL для редиректа, code_verifier для обмена кода на токен]
        """
        # Генерируем PKCE параметры
        code_verifier, code_challenge = self._generate_pkce_pair()
        
        params = {
            "client_id": settings.client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",  # Authorization Code Flow
            "scope": scope,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",  # SHA-256
        }
        
        if state:
            params["state"] = state
        
        auth_url = f"{self.auth_endpoint}?{urlencode(params)}"
        return auth_url, code_verifier
    
    async def exchange_code_for_tokens(
        self,
        code: str,
        redirect_uri: str,
        code_verifier: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Обмен authorization code на access token и refresh token с PKCE.
        
        Args:
            code: Authorization code от Keycloak
            redirect_uri: Redirect URI (должен совпадать с тем, что был в authorization request)
            code_verifier: PKCE code_verifier (если используется PKCE)
        
        Returns:
            Словарь с токенами: access_token, refresh_token, expires_in, и т.д.
        """
        data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
            "client_id": settings.client_id,
        }
        
        # Добавляем PKCE code_verifier
        if code_verifier:
            data["code_verifier"] = code_verifier
        
        # Если есть client_secret, добавляем его
        if settings.client_secret:
            data["client_secret"] = settings.client_secret
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.token_endpoint,
                data=data,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            
            if response.status_code != 200:
                logger.error(f"Failed to exchange code for tokens: {response.text}")
                raise Exception(f"Token exchange failed: {response.status_code}")
            
            return response.json()
    
    async def refresh_access_token(self, refresh_token: str) -> Dict[str, Any]:
        """
        Обновление access token с помощью refresh token.
        
        Args:
            refresh_token: Refresh token
        
        Returns:
            Словарь с новыми токенами
        """
        data = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": settings.client_id,
        }
        
        if settings.client_secret:
            data["client_secret"] = settings.client_secret
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.token_endpoint,
                data=data,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            
            if response.status_code != 200:
                logger.error(f"Failed to refresh token: {response.text}")
                raise Exception(f"Token refresh failed: {response.status_code}")
            
            return response.json()
    
    async def get_jwks(self) -> Dict[str, Any]:
        """
        Получение JWKS (JSON Web Key Set) от Keycloak.
        
        Returns:
            JWKS словарь
        """
        # Используем кэш, если он есть
        if self._jwks_cache:
            return self._jwks_cache
        
        async with httpx.AsyncClient() as client:
            response = await client.get(self.jwks_url)
            response.raise_for_status()
            
            self._jwks_cache = response.json()
            return self._jwks_cache
    
    async def verify_token(self, token: str) -> Dict[str, Any]:
        """
        Проверка и декодирование JWT токена.
        
        Args:
            token: JWT access token
        
        Returns:
            Декодированный payload токена
        """
        # Получаем JWKS
        jwks = await self.get_jwks()
        
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
        
        # Декодируем и проверяем токен
        # Пробуем оба варианта issuer (внутренний и публичный)
        for issuer_url in [self.realm_url, self.public_realm_url]:
            try:
                payload = jwt.decode(
                    token,
                    public_key,
                    algorithms=["RS256"],
                    issuer=issuer_url,
                    options={"verify_aud": False},  # Не проверяем audience для публичных клиентов
                )
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
        logger.error("Invalid token: no valid issuer found")
        raise Exception("Invalid token")
    
    async def get_user_info(self, access_token: str) -> Dict[str, Any]:
        """
        Получение информации о пользователе из Keycloak UserInfo endpoint.
        
        Args:
            access_token: Access token
        
        Returns:
            Информация о пользователе
        """
        async with httpx.AsyncClient() as client:
            response = await client.get(
                self.userinfo_endpoint,
                headers={"Authorization": f"Bearer {access_token}"},
            )
            
            if response.status_code != 200:
                logger.error(f"Failed to get user info: {response.text}")
                raise Exception(f"UserInfo request failed: {response.status_code}")
            
            return response.json()
    
    async def logout(
        self,
        refresh_token: str,
    ) -> bool:
        """
        Завершение сессии в Keycloak (logout).
        
        Args:
            refresh_token: Refresh token пользователя
        
        Returns:
            True если logout успешен, False в противном случае
        """
        try:
            async with httpx.AsyncClient() as client:
                data = {
                    "client_id": settings.client_id,
                    "refresh_token": refresh_token,
                }
                
                # Если есть client_secret, добавляем его
                if settings.client_secret:
                    data["client_secret"] = settings.client_secret
                
                response = await client.post(
                    self.logout_endpoint,
                    data=data,
                )
                
                if response.status_code == 204:
                    logger.info("Keycloak session terminated successfully")
                    return True
                else:
                    logger.warning(f"Keycloak logout returned status {response.status_code}: {response.text}")
                    return False
                    
        except Exception as e:
            logger.error(f"Failed to logout from Keycloak: {e}")
            return False


# Создаем глобальный экземпляр клиента Keycloak
keycloak_client = KeycloakClient()
