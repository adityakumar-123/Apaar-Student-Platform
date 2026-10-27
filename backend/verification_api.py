import hashlib
import hmac
import json
import os
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from database import get_db
from models import Student, Admission, Institution, Credential, ConsentRequest, AuditLog, User
from auth import require_roles

router = APIRouter()

SECRET = os.getenv("SIGNING_SECRET", "dev-only-change-me").encode()
DEMO_MODE = os.getenv("DEMO_MODE", "true").lower() == "true"
CONSENT_MINUTES = 10


def now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def sign(payload: dict) -> str:
    data = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hmac.new(SECRET, data, hashlib.sha256).hexdigest()


def otp_hash(consent_id: str, otp: str) -> str:
    return hmac.new(SECRET, f"{consent_id}:{otp}".encode(), hashlib.sha256).hexdigest()


def mask_name(name: str) -> str:
    return " ".join(p[0] + "*" * (len(p) - 1) for p in name.split())


def mask_id(apaar_id: str) -> str:
    return "*" * 8 + apaar_id[-4:]


class ConsentIn(BaseModel):
    credential_id: str
    verifier_name: str = Field(min_length=2)
    purpose: str = Field(min_length=3)


class OtpIn(BaseModel):
    otp: str


@router.post("/credentials/{apaar_id}", status_code=201)
def issue_credential(
    apaar_id: str,
    user: User = Depends(require_roles("institution", "aicte")),
    db: Session = Depends(get_db),
):
    student = db.query(Student).filter_by(apaar_id=apaar_id).first()
    if not student:
        raise HTTPException(404, "Student not found")
    admission = (
        db.query(Admission)
        .filter_by(student_id=student.id, status="admitted")
        .order_by(Admission.id.desc())
        .first()
    )
    if not admission:
        raise HTTPException(404, "No active admission for this student")
    if user.role == "institution" and admission.institution_id != user.institution_code:
        raise HTTPException(403, "You can only issue credentials for students admitted at your institution")
    inst = db.query(Institution).filter_by(code=admission.institution_id).first()

    credential_id = str(uuid.uuid4())
    payload = {
        "credential_id": credential_id,
        "apaar_id": student.apaar_id,
        "student_name": student.name,
        "dob": student.dob.isoformat(),
        "institution_code": admission.institution_id,
        "institution_name": inst.name if inst else admission.institution_id,
        "programme": admission.programme,
        "academic_year": admission.academic_year,
        "status": admission.status,
        "issued_at": now().isoformat(timespec="seconds"),
    }
    signature = sign(payload)
    db.add(Credential(
        id=credential_id,
        apaar_id=student.apaar_id,
        payload=json.dumps(payload),
        signature=signature,
    ))
    db.add(AuditLog(
        actor=user.username,
        action="CREDENTIAL_ISSUED",
        details=f"{mask_id(student.apaar_id)} {credential_id}",
    ))
    db.commit()
    return {"credential_id": credential_id, "signature": signature, "payload": payload}


@router.post("/credentials/{credential_id}/revoke")
def revoke_credential(
    credential_id: str,
    user: User = Depends(require_roles("aicte")),
    db: Session = Depends(get_db),
):
    cred = db.get(Credential, credential_id)
    if not cred:
        raise HTTPException(404, "Credential not found")
    cred.revoked = True
    db.add(AuditLog(actor=user.username, action="CREDENTIAL_REVOKED", details=credential_id))
    db.commit()
    return {"credential_id": credential_id, "revoked": True}


@router.post("/consent/request", status_code=201)
def request_consent(
    data: ConsentIn,
    user: User = Depends(require_roles("verifier", "aicte")),
    db: Session = Depends(get_db),
):
    cred = db.get(Credential, data.credential_id)
    if not cred:
        raise HTTPException(404, "Credential not found")

    consent_id = str(uuid.uuid4())
    otp = f"{secrets.randbelow(10**6):06d}"
    expires_at = now() + timedelta(minutes=CONSENT_MINUTES)
    db.add(ConsentRequest(
        id=consent_id,
        credential_id=data.credential_id,
        verifier_name=data.verifier_name,
        purpose=data.purpose,
        otp_hash=otp_hash(consent_id, otp),
        status="pending",
        expires_at=expires_at,
    ))
    db.add(AuditLog(
        actor=user.username,
        action="CONSENT_REQUESTED",
        details=f"{mask_id(cred.apaar_id)} for {data.verifier_name}: {data.purpose}",
    ))
    db.commit()

    response = {
        "consent_id": consent_id,
        "status": "pending",
        "expires_at": expires_at.isoformat(timespec="seconds"),
        "message": "An OTP has been sent to the student's registered mobile number",
    }
    if DEMO_MODE:
        print(f"[DEMO] OTP for consent {consent_id}: {otp}")
        response["demo_otp"] = otp
    return response


