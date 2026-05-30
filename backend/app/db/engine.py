from pathlib import Path
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from app.config import load_settings

_SCHEMA = Path(__file__).parent / "schema.sql"


def get_engine() -> Engine:
    settings = load_settings()
    return create_engine(settings.database.url(), pool_pre_ping=True)


def apply_schema(engine: Engine) -> None:
    ddl = _SCHEMA.read_text()
    with engine.begin() as conn:
        for statement in [s.strip() for s in ddl.split(";") if s.strip()]:
            conn.execute(text(statement))
