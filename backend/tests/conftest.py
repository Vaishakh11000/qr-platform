
import pytest
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import create_access_token, hash_password
from app.core.database import get_db
from app.main import app
from app.models import AdminUser, Base, Role


@pytest.fixture(scope="session")
def test_engine():
    """
    Create an engine exclusively for the dedicated test database.

    ORM tables are created and dropped only in qr_platform_test.
    """
    if settings.test_database_url.database == settings.database_url.database:
        raise RuntimeError(
            "Test database must be different from the production database."
        )

    engine = create_engine(
        settings.test_database_url,
        pool_pre_ping=True,
    )

    try:
        Base.metadata.create_all(bind=engine)
        yield engine
    finally:
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


@pytest.fixture
def db_session(test_engine):
    """
    Provide a database session isolated by an outer transaction.

    Application commits use savepoints. The outer transaction is
    rolled back after each test, including tests that call commit().
    """
    connection = test_engine.connect()
    transaction = connection.begin()

    session = Session(
        bind=connection,
        autoflush=False,
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
    )

    try:
        yield session
    finally:
        session.close()

        if transaction.is_active:
            transaction.rollback()

        connection.close()


@pytest.fixture
def client(db_session):
    """
    Provide a FastAPI test client connected to the test database.

    The production engine is not disposed during test shutdown.
    """
    app.dependency_overrides.clear()

    previous_disposal_setting = getattr(
        app.state,
        "dispose_engine_on_shutdown",
        True,
    )

    app.state.dispose_engine_on_shutdown = False

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()
        app.state.dispose_engine_on_shutdown = previous_disposal_setting


@pytest.fixture
def override_dependency(client):
    """
    Allow individual tests to replace FastAPI dependencies.

    Example:
        override_dependency(get_db, mock_get_db)
    """
    def _override(dependency, replacement):
        app.dependency_overrides[dependency] = replacement

    return _override


@pytest.fixture
def admin_client(client, db_session):
    """Test client authenticated as a temporary SUPER_ADMIN."""
    role = db_session.query(Role).filter_by(
        name="SUPER_ADMIN"
    ).one_or_none()

    if role is None:
        role = Role(
            name="SUPER_ADMIN",
            description="Automated API test role",
        )
        db_session.add(role)
        db_session.flush()

    admin = AdminUser(
        name="Automated Test Admin",
        email=f"{uuid4().hex}@example.test",
        password_hash=hash_password("Test-Password-123!"),
        role_id=role.id,
        is_active=True,
    )
    db_session.add(admin)
    db_session.flush()

    token = create_access_token(admin.id)
    client.headers.update({
        "Authorization": f"Bearer {token}"
    })
    return client
