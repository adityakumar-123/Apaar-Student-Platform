import csv
import io

from sqlalchemy import func

from models import Admission
from validation import parse_bool


def read_supernumerary(text):
    """Map apaar_id -> True/False from the optional is_supernumerary column."""
    result = {}
    reader = csv.DictReader(io.StringIO(text))
    reader.fieldnames = [h.strip().lower() for h in (reader.fieldnames or [])]
    for raw in reader:
        apaar = (raw.get("apaar_id") or "").strip()
        try:
            flag = parse_bool(raw.get("is_supernumerary"))
        except ValueError:
            flag = False
        result.setdefault(apaar, flag)
    return result


def find_active_admission(db, student_id, academic_year):
    return (
        db.query(Admission)
        .filter(
            Admission.student_id == student_id,
            Admission.academic_year == academic_year,
            Admission.status == "admitted",
        )
        .first()
    )


def programme_counts(db, institution_code, programme, academic_year):
    """Returns (regular_enrolled, supernumerary_enrolled), derived from admission rows."""
    base = db.query(func.count(Admission.id)).filter(
        Admission.institution_id == institution_code,
        Admission.programme == programme,
        Admission.academic_year == academic_year,
        Admission.status == "admitted",
    )
    total = base.scalar()
    supernumerary = base.filter(Admission.is_supernumerary.is_(True)).scalar()
    return total - supernumerary, supernumerary