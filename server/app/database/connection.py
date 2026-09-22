from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from app.config import settings

def create_db_engine() -> Engine:
    connect_args = {}
    if settings.DATABASE_URL.startswith("sqlite"):
        connect_args = {"check_same_thread": False}
        return create_engine(
            settings.DATABASE_URL,
            connect_args=connect_args,
            echo=False
        )
    else:
        return create_engine(
            settings.DATABASE_URL,
            pool_pre_ping=True,
            pool_size=10,
            max_overflow=20,
            echo=False
        )

engine = create_db_engine()

def check_db_connection() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
