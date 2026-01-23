from collection.abc import AsyncGenerator
import uuid


from sqlalchemy import Column, String, Text, DateTime, ForeignKey
from sqlalchemy.dialect.postgresql import uuid
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, relationShip


DATABASE_URL="sqlite+aiosqlite:///./test.db"