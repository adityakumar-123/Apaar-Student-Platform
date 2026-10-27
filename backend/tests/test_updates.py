from .conftest import make_csv, upload

ROWS = make_csv(
    "200000000001,Ananya Rao,2006-01-10,General,Indian,no,no,no,no",
    "200000000002,Rohit Das,2006-02-11,OBC,Indian,no,no,no,no",
    "200000000003,Meera Iyer,2006-03-12,SC,Indian,no,no,no,no",
    "200000000004,Kabir Shah,2006-04-13,General,Indian,no,no,no,no",
)
KEY = {"institution_code": "INST001", "programme": "B.Tech CSE", "academic_year": "2025-26"}


def patch_admission(client, headers, apaar, **body):
    return client.patch(f"/admissions/{apaar}", json={**KEY, "reason": "Correction requested by institution", **body}, headers=headers)


def intake_row(client, headers):
    return next(r for r in client.get("/compliance/intake", headers=headers).json() if r["institution_code"] == "INST001")


def audit(action):
    from database import SessionLocal
    from models import AuditLog
    db = SessionLocal()
    rows = db.query(AuditLog).filter_by(action=action).all()
    db.close()
    return rows


def test_withdrawing_an_admission_frees_the_seat(client, aicte, inst1, setup_world):
    upload(client, aicte, ROWS)
    assert intake_row(client, aicte)["status"] == "EXCESS"
    res = patch_admission(client, inst1, "200000000004", status="withdrawn")
    assert res.status_code == 200 and res.json()["status"] == "withdrawn"
    row = intake_row(client, aicte)
    assert row["regular_enrolled"] == 3 and row["status"] == "OK"


def test_marking_supernumerary_moves_the_student_out_of_regular_count(client, aicte, inst1, setup_world):
    upload(client, aicte, ROWS)
    assert patch_admission(client, inst1, "200000000004", is_supernumerary=True).status_code == 200
    row = intake_row(client, aicte)
    assert row["regular_enrolled"] == 3 and row["supernumerary_enrolled"] == 1


def test_update_is_audit_logged_with_actor_and_old_new_values(client, aicte, inst1, setup_world):
    upload(client, aicte, ROWS)
    patch_admission(client, inst1, "200000000004", status="withdrawn")
    entry = audit("ADMISSION_UPDATED")[0]
    assert entry.actor == "inst1"
    assert "admitted->withdrawn" in entry.details and "Correction requested" in entry.details
    assert "200000000004" not in entry.details  # APAAR ID is masked in the log


def test_reason_is_required_and_status_validated(client, aicte, inst1, setup_world):
    upload(client, aicte, ROWS)
    no_reason = client.patch("/admissions/200000000004", json={**KEY, "status": "withdrawn"}, headers=inst1)
    assert no_reason.status_code == 422
    assert patch_admission(client, inst1, "200000000004", status="deleted").status_code == 400
    assert patch_admission(client, inst1, "200000000004").status_code == 400  # nothing to change


def test_other_institution_cannot_change_admission(client, aicte, inst2, setup_world):
    upload(client, aicte, ROWS)
    res = patch_admission(client, inst2, "200000000004", status="withdrawn")
    assert res.status_code == 403
    assert intake_row(client, aicte)["regular_enrolled"] == 4


def test_unknown_admission_returns_404(client, inst1, setup_world):
    assert patch_admission(client, inst1, "299999999999", status="withdrawn").status_code == 404


def test_cannot_readmit_while_admitted_elsewhere(client, aicte, inst1, inst2, setup_world):
    upload(client, aicte, ROWS)
    patch_admission(client, inst1, "200000000004", status="withdrawn")
    upload(client, inst2, make_csv("200000000004,Kabir Shah,2006-04-13,General,Indian,no,no,no,no"), institution="INST002", programme="MBA")
    res = patch_admission(client, inst1, "200000000004", status="admitted")
    assert res.status_code == 409 and "already admitted at INST002" in res.json()["detail"]


def test_institution_corrects_category_but_not_identity(client, aicte, inst1, setup_world):
    upload(client, aicte, ROWS)
    ok = client.patch("/students/200000000001", json={"category": "OBC", "reason": "Certificate re-checked"}, headers=inst1)
    assert ok.status_code == 200 and ok.json()["fields"] == ["category"]
    assert "General->OBC" in audit("STUDENT_CORRECTED")[0].details

    blocked = client.patch("/students/200000000001", json={"name": "Someone Else", "reason": "Name change attempt"}, headers=inst1)
    assert blocked.status_code == 403


def test_aicte_corrects_name_without_copying_it_to_the_audit_log(client, aicte, setup_world):
    upload(client, aicte, ROWS)
    res = client.patch("/students/200000000001", json={"name": "Ananya R Rao", "reason": "Spelling fixed per APAAR card"}, headers=aicte)
    assert res.status_code == 200
    details = audit("STUDENT_CORRECTED")[0].details
    assert "name changed" in details and "Ananya" not in details


def test_correction_must_stay_consistent(client, aicte, inst1, setup_world):
    upload(client, aicte, ROWS)
    res = client.patch("/students/200000000001", json={"is_foreign_national": True, "reason": "Marked by mistake"}, headers=inst1)
    assert res.status_code == 422 and "Foreign National" in res.json()["detail"]


def test_institution_cannot_correct_student_from_another_institution(client, aicte, inst2, setup_world):
    upload(client, aicte, ROWS)
    res = client.patch("/students/200000000001", json={"category": "SC", "reason": "Trying another school"}, headers=inst2)
    assert res.status_code == 403
