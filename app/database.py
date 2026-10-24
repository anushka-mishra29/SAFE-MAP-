import os
from pathlib import Path

from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import declarative_base, sessionmaker

ROOT = Path(__file__).resolve().parent.parent
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{(ROOT / 'safemap.db').as_posix()}")
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def migrate_additive_columns():
    """Add fields introduced by SafeMap upgrades without dropping existing records."""
    additions = {
        "locations": {"is_demo": "BOOLEAN NOT NULL DEFAULT 1"},
        "safe_places": {"is_demo": "BOOLEAN NOT NULL DEFAULT 1"},
        "reports": {
            "title": "VARCHAR(120) NOT NULL DEFAULT 'Community report'",
            "is_demo": "BOOLEAN NOT NULL DEFAULT 0",
        },
    }
    with engine.begin() as connection:
        inspector = inspect(connection)
        for table, columns in additions.items():
            if not inspector.has_table(table):
                continue
            existing = {column["name"] for column in inspector.get_columns(table)}
            for name, ddl in columns.items():
                if name not in existing:
                    quoted_table = engine.dialect.identifier_preparer.quote(table)
                    quoted_name = engine.dialect.identifier_preparer.quote(name)
                    connection.exec_driver_sql(f"ALTER TABLE {quoted_table} ADD COLUMN {quoted_name} {ddl}")
