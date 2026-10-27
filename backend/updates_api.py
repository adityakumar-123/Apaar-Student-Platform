"""Corrections and status changes for data that is already uploaded.

Every change needs a reason and is written to the audit log with the old and new values.
Name and date of birth are identity fields, so only AICTE can correct them; an institution
could otherwise use a "correction" to get around the identity-mismatch check.
"""
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from auth import require_roles
from compliance import find_active_admission
from database import get_db
from models import Admission, AuditLog, Programme, Student, User
from validation import consistency_errors

router = APIRouter()

ADMISSION_STATUSES = {"admitted", "withdrawn", "cancelled"}
INSTITUTION_FIELDS = ["category", "nationality", "is_nri", "is_oci", "is_foreign_national"]
AICTE_ONLY_FIELDS = ["name", "dob"]


def mask(apaar_id: str) -> str:
    return "*" * 8 + apaar_id[-4:]


class AdmissionUpdate(BaseModel):
    institution_code: str
    programme: str
    academic_year: str
    is_supernumerary: bool | None = None
    status: str | None = None
    reason: str = Field(min_length=5, max_length=200)


class StudentUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=150)
    dob: date | None = None
    category: str | None = Field(None, max_length=20)
    nationality: str | None = Field(None, max_length=50)
    is_nri: bool | None = None
    is_oci: bool | None = None
    is_foreign_national: bool | None = None
    reason: str = Field(min_length=5, max_length=200)


def _own_institution(user: User, institution_code: str):
    if user.role == "institution" and user.institution_code != institution_code:
        raise HTTPException(403, "You can only change data for your own institution")


@router.patch("/admissions/{apaar_id}")
def update_admission(
    apaar_id: str,
    data: AdmissionUpdate,
    user: User = Depends(require_roles("institution", "aicte")),
    db: Session = Depends(get_db),
):
    """Mark an admission as supernumerary or not, or withdraw / cancel / re-admit it."""
    _own_institution(user, data.institution_code)
    if data.is_supernumerary is None and data.status is None:
        raise HTTPException(400, "Nothing to change: send is_supernumerary and/or status")
    if data.status is not None and data.status not in ADMISSION_STATUSES:
        raise HTTPException(400, "status must be one of: " + ", ".join(sorted(ADMISSION_STATUSES)))

    student = db.query(Student).filter_by(apaar_id=apaar_id).first()
    admission = None
    if student:
        admission = (
            db.query(Admission)
            .filter_by(
                student_id=student.id,
                institution_id=data.institution_code,
                programme=data.programme,
                academic_year=data.academic_year,
            )
            .order_by(Admission.id.desc())
            .first()
        )
    if not admission:
        raise HTTPException(404, "Admission not found for this student, programme and year")

    changes = []
    if data.status is not None and data.status != admission.status:
        if data.status == "admitted":
            other = find_active_admission(db, student.id, data.academic_year)
            if other and other.id != admission.id:
                raise HTTPException(
                    409,
                    f"Cannot re-admit: already admitted at {other.institution_id} / {other.programme}",
                )
        changes.append(f"status {admission.status}->{data.status}")
        admission.status = data.status
    if data.is_supernumerary is not None and data.is_supernumerary != bool(admission.is_supernumerary):
        changes.append(f"supernumerary {bool(admission.is_supernumerary)}->{data.is_supernumerary}")
        admission.is_supernumerary = data.is_supernumerary

    if not changes:
        return {"apaar_id": apaar_id, "changed": False, "message": "No change needed"}

    db.add(AuditLog(
        actor=user.username,
        action="ADMISSION_UPDATED",
        details=f"{mask(apaar_id)} {data.institution_code}/{data.programme}/{data.academic_year}: "
                f"{'; '.join(changes)}. Reason: {data.reason}"[:500],
    ))
    db.commit()
    return {
        "apaar_id": apaar_id,
        "changed": True,
        "status": admission.status,
        "is_supernumerary": bool(admission.is_supernumerary),
    }


@router.patch("/students/{apaar_id}")
def correct_student(
    apaar_id: str,
    data: StudentUpdate,
    user: User = Depends(require_roles("institution", "aicte")),
    db: Session = Depends(get_db),
):
    """Correct student details. Institutions can only touch students admitted with them."""
    student = db.query(Student).filter_by(apaar_id=apaar_id).first()
    if not student:
        raise HTTPException(404, "Student not found")

    if user.role == "institution":
        has_link = (
            db.query(Admission.id)
            .filter_by(student_id=student.id, institution_id=user.institution_code)
            .first()
        )
        if not has_link:
            raise HTTPException(403, "This student has no admission at your institution")

    updates = data.model_dump(exclude_unset=True, exclude={"reason"})
    updates = {k: v for k, v in updates.items() if v is not None or k in ("category",)}
    if not updates:
        raise HTTPException(400, "Nothing to change")
    if user.role == "institution":
        blocked = [f for f in AICTE_ONLY_FIELDS if f in updates]
        if blocked:
            raise HTTPException(403, "Only AICTE can correct " + " and ".join(blocked))

    # Check the result stays consistent before saving
    merged = {f: updates.get(f, getattr(student, f)) for f in INSTITUTION_FIELDS}
    errs = consistency_errors(merged["nationality"], merged)
    if "dob" in updates and updates["dob"] >= date.today():
        errs.append("DOB cannot be in the future")
    if errs:
        raise HTTPException(422, "; ".join(errs))

    changes = []
    for field, new in updates.items():
        old = getattr(student, field)
        if old == new:
            continue
        # Identity fields are logged by name only, so the audit log does not copy personal data
        if field in AICTE_ONLY_FIELDS:
            changes.append(f"{field} changed")
        else:
            changes.append(f"{field} {old}->{new}")
        setattr(student, field, new)

    if not changes:
        return {"apaar_id": apaar_id, "changed": False, "message": "No change needed"}

    db.add(AuditLog(
        actor=user.username,
        action="STUDENT_CORRECTED",
        details=f"{mask(apaar_id)}: {'; '.join(changes)}. Reason: {data.reason}"[:500],
    ))
    db.commit()
    return {"apaar_id": apaar_id, "changed": True, "fields": [c.split(" ")[0] for c in changes]}
