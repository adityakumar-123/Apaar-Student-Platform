from .conftest import make_csv, upload

BATCH = make_csv(
    "200000000001,Ananya Rao,2006-01-10,General,Indian,no,no,no,no",
    "200000000002,Rohit Das,2006-02-11,OBC,Indian,no,no,no,no",
    "200000000003,Meera Iyer,2006-03-12,SC,Indian,no,no,no,no",
    "200000000004,Kabir Shah,2006-04-13,General,Indian,no,no,no,no",
)


def test_dry_run_saves_nothing_but_reports_excess(client, aicte, setup_world):
    res = upload(client, aicte, BATCH, dry_run=True).json()
    assert res["accepted"] == 4 and res["rejected"] == 0
    assert res["projected_regular_enrolment"] == 4
    assert any("exceeds approved intake 3 by 1" in w for w in res["warnings"])
    report = client.get("/compliance/intake", headers=aicte).json()
    assert report[0]["regular_enrolled"] == 0


def test_saved_upload_marks_excess_on_dashboard(client, aicte, setup_world):
    assert upload(client, aicte, BATCH).status_code == 200
    row = next(r for r in client.get("/compliance/intake", headers=aicte).json() if r["institution_code"] == "INST001")
    assert row["regular_enrolled"] == 4 and row["excess"] == 1 and row["status"] == "EXCESS"


def test_supernumerary_seats_are_not_counted_against_intake(client, aicte, setup_world):
    csv_text = make_csv(
        "200000000001,A One,2006-01-10,General,Indian,no,no,no,no",
        "200000000002,B Two,2006-01-11,General,Indian,no,no,no,yes",
    )
    upload(client, aicte, csv_text)
    row = client.get("/compliance/intake", headers=aicte).json()[0]
    assert row["regular_enrolled"] == 1 and row["supernumerary_enrolled"] == 1 and row["status"] == "OK"


def test_reupload_is_rejected_as_already_admitted(client, aicte, setup_world):
    upload(client, aicte, BATCH)
    res = upload(client, aicte, BATCH).json()
    assert res["accepted"] == 0 and res["rejected"] == 4
    assert all("Already admitted in this programme" in e["errors"][0] for e in res["errors"])


def test_cross_institution_duplicate_enrolment_and_identity_mismatch(client, aicte, setup_world):
    upload(client, aicte, BATCH)
    csv_text = make_csv(
        "200000000002,Rohit Das,2006-02-11,OBC,Indian,no,no,no,no",      # same person, other institution
        "200000000001,Ananya Verma,2006-01-10,General,Indian,no,no,no,no",  # same ID, different name
        "200000000099,New Student,2006-05-05,General,Indian,no,no,no,no",
    )
    res = upload(client, aicte, csv_text, institution="INST002", programme="MBA").json()
    msgs = [e["errors"][0] for e in res["errors"]]
    assert any("Potential duplicate enrolment: already admitted at INST001" in m for m in msgs)
    assert any("different name or DOB" in m for m in msgs)
    assert res["accepted"] == 1


def test_institution_can_only_upload_for_own_institution(client, inst1, setup_world):
    csv_text = make_csv("200000000010,Own Student,2006-01-10,General,Indian,no,no,no,no")
    assert upload(client, inst1, csv_text).status_code == 200
    assert upload(client, inst1, csv_text, institution="INST002", programme="MBA").status_code == 403


def test_upload_requires_login_and_programme(client, aicte, setup_world):
    assert upload(client, {}, BATCH).status_code == 401
    assert upload(client, aicte, BATCH, programme="Nonexistent").status_code == 404


def test_upload_is_audit_logged_with_username(client, aicte, inst1, setup_world):
    upload(client, inst1, make_csv("200000000010,Own Student,2006-01-10,General,Indian,no,no,no,no"))
    from database import SessionLocal
    from models import AuditLog
    db = SessionLocal()
    entry = db.query(AuditLog).filter_by(action="ADMISSIONS_UPLOAD").one()
    db.close()
    assert entry.actor == "inst1" and "INST001" in entry.details


def test_registry_check_when_enabled(client, aicte, setup_world, monkeypatch, tmp_path):
    import json
    reg = tmp_path / "reg.json"
    reg.write_text(json.dumps({
        "200000000001": {"name": "Ananya Rao", "dob": "2006-01-10"},
        "200000000002": {"name": "Someone Else", "dob": "2006-02-11"},
    }))
    monkeypatch.setenv("APAAR_REGISTRY", "mock")
    monkeypatch.setenv("APAAR_REGISTRY_FILE", str(reg))
    csv_text = make_csv(
        "200000000001,Ananya Rao,2006-01-10,General,Indian,no,no,no,no",
        "200000000002,Rohit Das,2006-02-11,OBC,Indian,no,no,no,no",
        "200000000777,Ghost Student,2006-02-11,OBC,Indian,no,no,no,no",
    )
    res = upload(client, aicte, csv_text).json()
    msgs = [e["errors"][0] for e in res["errors"]]
    assert res["accepted"] == 1
    assert "Name does not match the APAAR registry" in msgs
    assert "APAAR ID not found in the national registry" in msgs
