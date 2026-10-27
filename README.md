# APAAR Student Data Management and Verification Platform

A platform for AICTE-approved institutions to submit student-level admission data keyed on **APAAR ID**, with automated validation, intake monitoring and an AICTE dashboard.

Built for the Smart India Hackathon problem statement: *APAAR ID-Based Student Data Management and Verification Platform for AICTE-Approved Institutions* (AICTE, Regulation Bureau).

**Author:** Aditya Kumar (adityakumargen4@gmail.com)

## Features (implemented)

- **Institution upload:** CSV upload with a *dry run* mode that validates without saving
- **APAAR validation:** missing, malformed (not 12 digits) and duplicate APAAR IDs
- **Data consistency checks:** NRI, OCI and Foreign National flags checked against nationality; invalid or future DOB
- **Cross-institution duplicate enrolment:** the same APAAR ID admitted at two places in the same year is rejected
- **Identity mismatch detection:** an APAAR ID already registered with a different name or DOB is rejected
- **Intake monitoring:** enrolment is derived from admission rows (never typed in), compared with approved intake; supernumerary seats are tracked separately
- **AICTE dashboard:** programme-wise intake vs enrolment with EXCESS flags
- **Audit log:** every upload is recorded
- **Database migrations:** Alembic

## Planned

- Signed verifiable student records with QR verification
- Consent-based verification for employers and regulators
- Role-based access control and authentication
- Anomaly detection and institution risk scores
- Real APAAR/DigiLocker API integration (a mock adapter will be used until access is granted)

## Tech stack

| Layer | Technology |
|---|---|
| Backend | FastAPI, SQLAlchemy, Alembic, Pydantic |
| Database | SQLite (prototype), PostgreSQL-ready |
| Frontend | React (Vite) |

## Project structure

```
Apaar-Student-Platform/
├── backend/
│   ├── main.py             # FastAPI app and student endpoints
│   ├── admissions_api.py   # institutions, programmes, admissions upload, compliance report
│   ├── validation.py       # row-level CSV validation
│   ├── compliance.py       # intake and duplicate-enrolment helpers
│   ├── models.py           # SQLAlchemy models
│   ├── schemas.py          # Pydantic schemas
│   ├── database.py
│   ├── migrations/         # Alembic migrations
│   └── sample_data/        # CSV files for testing
└── frontend/               # React app
```

## Run locally

Requires Python 3.10+ and Node.js 18+.

### Backend

```bash
cd backend
pip install -r requirements.txt
python -m alembic upgrade head
python -m uvicorn main:app --reload
```

API docs: http://127.0.0.1:8000/docs

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173. To use a different API address, create `frontend/.env` with `VITE_API_URL=http://127.0.0.1:8000`.

## Demo walkthrough

1. In http://127.0.0.1:8000/docs, create institutions with `POST /institutions`:
   ```json
   {"code": "INST001", "name": "Demo Institute of Technology", "state": "Delhi"}
   ```
   ```json
   {"code": "INST002", "name": "Demo Business School", "state": "Maharashtra"}
   ```
2. Create programmes with `POST /programmes`:
   ```json
   {"institution_code": "INST001", "name": "B.Tech CSE", "academic_year": "2025-26", "approved_intake": 3}
   ```
   ```json
   {"institution_code": "INST002", "name": "MBA", "academic_year": "2025-26", "approved_intake": 5}
   ```
3. Open the React app, go to **Institution upload**, choose `backend/sample_data/btech_cse_batch.csv` (INST001, B.Tech CSE, 2025-26) and run a **dry run**. The result warns that regular enrolment 4 exceeds approved intake 3.
4. Untick *Dry run* and save, then open **AICTE dashboard**. B.Tech CSE shows an **EXCESS +1** badge.
5. Upload `backend/sample_data/mba_batch.csv` to INST002 / MBA. Two rows are rejected: one potential duplicate enrolment at INST001 and one APAAR ID registered with a different name or DOB.
6. Upload `btech_cse_batch.csv` again to see every row rejected as already admitted.

## CSV format

```
apaar_id,name,dob,category,nationality,is_nri,is_oci,is_foreign_national,is_supernumerary
```

`apaar_id`, `name` and `dob` (YYYY-MM-DD) are required. Flags accept yes/no, true/false or 1/0.

## API overview

| Method | Endpoint | Purpose |
|---|---|---|
| POST | `/institutions` | Register an institution |
| POST | `/programmes` | Define a programme and its approved intake |
| POST | `/admissions/upload` | Upload admissions CSV (supports `dry_run`) |
| GET | `/compliance/intake` | Intake vs enrolment report |
| POST/GET | `/students` | Create and list students |
| POST | `/students/upload` | Student-only CSV upload |

## Limitations

- APAAR IDs are checked for format only. Real registry verification needs government API access; a mock adapter with the same contract is planned.
- No authentication yet.
- SQLite is used for the prototype.
## Verification and consent

- `POST /credentials/{apaar_id}` issues an HMAC-SHA256 signed credential with a QR code
- `GET /verify/{credential_id}` gives a public result with masked identity; altered records fail the signature check
- `POST /consent/request` and `POST /consent/{id}/approve` implement OTP-based student consent; full details are shown only after approval (valid for 10 minutes)
- Set `SIGNING_SECRET` in the environment for any real deployment; `DEMO_MODE=false` stops the OTP being returned in the API response
- Production would use asymmetric signatures (for example Ed25519 or W3C Verifiable Credentials) and an SMS/DigiLocker OTP gateway

