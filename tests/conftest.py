import os

import pytest

os.environ.setdefault("JWT_SECRET_KEY", "test-access-secret-key-with-32-chars")
os.environ.setdefault("JWT_REFRESH_SECRET_KEY", "test-refresh-secret-key-with-32-chars")


@pytest.fixture(autouse=True)
def clear_dependency_overrides():
    from app.main import app

    app.dependency_overrides.clear()
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"
