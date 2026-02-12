"""Основной модуль CRM API для регистрации пользователей интернет-магазина"""

import asyncio
import csv
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import Field, Session, SQLModel, create_engine, select, text

# Настраиваем базовый уровень логирования на INFO
logging.basicConfig(level=logging.INFO)


# Настройки подключения к базе данных
class DatabaseConfig:
    """Конфигурация подключения к PostgreSQL базе данных CRM."""

    import os

    host: str = os.getenv("DB_HOST", "localhost")  # Хост базы данных (из переменной окружения или localhost)
    port: int = int(os.getenv("DB_PORT", "5444"))  # Порт базы данных (из переменной окружения или 5444)
    database: str = os.getenv("DB_NAME", "crm_db")  # Имя базы данных (из переменной окружения)
    user: str = os.getenv("DB_USER", "crm_user")  # Пользователь БД (из переменной окружения)
    password: str = os.getenv("DB_PASSWORD", "crm_password")  # Пароль пользователя (из переменной окружения)

    @classmethod
    def get_connection_string(cls) -> str:
        """Формирует строку подключения к PostgreSQL."""
        return f"postgresql://{cls.user}:{cls.password}@{cls.host}:{cls.port}/{cls.database}"


# Модель для входных данных при регистрации пользователя
class IncomingUser(SQLModel):
    """Модель для создания нового пользователя (входные данные API)."""

    name: str = Field(max_length=100, description="Полное имя пользователя")
    email: str = Field(max_length=100, description="Email пользователя (должен быть уникальным)")
    age: Optional[int] = Field(default=None, description="Возраст пользователя")
    gender: Optional[str] = Field(default=None, max_length=10, description="Пол пользователя")
    country: Optional[str] = Field(default=None, max_length=100, description="Страна проживания")
    address: Optional[str] = Field(default=None, max_length=255, description="Адрес пользователя")
    phone: Optional[str] = Field(default=None, max_length=25, description="Номер телефона")


# Модель пользователя (User) для базы данных и API
class User(IncomingUser, table=True):
    """
    Модель пользователя интернет-магазина.
    Используется как для таблицы БД, так и для Pydantic-валидации.
    Наследуется от IncomingUser.
    """

    __tablename__ = "users"  # Имя таблицы в БД

    id: Optional[int] = Field(default=None, primary_key=True, description="Уникальный идентификатор пользователя")
    user_uuid: str = Field(max_length=36, unique=True, index=True, description="UUID пользователя (формат Keycloak)")
    registered_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Дата и время регистрации пользователя в БД (UTC)",
    )


# Создаем движок базы данных
engine = create_engine(DatabaseConfig.get_connection_string(), echo=True)  # Логируем все SQL-запросы


def create_db_and_tables():
    """Создает таблицы в базе данных, если они не существуют."""
    SQLModel.metadata.create_all(engine)


