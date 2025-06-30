import os
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from .models import Base

# Путь к папке с данными и файлу БД
DATA_DIR = "data"
DB_FILE = "bot_database.db"
DB_PATH = os.path.join(DATA_DIR, DB_FILE)

# Убедимся, что папка data существует
os.makedirs(DATA_DIR, exist_ok=True)

# URL для асинхронного подключения к SQLite
DATABASE_URL = f"sqlite+aiosqlite:///{DB_PATH}"

# Создаем асинхронный движок
engine = create_async_engine(DATABASE_URL, echo=False) # echo=True для дебага SQL запросов

# Создаем фабрику асинхронных сессий
async_session_factory = async_sessionmaker(engine, expire_on_commit=False)

async def create_db_and_tables():
    """Создает все таблицы в базе данных."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

async def get_async_session() -> AsyncSession:
    """Зависимость для получения асинхронной сессии."""
    async with async_session_factory() as session:
        yield session