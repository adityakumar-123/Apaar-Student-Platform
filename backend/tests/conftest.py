import os
import sys
import tempfile
from pathlib import Path

# Must be set before the app modules are imported
_tmp = tempfile.mkdtemp()
os.environ["DATABASE_URL"] = f"sqlite:///{Path(_tmp) / 'test.db'}"
os.environ.setdefault("JWT_SECRET", "test-jwt-secret-that-is-long-enough-for-hs256")
os.environ.setdefault("SIGNING_SECRET", "test-signing-secret-that-is-long-enough")
os.environ["APAAR_REGISTRY"] = "off"
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from fastapi.testclient import TestClient

from auth import hash_password
from database import SessionLocal, engine
from main import app
from models import Base, User

USERS = [
    ("aicte_admin", "Aicte@123", "aicte", None),
    ("inst1", "Inst1@123", "institution", "INST001"),
    ("inst2", "Inst2@123", "institution", "INST002"),
    ("verifier", "Verify@123", "verifier", None),
]


@pytest.fixture(autouse=True)
def fresh_db():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    db = SessionLocal()
    for username, password, role, inst in USERS:
        db.add(User(username=username, password_hash=hash_password(password), role=role, institution_code=inst))
    db.commit()
    db.close()
    yield


@pytest.fixture
def client():
    return TestClient(app)


def login(client, username, password):
    res = client.post("/auth/login", data={"username": username, "password": password})
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


@pytest.fixture
def aicte(client):
    return login(client, "aicte_admin", "Aicte@123")


@pytest.fixture
def inst1(client):
    return login(client, "inst1", "Inst1@123")


@pytest.fixture
def inst2(client):
    return login(client, "inst2", "Inst2@123")


@pytest.fixture
def verifier(client):
    return login(client, "verifier", "Verify@123")


HEADER = "apaar_id,name,dob,category,nationality,is_nri,is_oci,is_foreign_national,is_supernumerary\n"


def make_csv(*rows):
    return HEADER + "\n".join(rows) + "\n"


@pytest.fixture
def setup_world(client, aicte):
    """Two institutions, each with one programme (intake 3 and 5) for 2025-26."""
    for code, name in (("INST001", "Demo Institute"), ("INST002", "Demo Business School")):
        assert client.post("/institutions", json={"code": code, "name": name, "state": "Delhi"}, headers=aicte).status_code == 201
    assert client.post("/programmes", json={"institution_code": "INST001", "name": "B.Tech CSE", "academic_year": "2025-26", "approved_intake": 3}, headers=aicte).status_code == 201
    assert client.post("/programmes", json={"institution_code": "INST002", "name": "MBA", "academic_year": "2025-26", "approved_intake": 5}, headers=aicte).status_code == 201


def upload(client, headers, csv_text, institution="INST001", programme="B.Tech CSE", year="2025-26", dry_run=False):
    return client.post(
        "/admissions/upload",
        data={"institution_code": institution, "programme": programme, "academic_year": year, "dry_run": str(dry_run).lower()},
        files={"file": ("batch.csv", csv_text.encode(), "text/csv")},
        headers=headers,
    )
