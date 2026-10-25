import os

from sqlalchemy import create_engine
from sqlalchemy.orm import (
    declarative_base,
    sessionmaker,
)


RAW_DATABASE_URL = (
    os.getenv("DATABASE_URL")
    or "sqlite:///./adaptive_engine.db"
)


def normalize_database_url(url: str):
    """
    Normalize cloud PostgreSQL URLs for psycopg 3.

    Neon commonly supplies postgres:// or
    postgresql:// URLs. SQLAlchemy will use
    psycopg 3 explicitly after normalization.
    """
    if url.startswith(
        "postgres://"
    ):
        return (
            "postgresql+psycopg://"
            + url[len("postgres://"):]
        )

    if url.startswith(
        "postgresql://"
    ):
        return (
            "postgresql+psycopg://"
            + url[
                len(
                    "postgresql://"
                ):
            ]
        )

    return url


DATABASE_URL = (
    normalize_database_url(
        RAW_DATABASE_URL
    )
)


def is_postgres():
    return DATABASE_URL.startswith(
        "postgresql"
    )


connect_args = {}

if DATABASE_URL.startswith(
    "sqlite"
):
    connect_args[
        "check_same_thread"
    ] = False


engine_kwargs = {
    "connect_args":
        connect_args,
    "pool_pre_ping":
        True,
}

if is_postgres():
    engine_kwargs.update(
        {
            "pool_recycle":
                300,
        }
    )


engine = create_engine(
    DATABASE_URL,
    **engine_kwargs,
)


SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
)


Base = declarative_base()


def get_db():
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()
