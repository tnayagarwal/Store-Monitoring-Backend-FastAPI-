from __future__ import annotations

from contextlib import contextmanager
import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, DeclarativeBase


POSTGRES_USER = os.getenv("PGUSER", "postgres")
POSTGRES_PASSWORD = os.getenv("PGPASSWORD", "TaNaY")
POSTGRES_HOST = os.getenv("PGHOST", "localhost")
POSTGRES_PORT = int(os.getenv("PGPORT", "5432"))
POSTGRES_DB = os.getenv("PGDATABASE", "assignment")

DATABASE_URL = (
    f"postgresql+psycopg://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"
)


class Base(DeclarativeBase):
    pass


# PostgreSQL engine
engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


@contextmanager
def get_session():
    session = SessionLocal()
    try:
        yield session
        session.close()
    except Exception:
        session.rollback()
        session.close()
        raise


def ensure_database_exists() -> None:
    """Create the target database if it does not exist.

    Connects to the default 'postgres' database and checks pg_database.
    """
    default_url = (
        f"postgresql+psycopg://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/postgres"
    )
    default_engine = create_engine(default_url, isolation_level="AUTOCOMMIT", pool_pre_ping=True)
    with default_engine.connect() as conn:
        exists = conn.execute(
            text("SELECT 1 FROM pg_database WHERE datname = :name"), {"name": POSTGRES_DB}
        ).scalar()
        if not exists:
            conn.execute(text(f"CREATE DATABASE {POSTGRES_DB}"))
    default_engine.dispose()


