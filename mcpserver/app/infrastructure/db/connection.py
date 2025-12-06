from collections.abc import AsyncGenerator

from sqlalchemy import event
from sqlalchemy.engine import Engine

# from sqlalchemy.engine import Engine
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlmodel import SQLModel  # , create_engine

from app.core.settings import getAppSettings

settings = getAppSettings()
connect_args = {"check_same_thread": False, "timeout": 10}

# sync_engine: Engine = create_engine(SQLALCHEMY_DATABASE_URL, echo=True, future=True)
# async_engine: AsyncEngine = AsyncEngine(sync_engine)
async_engine: AsyncEngine = create_async_engine(
    settings.database_url,
    # echo=True,
    connect_args=connect_args,
    execution_options={"sqlite_raw_colnames": True},
)

AsyncSessionLocal = async_sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=async_engine,
    expire_on_commit=False,  # Recommended for async
)


async def get_session_local() -> async_sessionmaker[AsyncSession]:
    return AsyncSessionLocal


@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    """
    Sets the SQLite journal mode to WAL for new connections.
    """
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL;")
    cursor.execute("PRAGMA synchronous=NORMAL;")  # Opcional: mejora el rendimiento
    cursor.close()


async def setup_database_models():
    async with async_engine.begin() as conn:
        # await conn.run_sync(SQLModel.metadata.drop_all)
        await conn.run_sync(SQLModel.metadata.create_all)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session