def get_session():
    """Dependency для получения сессии базы данных."""
    with Session(engine) as session:
        yield session


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Обработчик lifespan для инициализации и очистки ресурсов."""
    # Startup
    logging.info("Запуск CRM API...")
    create_db_and_tables()
    logging.info("Таблицы БД созданы/проверены")

    yield

    # Shutdown
    logging.info("Завершение работы CRM API")


# Создаем экземпляр FastAPI с lifespan
app = FastAPI(title="CRM API", description="API для регистрации пользователей интернет-магазина", lifespan=lifespan)

# Добавляем промежуточное ПО для поддержки CORS-запросов
app.add_middleware(
    CORSMiddleware,  # Класс промежуточного ПО для CORS
    allow_origins=["*"],  # Разрешаем запросы со всех доменов
    allow_credentials=True,  # Разрешаем передачу cookies и авторизационных заголовков
    allow_methods=["*"],  # Разрешаем все HTTP-методы
    allow_headers=["*"],  # Разрешаем любые заголовки в запросах
)


@app.post("/register", response_model=User, status_code=201)
async def register_user(user_data: IncomingUser, session: Session = Depends(get_session)) -> User:
    """
    Регистрация нового пользователя в системе.

    Args:
        user_data: Данные нового пользователя
        session: Сессия базы данных

    Returns:
        User: Созданный пользователь с присвоенным ID и временем регистрации

    Raises:
        HTTPException: 400 если email уже существует в системе
    """
    # Проверяем, существует ли пользователь с таким email
    statement = select(User).where(User.email == user_data.email)
    existing_user = session.exec(statement).first()

    if existing_user:
        logging.warning(f"Попытка регистрации с существующим email: {user_data.email}")
        raise HTTPException(status_code=400, detail=f"Пользователь с email {user_data.email} уже зарегистрирован")

    # Создаем нового пользователя
    new_user = User(
        user_uuid=str(uuid.uuid4()),
        name=user_data.name,
        email=user_data.email,
        age=user_data.age,
        gender=user_data.gender,
        country=user_data.country,
        address=user_data.address,
        phone=user_data.phone,
        registered_at=datetime.now(timezone.utc),
    )

    # Сохраняем в БД
    session.add(new_user)
    session.commit()
    session.refresh(new_user)

    logging.info(f"Зарегистрирован новый пользователь: {new_user.email} (ID: {new_user.id})")

    return new_user


@app.get("/")
async def root():
    """Корневой эндпоинт, возвращающий имя сервиса."""
    return {"service": "crm_api"}


@app.get("/health")
async def health_check():
    """Проверка работоспособности API."""
    return {"status": "healthy", "service": "CRM API"}


@app.post("/populate_base")
async def populate_base(session: Session = Depends(get_session)):
    """
    Пересоздает схему БД и наполняет её тестовыми данными из crm.csv.

    Args:
        session: Сессия базы данных

    Returns:
        dict: Статистика загрузки данных
    """
    # Путь к CSV-файлу
    csv_path = Path(__file__).parent / "crm.csv"

    if not csv_path.exists():
        raise HTTPException(status_code=404, detail=f"CSV-файл не найден: {csv_path}")

    # Очищаем таблицы (не удаляем их, чтобы не ломать Debezium-коннекторы)
    logging.info("Очистка таблицы users...")
    session.exec(text("TRUNCATE TABLE users RESTART IDENTITY CASCADE"))
    session.commit()
    logging.info("Таблица users очищена")

    # Читаем и загружаем данные из CSV
    users_loaded = 0

    # Используем asyncio для асинхронной обработки
    await asyncio.sleep(0)  # Уступаем управление event loop

    with open(csv_path, "r", encoding="utf-8") as csvfile:
        reader = csv.DictReader(csvfile)

        for row in reader:
            # Парсим дату регистрации из CSV
            registered_at = datetime.strptime(row["registered_at"], "%Y-%m-%d %H:%M:%S")
            registered_at = registered_at.replace(tzinfo=timezone.utc)

            # Создаем пользователя из строки CSV (без ID - пусть БД генерирует автоматически)
            user = User(
                user_uuid=row["user_uuid"],
                name=row["name"],
                email=row["email"],
                age=int(row["age"]) if row.get("age") else None,
                gender=row.get("gender") or None,
                country=row.get("country") or None,
                address=row.get("address") or None,
                phone=row.get("phone") or None,
                registered_at=registered_at,
            )

            session.add(user)
            users_loaded += 1

            # Периодически уступаем управление event loop
            if users_loaded % 100 == 0:
                await asyncio.sleep(0)

    # Сохраняем все изменения
    session.commit()

    logging.info(f"Загружено {users_loaded} пользователей из CSV")

    return {
        "status": "success",
        "message": "База данных пересоздана и наполнена тестовыми данными",
        "users_loaded": users_loaded,
    }


# Запускаем приложение, если файл выполняется напрямую
if __name__ == "__main__":
    import asyncio
    from uvicorn import Config, Server

    # Создаем конфигурацию сервера
    config = Config(app, host="0.0.0.0", port=3001)
    # Создаем экземпляр сервера
    server = Server(config)
    # Запускаем сервер с asyncio.run
    asyncio.run(server.serve())
