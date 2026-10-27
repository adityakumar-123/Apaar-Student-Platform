from .conftest import make_csv, upload

ROWS = make_csv(
    "200000000001,Ananya Rao,2006-01-10,General,Indian,no,no,no,no",
    "200000000002,Rohit Das,2006-02-11,OBC,Indian,no,no,no,no",
    "200000000003,Meera Iyer,2006-03-12,SC,Indian,no,no,no,no",
    "200000000004,Kabir Shah,2006-04-13,General,Indian,no,no,no,no",
)


def test_institution_dashboard_shows_only_own_data(client, aicte, inst1, setup_world):
    upload(client, inst1, ROWS)
    res = client.get("/institution/dashboard", headers=inst1)
    assert res.status_code == 200
    data = res.json()
    assert data["institution"]["code"] == "INST001"
    assert [p["programme"] for p in data["programmes"]] == ["B.Tech CSE"]
    assert data["programmes"][0]["status"] == "EXCESS"
    assert data["risk"]["level"] in {"LOW", "MEDIUM", "HIGH"} and data["risk"]["reasons"]
    assert data["recent_activity"][0]["action"] == "ADMISSIONS_UPLOAD"


def test_institution_cannot_view_another_institution(client, inst1, setup_world):
    assert client.get("/institution/dashboard?institution_code=INST002", headers=inst1).status_code == 403
    res = client.get("/institution/admissions?institution_code=INST002&programme=MBA&academic_year=2025-26", headers=inst1)
    assert res.status_code == 403


def test_aicte_must_name_the_institution(client, aicte, setup_world):
    assert client.get("/institution/dashboard", headers=aicte).status_code == 400
    assert client.get("/institution/dashboard?institution_code=INST002", headers=aicte).status_code == 200
    assert client.get("/institution/dashboard?institution_code=NOPE", headers=aicte).status_code == 404


def test_verifier_and_anonymous_are_blocked(client, verifier, setup_world):
    assert client.get("/institution/dashboard", headers=verifier).status_code == 403
    assert client.get("/institution/dashboard").status_code == 401


def test_admissions_list_for_own_programme(client, inst1, setup_world):
    upload(client, inst1, ROWS)
    res = client.get("/institution/admissions?programme=B.Tech CSE&academic_year=2025-26", headers=inst1)
    assert res.status_code == 200
    rows = res.json()
    assert len(rows) == 4 and {r["status"] for r in rows} == {"admitted"}


def test_institution_cannot_issue_credential_for_another_institutions_student(client, aicte, inst2, setup_world):
    upload(client, aicte, ROWS)
    assert client.post("/credentials/200000000001", headers=inst2).status_code == 403


def test_credential_issue_and_revoke_are_audited_with_real_user(client, aicte, inst1, setup_world):
    upload(client, aicte, ROWS)
    cred = client.post("/credentials/200000000001", headers=inst1)
    assert cred.status_code == 201
    cid = cred.json()["credential_id"]
    assert client.post(f"/credentials/{cid}/revoke", headers=aicte).status_code == 200

    from database import SessionLocal
    from models import AuditLog
    db = SessionLocal()
    actors = {a.action: a.actor for a in db.query(AuditLog).filter(AuditLog.action.in_(["CREDENTIAL_ISSUED", "CREDENTIAL_REVOKED"])).all()}
    db.close()
    assert actors == {"CREDENTIAL_ISSUED": "inst1", "CREDENTIAL_REVOKED": "aicte_admin"}


def test_consent_request_logs_authenticated_user(client, aicte, inst1, verifier, setup_world):
    upload(client, aicte, ROWS)
    cid = client.post("/credentials/200000000001", headers=inst1).json()["credential_id"]
    res = client.post("/consent/request", json={"credential_id": cid, "verifier_name": "Acme Corp HR", "purpose": "Employment check"}, headers=verifier)
    assert res.status_code == 201

    from database import SessionLocal
    from models import AuditLog
    db = SessionLocal()
    entry = db.query(AuditLog).filter_by(action="CONSENT_REQUESTED").one()
    db.close()
    assert entry.actor == "verifier" and "Acme Corp HR" in entry.details


def test_tampered_credential_fails_verification(client, aicte, inst1, setup_world):
    upload(client, aicte, ROWS)
    cid = client.post("/credentials/200000000001", headers=inst1).json()["credential_id"]
    assert client.get(f"/verify/{cid}").json()["valid"] is True

    from database import SessionLocal
    from models import Credential
    import json
    db = SessionLocal()
    cred = db.get(Credential, cid)
    payload = json.loads(cred.payload)
    payload["programme"] = "Forged Programme"
    cred.payload = json.dumps(payload)
    db.commit()
    db.close()
    assert client.get(f"/verify/{cid}").json()["valid"] is False
