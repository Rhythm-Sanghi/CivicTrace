import os
import sys
import tempfile
import uuid
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

    # 1. Unconditionally reject production, staging, development, and live terms
    forbidden_terms = ["prod", "production", "live", "dev", "development", "stage", "staging", "primary", "master"]
    for term in forbidden_terms:
        if term in lower_url:
            raise RuntimeError(
                f"SAFETY ABORT: Refusing to initialize test database against potential production or development database: {db_url}. "
                f"Contains forbidden term '{term}'."
            )

    if lower_url.startswith("sqlite"):
        if ":memory:" in lower_url:
            return
        # Extract filename part
        clean_url = lower_url.split("?")[0]
        filename = clean_url.replace("\\", "/").split("/")[-1]
        # Must have an explicit test boundary (starts with test_, ends with _test.db, or has _test_ / test.)
        is_dedicated_test_sqlite = (
            filename in ("test.db", ":memory:")
            or filename.startswith("test_")
            or filename.startswith("test.")
            or "_test." in filename
            or "_test_" in filename
        )
        if not is_dedicated_test_sqlite:
            raise RuntimeError(
                f"SAFETY ABORT: SQLite test database filename must explicitly start or end with 'test': {db_url} (got '{filename}')"
            )
    elif lower_url.startswith("postgres"):
        # Extract database name from URL (after last / before any query parameters)
        db_name = db_url.split("/")[-1].split("?")[0].lower()
        # Reject default system databases
        if db_name in ("postgres", "template0", "template1", "admin", "root"):
            raise RuntimeError(
                f"SAFETY ABORT: Refusing to run tests against default system database '{db_name}': {db_url}"
            )
        # Dedicated test database authorization:
        # Must strictly have 'test' as a distinct token, e.g. starting with 'test_' or ending with '_test', or equal 'test'/'test_db'
        is_dedicated_test_db = (
            db_name in ("test", "test_db")
            or db_name.startswith("test_")
            or db_name.endswith("_test")
            or db_name.endswith("_test_db")
        )
        if not is_dedicated_test_db:
            raise RuntimeError(
                f"SAFETY ABORT: PostgreSQL test database must be an explicitly authorized dedicated test database "
                f"(must start with 'test_' or end with '_test', e.g. 'civictrace_test'; got '{db_name}'). "
                f"Full URL: {db_url}. Refusing to connect or modify tables on unconfirmed database."
            )
    else:
        raise RuntimeError(f"SAFETY ABORT: Unsupported database dialect for test runner: {db_url}")


# Explicit disposable test database configuration:
# Only use TEST_DATABASE_URL if explicitly configured in environment.
# When omitted, create a unique disposable temporary SQLite database per test run.
# NEVER silently fall back to normal application DATABASE_URL.
_disposable_sqlite_file = None
raw_url = os.environ.get("TEST_DATABASE_URL")
if raw_url:
    validate_test_database_safety(raw_url)
    TEST_DB_URL = raw_url
else:
    _disposable_sqlite_file = os.path.join(tempfile.gettempdir(), f"test_civictrace_{uuid.uuid4().hex[:12]}.db")
    normalized_path = _disposable_sqlite_file.replace("\\", "/")
    TEST_DB_URL = f"sqlite:///{normalized_path}"
    os.environ["TEST_DATABASE_URL"] = TEST_DB_URL

validate_test_database_safety(TEST_DB_URL)

# Alias module in sys.modules so imports of 'app.tests.conftest' share the same session/engine
if __name__ != "app.tests.conftest":
    sys.modules["app.tests.conftest"] = sys.modules[__name__]

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
    test_engine.dispose()
    if _disposable_sqlite_file and os.path.exists(_disposable_sqlite_file):
        try:
            os.remove(_disposable_sqlite_file)
        except Exception:
            pass
    if not raw_url and "TEST_DATABASE_URL" in os.environ:
        del os.environ["TEST_DATABASE_URL"]


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

