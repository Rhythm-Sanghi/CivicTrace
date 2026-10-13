import os
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient
from app.main import app as fastapi_app
from app.db.session import Base, get_db
from app.core.config import settings
from app.db import session as db_session_module


def validate_test_database_safety(db_url: str) -> None:
    """
    Fail-Safe Guard:
    Guarantees that database setup and teardown can NEVER modify development or production data.
    Fails closed if the test database identity or isolation cannot be confirmed.
    Destructive test setup cannot target production or ordinary development databases
    merely because their names contain 'test'.
    """
    lower_url = db_url.lower()

    # Unconditionally reject production and development terms, even if 'test' is present
    forbidden_terms = ["prod", "production", "live", "dev", "development"]
    for term in forbidden_terms:
        if term in lower_url:
            raise RuntimeError(
                f"SAFETY ABORT: Refusing to initialize test database against potential production or development database: {db_url}. "
                f"Contains forbidden term '{term}'."
            )

    if lower_url.startswith("sqlite"):
        if "test" not in lower_url and ":memory:" not in lower_url:
            raise RuntimeError(
                f"SAFETY ABORT: SQLite test database URL must explicitly contain 'test' or ':memory:': {db_url}"
            )
    elif lower_url.startswith("postgres"):
        # Extract database name from URL (after last / before any query parameters)
        db_name = db_url.split("/")[-1].split("?")[0].lower()
        if "test" not in db_name:
            raise RuntimeError(
                f"SAFETY ABORT: PostgreSQL test database name must explicitly contain 'test' (got '{db_name}'). "
                f"Full URL: {db_url}. Refusing to connect or modify tables on unconfirmed database."
            )
    else:
        raise RuntimeError(f"SAFETY ABORT: Unsupported database dialect for test runner: {db_url}")


# Explicit disposable test database configuration:
# Only use TEST_DATABASE_URL if explicitly configured in environment.
# NEVER silently fall back to normal application DATABASE_URL.
raw_url = os.environ.get("TEST_DATABASE_URL")
if raw_url:
    validate_test_database_safety(raw_url)
    TEST_DB_URL = raw_url
else:
    TEST_DB_URL = "sqlite:///./test_shared_civictrace.db"

validate_test_database_safety(TEST_DB_URL)

# Configure engine with dialect-specific connection arguments
connect_args = {}
pool_kwargs = {}
if TEST_DB_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}
else:
    from sqlalchemy.pool import NullPool
    pool_kwargs = {"poolclass": NullPool}

test_engine = create_engine(TEST_DB_URL, connect_args=connect_args, **pool_kwargs)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

# Patch app session and settings to use test database
db_session_module.engine = test_engine
db_session_module.SessionLocal = TestingSessionLocal
settings.DATABASE_URL = TEST_DB_URL


@pytest.fixture(scope="session", autouse=True)
def setup_test_database():
    validate_test_database_safety(TEST_DB_URL)
    Base.metadata.drop_all(bind=test_engine)
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture
def db_session():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def client(db_session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    fastapi_app.dependency_overrides[get_db] = override_get_db
    with TestClient(fastapi_app) as c:
        yield c
    fastapi_app.dependency_overrides.clear()

