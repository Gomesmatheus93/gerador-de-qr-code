import base64
import re

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models import User
from app.services.security import hash_password


@pytest.fixture
def client():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    with session_factory() as db:
        db.add(User(name="Admin", email="admin@example.com", password_hash=hash_password("correct-password")))
        db.commit()

    def override_db():
        with session_factory() as db:
            yield db

    app.dependency_overrides[get_db] = override_db
    with TestClient(app, follow_redirects=False) as test_client:
        yield test_client, session_factory
    app.dependency_overrides.clear()
    engine.dispose()


@pytest.fixture
def basic_auth():
    token = base64.b64encode(b"admin@example.com:correct-password").decode()
    return {"Authorization": f"Basic {token}"}


def login(client: TestClient):
    page = client.get("/login")
    token = re.search(r'name="csrf" value="([^"]+)"', page.text).group(1)
    return client.post("/login", data={"email": "admin@example.com", "password": "correct-password", "csrf": token})
