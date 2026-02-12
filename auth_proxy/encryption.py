"""Модуль для шифрования/дешифрования токенов в Redis."""

import base64
import os
from typing import Optional

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC


class TokenEncryption:
    """Класс для шифрования и дешифрования токенов."""
    
    def __init__(self, encryption_key: Optional[str] = None):
        """
        Инициализация шифрования.
        
        Args:
            encryption_key: Ключ шифрования (base64-encoded строка длиной 32 байта).
                           Если не задан, шифрование не используется.
        """
        self.encryption_key = encryption_key
        self.cipher = None
        
        if encryption_key:
            # Создаем Fernet cipher из ключа
            try:
                # Проверяем, что ключ в правильном формате (base64, 32 байта)
                key_bytes = base64.urlsafe_b64decode(encryption_key)
                if len(key_bytes) != 32:
                    raise ValueError(f"Ключ должен быть 32 байта, получено: {len(key_bytes)}")
                
                self.cipher = Fernet(encryption_key.encode() if isinstance(encryption_key, str) else encryption_key)
            except Exception as e:
                raise ValueError(f"Неверный формат ключа шифрования: {e}")
    
    def encrypt(self, data: str) -> str:
        """
        Шифрование данных.
        
        Args:
            data: Строка для шифрования
        
        Returns:
            Зашифрованная строка (или исходная, если шифрование отключено)
        """
        if not self.cipher:
            # Шифрование отключено, возвращаем данные как есть
            return data
        
        # Шифруем данные
        encrypted_bytes = self.cipher.encrypt(data.encode('utf-8'))
        # Возвращаем base64-encoded строку
        return base64.urlsafe_b64encode(encrypted_bytes).decode('utf-8')
    
    def decrypt(self, encrypted_data: str) -> str:
        """
        Дешифрование данных.
        
        Args:
            encrypted_data: Зашифрованная строка
        
        Returns:
            Расшифрованная строка (или исходная, если шифрование отключено)
        """
        if not self.cipher:
            # Шифрование отключено, возвращаем данные как есть
            return encrypted_data
        
        try:
            # Декодируем base64
            encrypted_bytes = base64.urlsafe_b64decode(encrypted_data.encode('utf-8'))
            # Дешифруем данные
            decrypted_bytes = self.cipher.decrypt(encrypted_bytes)
            return decrypted_bytes.decode('utf-8')
        except Exception as e:
            raise ValueError(f"Ошибка дешифрования: {e}")
    
    @staticmethod
    def generate_key() -> str:
        """
        Генерация нового ключа шифрования.
        
        Returns:
            Base64-encoded ключ (32 байта)
        """
        return Fernet.generate_key().decode('utf-8')


def derive_key_from_password(password: str, salt: Optional[bytes] = None) -> tuple[str, bytes]:
    """
    Генерация ключа шифрования из пароля с использованием PBKDF2.
    
    Args:
        password: Пароль для генерации ключа
        salt: Соль (если не задана, генерируется новая)
    
    Returns:
        Tuple (base64-encoded ключ, соль)
    """
    if salt is None:
        salt = os.urandom(16)
    
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100000,
    )
    key = base64.urlsafe_b64encode(kdf.derive(password.encode('utf-8')))
    return key.decode('utf-8'), salt
