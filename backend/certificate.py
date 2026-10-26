import hmac
import io
import json
import os

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from reportlab.graphics import renderPDF
from reportlab.graphics.barcode import qr
from reportlab.graphics.shapes import Drawing
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from sqlalchemy.orm import Session

from auth import require_roles
from database import get_db
from models import AuditLog, Credential, User
from verification_api import sign

router = APIRouter()

FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")


def build_pdf(payload: dict, credential_id: str, signature: str, student_id_no: str | None) -> bytes:
    buffer = io.BytesIO()
    width, height = landscape(A4)
    c = canvas.Canvas(buffer, pagesize=(width, height))
    c.setTitle("Enrolment certificate")

    # Border
    c.setStrokeColor(colors.HexColor("#2557d6"))
    c.setLineWidth(3)
    c.rect(10 * mm, 10 * mm, width - 20 * mm, height - 20 * mm)
    c.setLineWidth(0.8)
    c.rect(14 * mm, 14 * mm, width - 28 * mm, height - 28 * mm)

    # Heading
    c.setFillColor(colors.HexColor("#1f2933"))
    c.setFont("Helvetica-Bold", 24)
    c.drawCentredString(width / 2, height - 38 * mm, "ENROLMENT CERTIFICATE")
    c.setFont("Helvetica", 12)
    c.drawCentredString(width / 2, height - 47 * mm, payload["institution_name"])

    c.setFont("Helvetica", 12)
    c.drawCentredString(width / 2, height - 62 * mm, "This is to certify that")
    c.setFont("Helvetica-Bold", 20)
    c.drawCentredString(width / 2, height - 73 * mm, payload["student_name"])
    c.setFont("Helvetica", 12)
    c.drawCentredString(
        width / 2,
        height - 83 * mm,
        f"is enrolled in {payload['programme']} for the academic year {payload['academic_year']}.",
    )

    # IDs block
    left = 40 * mm
    y = height - 105 * mm
    rows = [("APAAR ID", payload["apaar_id"])]
    if student_id_no:
        rows.append(("Student ID", student_id_no))
    rows += [
        ("Date of birth", payload["dob"]),
        ("Institution code", payload["institution_code"]),
        ("Credential issued", payload["issued_at"].replace("T", " ")),
    ]
    for label, value in rows:
        c.setFont("Helvetica", 11)
        c.setFillColor(colors.HexColor("#52606d"))
        c.drawString(left, y, label)
        c.setFont("Helvetica-Bold", 12)
        c.setFillColor(colors.HexColor("#1f2933"))
        c.drawString(left + 45 * mm, y, str(value))
        y -= 8 * mm

    # QR code linking to the public verification page
    url = f"{FRONTEND_URL}/?verify={credential_id}"
    widget = qr.QrCodeWidget(url)
    x0, y0, x1, y1 = widget.getBounds()
    size = 40 * mm
    drawing = Drawing(size, size, transform=[size / (x1 - x0), 0, 0, size / (y1 - y0), 0, 0])
    drawing.add(widget)
    qr_x, qr_y = width - 40 * mm - size, 30 * mm
    renderPDF.draw(drawing, c, qr_x, qr_y)
    c.setFont("Helvetica", 8)
    c.setFillColor(colors.HexColor("#52606d"))
    c.drawCentredString(qr_x + size / 2, qr_y - 4 * mm, "Scan to verify")

    # Footer
    c.setFont("Helvetica", 8)
    c.drawString(24 * mm, 30 * mm, f"Credential ID: {credential_id}")
    c.drawString(24 * mm, 25 * mm, f"Digital signature (HMAC-SHA256): {signature[:32]}...")
    c.drawString(24 * mm, 20 * mm, "Verify the authenticity of this certificate by scanning the QR code or entering the credential ID.")

    c.showPage()
    c.save()
    return buffer.getvalue()


@router.get("/credentials/{credential_id}/certificate")
def certificate(
    credential_id: str,
    student_id_no: str | None = Query(None, max_length=40),
    user: User = Depends(require_roles("institution", "aicte")),
    db: Session = Depends(get_db),
):
    cred = db.get(Credential, credential_id)
    if not cred:
        raise HTTPException(404, "Credential not found")

    payload = json.loads(cred.payload)
    if not hmac.compare_digest(sign(payload), cred.signature):
        raise HTTPException(409, "Credential failed the signature check")
    if cred.revoked:
        raise HTTPException(409, "Credential has been revoked")
    if user.role == "institution" and user.institution_code != payload["institution_code"]:
        raise HTTPException(403, "You can only print certificates for your own institution")

    pdf = build_pdf(payload, credential_id, cred.signature, (student_id_no or "").strip() or None)
    db.add(AuditLog(actor=user.username, action="CERTIFICATE_GENERATED", details=credential_id))
    db.commit()
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="certificate-{credential_id[:8]}.pdf"'},
    )