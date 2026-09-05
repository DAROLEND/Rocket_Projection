from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

DATABASE_URL = "sqlite+aiosqlite:///./rocket.db"

engine = create_async_engine(DATABASE_URL, echo=False)
async_session = async_sessionmaker(engine, expire_on_commit=False)

class Base(DeclarativeBase):
    pass

async def get_db():
    async with async_session() as session:
        yield session


# Lightweight ad-hoc migration for SQLite: this project doesn't have real Alembic
# migrations wired up yet, so newly added nullable columns are patched onto an
# existing rocket.db in place rather than requiring a destroy-and-recreate.
_NEW_COLUMNS = {
    "thrust": "ALTER TABLE simulations ADD COLUMN thrust FLOAT",
    "burn_time": "ALTER TABLE simulations ADD COLUMN burn_time FLOAT",
    "propellant_mass": "ALTER TABLE simulations ADD COLUMN propellant_mass FLOAT",
    "parachute_cd": "ALTER TABLE simulations ADD COLUMN parachute_cd FLOAT",
    "parachute_area": "ALTER TABLE simulations ADD COLUMN parachute_area FLOAT",
    "integration_method": "ALTER TABLE simulations ADD COLUMN integration_method TEXT DEFAULT 'euler'",
}


async def ensure_schema_migrated(conn) -> None:
    result = await conn.exec_driver_sql("PRAGMA table_info(simulations)")
    existing_columns = {row[1] for row in result.fetchall()}

    for column, ddl in _NEW_COLUMNS.items():
        if column not in existing_columns:
            await conn.exec_driver_sql(ddl)