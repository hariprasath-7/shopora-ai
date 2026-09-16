"""SQLAlchemy database setup.

SQLite remains convenient for local development/tests. Production should use
PostgreSQL via DATABASE_URL.
"""
from collections.abc import Generator
from pathlib import Path

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import settings


class Base(DeclarativeBase):
    pass


connect_args: dict = {}
engine_kwargs: dict = {"echo": settings.debug, "pool_pre_ping": True}

if settings.database_url.startswith("sqlite"):
    connect_args = {"check_same_thread": False}
    engine_kwargs["connect_args"] = connect_args
    # SQLite won't create a missing parent directory on its own, and `data/`
    # is gitignored, so a fresh clone would otherwise fail with a cryptic
    # "unable to open database file" the first time anything touches the DB.
    db_path = settings.database_url.removeprefix("sqlite:///")
    if db_path and db_path != ":memory:":
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
else:
    engine_kwargs.update({"pool_size": 10, "max_overflow": 20, "pool_timeout": 30})

engine = create_engine(settings.database_url, **engine_kwargs)


if settings.database_url.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def _enable_sqlite_foreign_keys(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Generator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def check_database() -> None:
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
