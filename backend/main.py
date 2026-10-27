from fastapi import FastAPI, Depends, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from database import get_db
from models import Student, AuditLog
from schemas import StudentCreate, StudentOut
from validation import validate_csv
from auth import require_roles

app = FastAPI(title="APAAR Student Platform")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    return {"message": "APAAR Student Platform API", "docs": "/docs"}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/students", response_model=StudentOut, status_code=201, dependencies=[Depends(require_roles("aicte"))])
def create_student(data: StudentCreate, db: Session = Depends(get_db)):
    if db.query(Student).filter_by(apaar_id=data.apaar_id).first():
        raise HTTPException(409, "Duplicate APAAR ID")
    student = Student(**data.model_dump())
    db.add(student)
    db.commit()
    db.refresh(student)
    return student


@app.get("/students", response_model=list[StudentOut], dependencies=[Depends(require_roles("aicte"))])
def list_students(db: Session = Depends(get_db)):
    return db.query(Student).all()


@app.get("/students/{apaar_id}", response_model=StudentOut, dependencies=[Depends(require_roles("aicte"))])
def get_student(apaar_id: str, db: Session = Depends(get_db)):
    student = db.query(Student).filter_by(apaar_id=apaar_id).first()
    if not student:
        raise HTTPException(404, "Student not found")
    return student


@app.post("/students/upload", dependencies=[Depends(require_roles("aicte"))])
async def upload_students(
    file: UploadFile = File(...),
    dry_run: bool = False,
    db: Session = Depends(get_db),
):
    if not (file.filename or "").lower().endswith(".csv"):
        raise HTTPException(400, "Please upload a .csv file")
    try:
        text = (await file.read()).decode("utf-8-sig")
    except UnicodeDecodeError:
        raise HTTPException(400, "File must be UTF-8 encoded")

    existing_ids = {row[0] for row in db.query(Student.apaar_id).all()}
    try:
        valid, errors = validate_csv(text, existing_ids)
    except ValueError as e:
        raise HTTPException(400, str(e))

    if not dry_run and valid:
        db.add_all([Student(**r) for r in valid])
        db.add(AuditLog(
            actor="institution",
            action="CSV_UPLOAD",
            details=f"{file.filename}: {len(valid)} accepted, {len(errors)} rejected",
        ))
        db.commit()

    return {
        "dry_run": dry_run,
        "total_rows": len(valid) + len(errors),
        "accepted": len(valid),
        "rejected": len(errors),
        "errors": errors,
    }
from admissions_api import router as admissions_router
app.include_router(admissions_router)

from verification_api import router as verification_router
app.include_router(verification_router)

from auth import router as auth_router
app.include_router(auth_router)

from risk_api import router as risk_router
app.include_router(risk_router)

from certificate import router as certificate_router
app.include_router(certificate_router)

from reports_api import router as reports_router
app.include_router(reports_router)
