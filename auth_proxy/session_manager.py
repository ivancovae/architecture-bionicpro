"""Session manager for Redis-based session storage."""

import json
import secrets
import time
from typing import Optional

import redis.asyncio as redis

from config import settings
from encryption import TokenEncryption
from models import SessionData


class SessionManager:
    """Менеджер сессий с использованием Redis."""
    
    def __init__(self):
        """Инициализация менеджера сессий."""
        # Создаем подключение к Redis
        self.redis_client: Optional[redis.Redis] = None
        # Инициализируем шифрование токенов
        self.encryption = TokenEncryption(settings.encryption_key)
    
    async def connect(self):
        """Подключение к Redis."""
        self.redis_client = await redis.Redis(
            host=settings.redis_host,
            port=settings.redis_port,
            db=settings.redis_db,
            password=settings.redis_password,
            decode_responses=True,  # Автоматически декодировать ответы в строки
        )
    
    async def disconnect(self):
        """Отключение от Redis."""
        if self.redis_client:
            await self.redis_client.close()
    
    def _generate_session_id(self) -> str:
        """Генерация уникального session ID."""
        # Генерируем криптографически стойкий случайный токен
        return secrets.token_urlsafe(32)
    
    def _session_key(self, session_id: str) -> str:
        """Получение ключа для хранения сессии в Redis."""
        return f"session:{session_id}"
    
    def _user_session_key(self, user_id: str) -> str:
        """Получение ключа для хранения session_id пользователя."""
        return f"user_session:{user_id}"
    
    async def create_session(
        self,
        user_id: str,
        username: str,
        access_token: str,
        refresh_token: str,
        expires_at: int,
    ) -> str:
        """
        Создание новой сессии для пользователя.
        
        Args:
            user_id: ID пользователя (sub из JWT)
            username: Имя пользователя
            access_token: Access token от Keycloak
            refresh_token: Refresh token от Keycloak
            expires_at: Время истечения access token (Unix timestamp)
        
        Returns:
            session_id: ID созданной сессии
        """
        # Если включен режим single session per user, удаляем старую сессию
        if settings.single_session_per_user:
            await self._delete_user_session(user_id)
        
        # Генерируем новый session ID
        session_id = self._generate_session_id()
        
        # Создаем данные сессии
        current_time = int(time.time())
        
        # Шифруем токены перед сохранением
        encrypted_access_token = self.encryption.encrypt(access_token)
        encrypted_refresh_token = self.encryption.encrypt(refresh_token)
        
        session_data = SessionData(
            session_id=session_id,
            user_id=user_id,
            username=username,
            access_token=encrypted_access_token,
            refresh_token=encrypted_refresh_token,
            expires_at=expires_at,
            created_at=current_time,
            last_used_at=current_time,
        )
        
        # Сохраняем сессию в Redis
        session_key = self._session_key(session_id)
        await self.redis_client.setex(
            session_key,
            settings.session_lifetime_seconds,
            session_data.model_dump_json(),
        )
        
        # Сохраняем связь user_id -> session_id
        user_session_key = self._user_session_key(user_id)
        await self.redis_client.setex(
            user_session_key,
            settings.session_lifetime_seconds,
            session_id,
        )
        
        return session_id
    
    async def get_session(self, session_id: str) -> Optional[SessionData]:
        """
        Получение данных сессии по session ID.
        
        Args:
            session_id: ID сессии
        
        Returns:
            SessionData или None, если сессия не найдена
        """
        session_key = self._session_key(session_id)
        session_json = await self.redis_client.get(session_key)
        
        if not session_json:
            return None
        
        # Парсим JSON и создаем объект SessionData
        session_data = SessionData.model_validate_json(session_json)
        
        # Если включен single_session_per_user, проверяем, что это текущая активная сессия
        if settings.single_session_per_user:
            user_session_key = self._user_session_key(session_data.user_id)
            current_session_id = await self.redis_client.get(user_session_key)
            
            # Если session_id не совпадает с текущим активным, инвалидируем сессию
            if current_session_id and current_session_id != session_id:
                await self.delete_session(session_id)
                return None
        
        # Дешифруем токены после чтения
        session_data.access_token = self.encryption.decrypt(session_data.access_token)
        session_data.refresh_token = self.encryption.decrypt(session_data.refresh_token)
        
        return session_data
    
    async def update_session(self, session_data: SessionData):
        """
        Обновление данных сессии в Redis.
        
        Args:
            session_data: Обновленные данные сессии
        """
        session_key = self._session_key(session_data.session_id)
        
        # Обновляем время последнего использования
        session_data.last_used_at = int(time.time())
        
        # Шифруем токены перед сохранением
        encrypted_data = session_data.model_copy()
        encrypted_data.access_token = self.encryption.encrypt(session_data.access_token)
        encrypted_data.refresh_token = self.encryption.encrypt(session_data.refresh_token)
        
        # Сохраняем обновленные данные с продлением TTL
        await self.redis_client.setex(
            session_key,
            settings.session_lifetime_seconds,
            encrypted_data.model_dump_json(),
        )
        
        # Продлеваем TTL для связи user_id -> session_id
        user_session_key = self._user_session_key(session_data.user_id)
        await self.redis_client.setex(
            user_session_key,
            settings.session_lifetime_seconds,
            session_data.session_id,
        )
    
    async def rotate_session(self, old_session_id: str) -> Optional[str]:
        """
        Ротация session ID (создание нового session_id, немедленное удаление старого).
        
        Args:
            old_session_id: Старый session ID
        
        Returns:
            Новый session ID или None, если старая сессия не найдена
        """
        # Получаем данные старой сессии
        session_data = await self.get_session(old_session_id)
        
        if not session_data:
            return None
        
        # Генерируем новый session ID
        new_session_id = self._generate_session_id()
        
        # Обновляем session_id в данных
        session_data.session_id = new_session_id
        
        # Сохраняем сессию с новым ID
        await self.update_session(session_data)
        
        # Обновляем связь user_id -> session_id (если включен single_session_per_user)
        if settings.single_session_per_user:
            user_session_key = self._user_session_key(session_data.user_id)
            await self.redis_client.set(user_session_key, new_session_id)
        
        # НЕМЕДЛЕННО удаляем старую сессию из Redis
        old_session_key = self._session_key(old_session_id)
        await self.redis_client.delete(old_session_key)
        
        return new_session_id
    
    async def delete_session(self, session_id: str):
        """
        Удаление сессии по session ID.
        
        Args:
            session_id: ID сессии
        """
        # Получаем данные сессии для удаления связи user_id -> session_id
        session_data = await self.get_session(session_id)
        
        # Удаляем сессию
        session_key = self._session_key(session_id)
        await self.redis_client.delete(session_key)
        
        # Удаляем связь user_id -> session_id (если это текущая сессия пользователя)
        if session_data:
            user_session_key = self._user_session_key(session_data.user_id)
            current_session_id = await self.redis_client.get(user_session_key)
            
            if current_session_id == session_id:
                await self.redis_client.delete(user_session_key)
    
    async def _delete_user_session(self, user_id: str):
        """
        Удаление активной сессии пользователя (для single session per user).
        
        Args:
            user_id: ID пользователя
        """
        # Получаем текущий session_id пользователя
        user_session_key = self._user_session_key(user_id)
        old_session_id = await self.redis_client.get(user_session_key)
        
        if old_session_id:
            # Удаляем старую сессию
            await self.delete_session(old_session_id)


# Создаем глобальный экземпляр менеджера сессий
session_manager = SessionManager()
