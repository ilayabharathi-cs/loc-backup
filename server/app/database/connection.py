from sqlalchemy import create_engine, text, event
from sqlalchemy.engine import Engine
from app.config import settings

def create_db_engine() -> Engine:
    connect_args = {}
    if settings.DATABASE_URL.startswith("sqlite"):
        connect_args = {"check_same_thread": False, "timeout": 60.0}
        eng = create_engine(
            settings.DATABASE_URL,
            connect_args=connect_args,
            pool_size=25,
            max_overflow=35,
            pool_timeout=60.0,
            echo=False
        )
        @event.listens_for(eng, "connect")
        def set_sqlite_pragma(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA synchronous=NORMAL")
            cursor.execute("PRAGMA busy_timeout=30000")
            cursor.close()
        return eng
    else:
        return create_engine(
            settings.DATABASE_URL,
            pool_pre_ping=True,
            pool_size=25,
            max_overflow=35,
            pool_timeout=60.0,
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