## Authentication and roles

Run `python seed_users.py` from `backend` after the migrations to create demo accounts (demo only, never reuse these passwords):

| Username | Password | Role |
|---|---|---|
| aicte_admin | Aicte@123 | aicte: full access, dashboard |
| inst001_operator | Inst001@123 | institution (INST001): upload for own institution, issue credentials |
| inst002_operator | Inst002@123 | institution (INST002) |
| employer_demo | Verify@123 | verifier: request consent |

Verification of a credential (masked result) and student OTP approval need no login. Set `JWT_SECRET` and `SIGNING_SECRET` in the environment for any real deployment.

Limitations: no login rate limiting or account lockout yet, tokens live in sessionStorage, and HTTPS is required in production.

## Anomaly detection and risk scores

`GET /compliance/risk` (AICTE only) scores each institution from 0 to 100 using transparent, explainable rules:

| Rule | Points |
|---|---|
| Regular enrolment above approved intake | 10-40, scaled by excess |
| Supernumerary share above 20% | 15 |
| NRI/OCI/Foreign National share above 30% | 15 |
| Special-category share more than 2 standard deviations above peers (5+ institutions) | 10 |
| Possible duplicate identity (same DOB, similar name, different APAAR ID) | 10 each, max 30 |

Levels: LOW below 25, MEDIUM 25-49, HIGH 50 and above. Every flag carries a plain-language reason. Thresholds are constants in `backend/anomaly.py`. A flag means review, not wrongdoing. With real national-scale data, an unsupervised model such as Isolation Forest could be added on top of these rules.

## Anomaly detection and risk scores

`GET /compliance/risk` (AICTE only) scores each institution from 0 to 100 using transparent, explainable rules:

| Rule | Points |
|---|---|
| Regular enrolment above approved intake | 10-40, scaled by excess |
| Supernumerary share above 20% | 15 |
| NRI/OCI/Foreign National share above 30% | 15 |
| Special-category share more than 2 standard deviations above peers (5+ institutions) | 10 |
| Possible duplicate identity (same DOB, similar name, different APAAR ID) | 10 each, max 30 |

Levels: LOW below 25, MEDIUM 25-49, HIGH 50 and above. Every flag carries a plain-language reason. Thresholds are constants in `backend/anomaly.py`. A flag means review, not wrongdoing. With real national-scale data, an unsupervised model such as Isolation Forest could be added on top of these rules.

## Certificate with APAAR ID

`GET /credentials/{credential_id}/certificate?student_id_no=...` (institution or AICTE login) returns a PDF showing the student's APAAR ID next to the institution's student ID, the programme, and a QR code that opens the public verification page. It is only produced for credentials that pass the signature check and are not revoked, an institution can only print its own, and each print is audit-logged. Set `FRONTEND_URL` so the QR points at the deployed site. Names are drawn with a built-in Latin font, so non-Latin scripts would need an embedded font.

## Certificate with APAAR ID

`GET /credentials/{credential_id}/certificate?student_id_no=...` (institution or AICTE login) returns a PDF showing the student's APAAR ID next to the institution's student ID, the programme, and a QR code that opens the public verification page. It is only produced for credentials that pass the signature check and are not revoked, an institution can only print its own, and each print is audit-logged. Set `FRONTEND_URL` so the QR points at the deployed site. Names are drawn with a built-in Latin font, so non-Latin scripts would need an embedded font.

## Certificate with APAAR ID

`GET /credentials/{credential_id}/certificate?student_id_no=...` (institution or AICTE login) returns a PDF showing the student's APAAR ID next to the institution's student ID, the programme, and a QR code that opens the public verification page. It is only produced for credentials that pass the signature check and are not revoked, an institution can only print its own, and each print is audit-logged. Set `FRONTEND_URL` so the QR points at the deployed site. Names are drawn with a built-in Latin font, so non-Latin scripts would need an embedded font.

## Certificate with APAAR ID

`GET /credentials/{credential_id}/certificate?student_id_no=...` (institution or AICTE login) returns a PDF showing the student's APAAR ID next to the institution's student ID, the programme, and a QR code that opens the public verification page. It is only produced for credentials that pass the signature check and are not revoked, an institution can only print its own, and each print is audit-logged. Set `FRONTEND_URL` so the QR points at the deployed site. Names are drawn with a built-in Latin font, so non-Latin scripts would need an embedded font.

## Certificate with APAAR ID

`GET /credentials/{credential_id}/certificate?student_id_no=...` (institution or AICTE login) returns a PDF showing the student's APAAR ID next to the institution's student ID, the programme, and a QR code that opens the public verification page. It is only produced for credentials that pass the signature check and are not revoked, an institution can only print its own, and each print is audit-logged. Set `FRONTEND_URL` so the QR points at the deployed site. Names are drawn with a built-in Latin font, so non-Latin scripts would need an embedded font.

## Reports

AICTE users can download CSV reports from the dashboard: `GET /reports/intake.csv` (intake vs enrolment per programme, optional `academic_year` filter) and `GET /reports/risk.csv` (risk scores with each reason). Files open in Excel, cells starting with `=`, `+`, `-` or `@` are escaped, and every export is audit-logged. PDF reports and scheduled exports are not built yet.
