from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from app.config import DATABASE_URL
from contextlib import asynccontextmanager

engine = create_async_engine(DATABASE_URL, echo=False)
async_session = sessionmaker(
    engine, expire_on_commit=False, class_=AsyncSession
)
Base = declarative_base()

@asynccontextmanager
async def get_session() -> AsyncSession: # type: ignore
    async with async_session() as session:
        yield session

async def close_engine() -> None:
    await engine.dispose()
