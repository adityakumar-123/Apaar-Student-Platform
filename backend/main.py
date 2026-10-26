from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from database import get_db
from models import Student
from schemas import StudentCreate, StudentOut

app = FastAPI(title="APAAR Student Platform")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
@app.get("/")
def root():
    return {"message": "APAAR Student Platform API", "docs": "/docs"}
def health():
    return {"status": "ok"}


@app.post("/students", response_model=StudentOut, status_code=201)
def create_student(data: StudentCreate, db: Session = Depends(get_db)):
    if db.query(Student).filter_by(apaar_id=data.apaar_id).first():
        raise HTTPException(409, "Duplicate APAAR ID")
    student = Student(**data.model_dump())
    db.add(student)
    db.commit()
    db.refresh(student)
    return student


@app.get("/students", response_model=list[StudentOut])
def list_students(db: Session = Depends(get_db)):
    return db.query(Student).all()


@app.get("/students/{apaar_id}", response_model=StudentOut)
def get_student(apaar_id: str, db: Session = Depends(get_db)):
    student = db.query(Student).filter_by(apaar_id=apaar_id).first()
    if not student:
        raise HTTPException(404, "Student not found")
    return student