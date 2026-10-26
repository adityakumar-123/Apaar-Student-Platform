from sqlalchemy import Column, Integer, String, Date, Boolean, DateTime, ForeignKey, func
from sqlalchemy.orm import declarative_base

Base = declarative_base()

class Student(Base):
    __tablename__ = "students"
    id = Column(Integer, primary_key=True)
    apaar_id = Column(String(12), unique=True, nullable=False, index=True)
    name = Column(String(150), nullable=False)
    dob = Column(Date, nullable=False)
    category = Column(String(20))
    nationality = Column(String(50))
    is_nri = Column(Boolean, default=False)
    is_oci = Column(Boolean, default=False)
    is_foreign_national = Column(Boolean, default=False)

class Admission(Base):
    __tablename__ = "admissions"
    id = Column(Integer, primary_key=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False)
    institution_id = Column(String(20), nullable=False, index=True)
    programme = Column(String(100), nullable=False)
    academic_year = Column(String(9), nullable=False)
    is_supernumerary = Column(Boolean, default=False)
    status = Column(String(20), default="admitted")

class AuditLog(Base):
    __tablename__ = "audit_logs"
    id = Column(Integer, primary_key=True)
    actor = Column(String(100))
    action = Column(String(50))
    details = Column(String(500))
    created_at = Column(DateTime, server_default=func.now())

from sqlalchemy import UniqueConstraint


class Institution(Base):
    __tablename__ = "institutions"
    id = Column(Integer, primary_key=True)
    code = Column(String(20), unique=True, nullable=False, index=True)
    name = Column(String(200), nullable=False)
    state = Column(String(50))


class Programme(Base):
    __tablename__ = "programmes"
    id = Column(Integer, primary_key=True)
    institution_code = Column(String(20), ForeignKey("institutions.code"), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    academic_year = Column(String(9), nullable=False)
    approved_intake = Column(Integer, nullable=False)
    __table_args__ = (
        UniqueConstraint("institution_code", "name", "academic_year", name="uq_programme"),
    )
