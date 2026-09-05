import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from app.database import Base
from app import main as main_module


@pytest_asyncio.fixture
async def client(tmp_path, monkeypatch):
    """A test client backed by its own throwaway SQLite file, so tests never
    touch the real rocket.db or the real ChromaDB index."""
    db_path = tmp_path / "test.db"
    test_engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}", echo=False)
    test_session = async_sessionmaker(test_engine, expire_on_commit=False)

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async def override_get_db():
        async with test_session() as session:
            yield session

    main_module.app.dependency_overrides[main_module.get_db] = override_get_db
    monkeypatch.setattr(main_module, "index_simulation", lambda simulation: None)

    transport = ASGITransport(app=main_module.app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    main_module.app.dependency_overrides.clear()
    await test_engine.dispose()
