from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from database import get_db
from models import Student, Admission, AuditLog, Institution, Programme
from validation import validate_csv
from compliance import read_supernumerary, find_active_admission, programme_counts

router = APIRouter()


class InstitutionIn(BaseModel):
    code: str
    name: str
    state: str | None = None


class ProgrammeIn(BaseModel):
    institution_code: str
    name: str
    academic_year: str  # e.g. "2025-26"
    approved_intake: int = Field(gt=0)


@router.post("/institutions", status_code=201)
def create_institution(data: InstitutionIn, db: Session = Depends(get_db)):
    if db.query(Institution).filter_by(code=data.code).first():
        raise HTTPException(409, "Institution code already exists")
    inst = Institution(**data.model_dump())
    db.add(inst)
    db.commit()
    return {"id": inst.id, **data.model_dump()}


@router.post("/programmes", status_code=201)
def create_programme(data: ProgrammeIn, db: Session = Depends(get_db)):
    if not db.query(Institution).filter_by(code=data.institution_code).first():
        raise HTTPException(404, "Institution not found")
    exists = db.query(Programme).filter_by(
        institution_code=data.institution_code,
        name=data.name,
        academic_year=data.academic_year,
    ).first()
    if exists:
        raise HTTPException(409, "Programme already defined for this year")
    prog = Programme(**data.model_dump())
    db.add(prog)
    db.commit()
    return {"id": prog.id, **data.model_dump()}


@router.post("/admissions/upload")
async def upload_admissions(
    institution_code: str = Form(...),
    programme: str = Form(...),
    academic_year: str = Form(...),
    dry_run: bool = Form(False),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    prog = db.query(Programme).filter_by(
        institution_code=institution_code, name=programme, academic_year=academic_year
    ).first()
    if not prog:
        raise HTTPException(404, "Programme not found. Create it with POST /programmes first")

    if not (file.filename or "").lower().endswith(".csv"):
        raise HTTPException(400, "Please upload a .csv file")
    try:
        text = (await file.read()).decode("utf-8-sig")
    except UnicodeDecodeError:
        raise HTTPException(400, "File must be UTF-8 encoded")

    # Row-level validation (APAAR format, duplicates in file, flag consistency).
    # Students may already exist from earlier uploads, so we pass an empty set here.
    try:
        valid, errors = validate_csv(text, set())
    except ValueError as e:
        raise HTTPException(400, str(e))

    super_map = read_supernumerary(text)

    # Cross-record checks against the database
    accepted = []
    for row in valid:
        student = db.query(Student).filter_by(apaar_id=row["apaar_id"]).first()
        if student:
            same_person = (
                student.dob == row["dob"]
                and student.name.strip().lower() == row["name"].strip().lower()
            )
            if not same_person:
                errors.append({
                    "row": None,
                    "apaar_id": row["apaar_id"],
                    "errors": ["APAAR ID already registered with different name or DOB"],
                })
                continue
            existing = find_active_admission(db, student.id, academic_year)
            if existing:
                if existing.institution_id == institution_code and existing.programme == programme:
                    msg = "Already admitted in this programme"
                else:
                    msg = (
                        "Potential duplicate enrolment: already admitted at "
                        f"{existing.institution_id} / {existing.programme}"
                    )
                errors.append({"row": None, "apaar_id": row["apaar_id"], "errors": [msg]})
                continue
        accepted.append((row, student))

    # Intake check: enrolment is derived from rows, never typed in
    regular_now, super_now = programme_counts(db, institution_code, programme, academic_year)
    added_super = sum(1 for r, _ in accepted if super_map.get(r["apaar_id"], False))
    added_regular = len(accepted) - added_super
    projected_regular = regular_now + added_regular
    excess = max(0, projected_regular - prog.approved_intake)
    warnings = []
    if excess:
        warnings.append(
            f"Regular enrolment {projected_regular} exceeds approved intake "
            f"{prog.approved_intake} by {excess}"
        )

    if not dry_run and accepted:
        for row, student in accepted:
            if not student:
                student = Student(**row)
                db.add(student)
                db.flush()
            db.add(Admission(
                student_id=student.id,
                institution_id=institution_code,
                programme=programme,
                academic_year=academic_year,
                is_supernumerary=super_map.get(row["apaar_id"], False),
                status="admitted",
            ))
        db.add(AuditLog(
            actor=institution_code,
            action="ADMISSIONS_UPLOAD",
            details=(
                f"{file.filename}: {len(accepted)} accepted, {len(errors)} rejected, "
                f"{excess} over intake"
            ),
        ))
        db.commit()

    return {
        "dry_run": dry_run,
        "approved_intake": prog.approved_intake,
        "total_rows": len(accepted) + len(errors),
        "accepted": len(accepted),
        "rejected": len(errors),
        "projected_regular_enrolment": projected_regular,
        "projected_supernumerary": super_now + added_super,
        "warnings": warnings,
        "errors": errors,
    }


@router.get("/compliance/intake")
def intake_report(academic_year: str | None = None, db: Session = Depends(get_db)):
    query = db.query(Programme)
    if academic_year:
        query = query.filter(Programme.academic_year == academic_year)
    report = []
    for p in query.all():
        regular, supernumerary = programme_counts(db, p.institution_code, p.name, p.academic_year)
        excess = max(0, regular - p.approved_intake)
        report.append({
            "institution_code": p.institution_code,
            "programme": p.name,
            "academic_year": p.academic_year,
            "approved_intake": p.approved_intake,
            "regular_enrolled": regular,
            "supernumerary_enrolled": supernumerary,
            "total_enrolled": regular + supernumerary,
            "excess": excess,
            "status": "EXCESS" if excess else "OK",
        })
    return report