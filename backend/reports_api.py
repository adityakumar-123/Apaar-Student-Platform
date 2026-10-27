import csv
import io

from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy.orm import Session

from admissions_api import intake_report
from anomaly import analyse
from auth import require_roles
from database import get_db
from models import AuditLog, User

router = APIRouter()


def safe(value):
    """Stop spreadsheet apps from running text that starts with = + - @ as a formula."""
    text = "" if value is None else str(value)
    return "'" + text if text[:1] in ("=", "+", "-", "@") else text


def csv_response(rows, filename):
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    for row in rows:
        writer.writerow([safe(v) for v in row])
    # utf-8-sig adds a marker so Excel opens the file with the right encoding
    return Response(
        content=buffer.getvalue().encode("utf-8-sig"),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def log(db, user, action, details=""):
    db.add(AuditLog(actor=user.username, action=action, details=details))
    db.commit()


@router.get("/reports/intake.csv")
def intake_csv(
    academic_year: str | None = None,
    user: User = Depends(require_roles("aicte")),
    db: Session = Depends(get_db),
):
    data = intake_report(academic_year=academic_year, db=db)
    rows = [[
        "Institution", "Programme", "Academic year", "Approved intake",
        "Regular enrolled", "Supernumerary enrolled", "Total enrolled", "Excess", "Status",
    ]]
    for r in data:
        rows.append([
            r["institution_code"], r["programme"], r["academic_year"], r["approved_intake"],
            r["regular_enrolled"], r["supernumerary_enrolled"], r["total_enrolled"],
            r["excess"], r["status"],
        ])
    log(db, user, "REPORT_EXPORTED", f"intake {academic_year or 'all years'}")
    return csv_response(rows, "intake-report.csv")


@router.get("/reports/risk.csv")
def risk_csv(
    user: User = Depends(require_roles("aicte")),
    db: Session = Depends(get_db),
):
    rows = [["Institution", "Name", "State", "Risk score", "Level", "Reason points", "Reason"]]
    for inst in analyse(db):
        if not inst["reasons"]:
            rows.append([inst["institution_code"], inst["institution_name"], inst["state"],
                         inst["score"], inst["level"], "", "No flags"])
        for reason in inst["reasons"]:
            rows.append([inst["institution_code"], inst["institution_name"], inst["state"],
                         inst["score"], inst["level"], reason["points"], reason["text"]])
    log(db, user, "REPORT_EXPORTED", "risk scores")
    return csv_response(rows, "risk-report.csv")