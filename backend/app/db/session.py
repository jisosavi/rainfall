from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.config import get_settings

settings = get_settings()
engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def limit_statement_time(db) -> None:
    """Web requests (REST, MCP) cancel any statement running over STATEMENT_TIMEOUT_MS, so one
    heavy query can't hold up the app. Ingestion uses plain sessions and isn't limited."""
    ms = int(settings.statement_timeout_ms)
    if ms > 0 and db.get_bind().dialect.name == "postgresql":
        db.execute(text(f"SET statement_timeout = {ms}"))


def get_db():
    db = SessionLocal()
    limit_statement_time(db)
    try:
        yield db
    finally:
        db.close()
