"""
SQLAlchemy engine, session factory, and declarative base.
"""
import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.pool import NullPool

from app.config import settings

# Managed Postgres poolers (Neon, Supabase) run PgBouncer in transaction mode,
# which does not support psycopg's server-side prepared statements, so turn
# them off. This is harmless on a direct connection.
# connect_timeout makes a wrong or unreachable database fail in 10 seconds
# instead of hanging forever.
_engine_kwargs = {
    "connect_args": {"prepare_threshold": None, "connect_timeout": 10},
}

if os.environ.get("VERCEL"):
    # Serverless: every function instance is short-lived and many can run at
    # once, so don't keep a local connection pool - the provider's pooler
    # (Neon/Supabase) does the real pooling.
    _engine_kwargs["poolclass"] = NullPool
else:
    _engine_kwargs["pool_pre_ping"] = True

engine = create_engine(settings.database_url, **_engine_kwargs)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()