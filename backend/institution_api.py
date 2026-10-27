"""Institution-facing dashboard: own programmes, risk flags, admissions list and activity."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from anomaly import analyse
from auth import require_roles
from compliance import programme_counts
from database import get_db
from models import Admission, AuditLog, Institution, Programme, Student, User

router = APIRouter()


def resolve_institution(user: User, institution_code: str | None) -> str:
    """Institution users are fixed to their own code; AICTE must say which one to view."""
    if user.role == "institution":
        if institution_code and institution_code != user.institution_code:
            raise HTTPException(403, "You can only view your own institution")
        return user.institution_code
    if not institution_code:
        raise HTTPException(400, "institution_code is required")
    return institution_code


@router.get("/institution/dashboard")
def institution_dashboard(
    institution_code: str | None = None,
    user: User = Depends(require_roles("institution", "aicte")),
    db: Session = Depends(get_db),
):
    code = resolve_institution(user, institution_code)
    inst = db.query(Institution).filter_by(code=code).first()
    if not inst:
        raise HTTPException(404, "Institution not found")

    programmes = []
    for p in (
        db.query(Programme)
        .filter_by(institution_code=code)
        .order_by(Programme.academic_year.desc(), Programme.name)
        .all()
    ):
        regular, supernumerary = programme_counts(db, code, p.name, p.academic_year)
        excess = max(0, regular - p.approved_intake)
        programmes.append({
            "programme": p.name,
            "academic_year": p.academic_year,
            "approved_intake": p.approved_intake,
            "regular_enrolled": regular,
            "supernumerary_enrolled": supernumerary,
            "total_enrolled": regular + supernumerary,
            "excess": excess,
            "status": "EXCESS" if excess else "OK",
        })

    risk = next((r for r in analyse(db) if r["institution_code"] == code), None)

    # Activity by this institution's own users (plus older entries logged under the code itself)
    usernames = [u for (u,) in db.query(User.username).filter_by(institution_code=code).all()]
    actors = usernames + [code]
    activity = [
        {"time": a.created_at.isoformat(timespec="seconds") if a.created_at else None,
         "actor": a.actor, "action": a.action, "details": a.details}
        for a in db.query(AuditLog)
        .filter(AuditLog.actor.in_(actors))
        .order_by(AuditLog.id.desc())
        .limit(15)
        .all()
    ]

    return {
        "institution": {"code": inst.code, "name": inst.name, "state": inst.state},
        "programmes": programmes,
        "risk": risk and {
            "score": risk["score"], "level": risk["level"], "reasons": risk["reasons"],
        },
        "recent_activity": activity,
    }


@router.get("/institution/admissions")
def institution_admissions(
    programme: str,
    academic_year: str,
    institution_code: str | None = None,
    user: User = Depends(require_roles("institution", "aicte")),
    db: Session = Depends(get_db),
):
    code = resolve_institution(user, institution_code)
    rows = (
        db.query(Admission, Student)
        .join(Student, Admission.student_id == Student.id)
        .filter(
            Admission.institution_id == code,
            Admission.programme == programme,
            Admission.academic_year == academic_year,
        )
        .order_by(Student.name)
        .all()
    )
    return [
        {
            "apaar_id": s.apaar_id,
            "name": s.name,
            "category": s.category,
            "nationality": s.nationality,
            "is_nri": bool(s.is_nri),
            "is_oci": bool(s.is_oci),
            "is_foreign_national": bool(s.is_foreign_national),
            "is_supernumerary": bool(a.is_supernumerary),
            "status": a.status,
        }
        for a, s in rows
    ]