@router.post("/consent/{consent_id}/approve")
def approve_consent(consent_id: str, data: OtpIn, db: Session = Depends(get_db)):
    consent = db.get(ConsentRequest, consent_id)
    if not consent:
        raise HTTPException(404, "Consent request not found")
    if consent.status != "pending":
        raise HTTPException(409, f"Consent is already {consent.status}")
    if consent.expires_at < now():
        consent.status = "expired"
        db.commit()
        raise HTTPException(410, "OTP has expired. Request consent again")
    if consent.attempts >= 5:
        raise HTTPException(429, "Too many incorrect attempts")

    consent.attempts += 1
    if not hmac.compare_digest(otp_hash(consent_id, data.otp.strip()), consent.otp_hash):
        db.commit()
        raise HTTPException(401, "Incorrect OTP")

    consent.status = "approved"
    db.add(AuditLog(
        actor="student",
        action="CONSENT_APPROVED",
        details=f"{consent.verifier_name}: {consent.purpose}",
    ))
    db.commit()
    return {
        "consent_id": consent_id,
        "status": "approved",
        "expires_at": consent.expires_at.isoformat(timespec="seconds"),
    }


@router.get("/verify/{credential_id}")
def verify(credential_id: str, consent_id: str | None = None, db: Session = Depends(get_db)):
    cred = db.get(Credential, credential_id)
    if not cred:
        raise HTTPException(404, "Credential not found")

    payload = json.loads(cred.payload)
    signature_valid = hmac.compare_digest(sign(payload), cred.signature)

    if not signature_valid:
        db.add(AuditLog(actor="public", action="VERIFY_FAILED", details=f"{credential_id}: signature mismatch"))
        db.commit()
        return {
            "valid": False,
            "signature_valid": False,
            "reason": "This record was altered or was not issued by this platform",
        }

    admission = (
        db.query(Admission)
        .join(Student, Admission.student_id == Student.id)
        .filter(
            Student.apaar_id == cred.apaar_id,
            Admission.institution_id == payload["institution_code"],
            Admission.programme == payload["programme"],
            Admission.academic_year == payload["academic_year"],
        )
        .first()
    )
    current_status = admission.status if admission else "not_found"

    reason = None
    if cred.revoked:
        reason = "This credential has been revoked"
    elif current_status != "admitted":
        reason = f"Student's current admission status is '{current_status}'"

    result = {
        "valid": reason is None,
        "signature_valid": True,
        "revoked": bool(cred.revoked),
        "current_status": current_status,
        "reason": reason,
        "institution_name": payload["institution_name"],
        "programme": payload["programme"],
        "academic_year": payload["academic_year"],
        "issued_at": payload["issued_at"],
        "apaar_id_masked": mask_id(payload["apaar_id"]),
        "student_name_masked": mask_name(payload["student_name"]),
        "details": None,
    }
    actor = "public"

    if consent_id:
        consent = db.get(ConsentRequest, consent_id)
        if not consent or consent.credential_id != credential_id:
            raise HTTPException(404, "Consent not found for this credential")
        if consent.status != "approved":
            raise HTTPException(403, f"Consent is {consent.status}")
        if consent.expires_at < now():
            raise HTTPException(403, "Consent has expired")
        student = db.query(Student).filter_by(apaar_id=cred.apaar_id).first()
        result["details"] = {
            "apaar_id": payload["apaar_id"],
            "student_name": payload["student_name"],
            "dob": payload["dob"],
            "category": student.category if student else None,
            "nationality": student.nationality if student else None,
            "verifier": consent.verifier_name,
            "purpose": consent.purpose,
        }
        actor = consent.verifier_name

    db.add(AuditLog(
        actor=actor,
        action="VERIFY",
        details=f"{credential_id}: valid={result['valid']}, full_details={bool(consent_id)}",
    ))
    db.commit()
    return result