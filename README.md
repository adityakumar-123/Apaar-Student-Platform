# APAAR Student Data Management and Verification Platform

A platform for AICTE-approved institutions to submit student-level admission data keyed on **APAAR ID**, with automated validation, intake monitoring, verifiable credentials and an AICTE dashboard.

Built for the Smart India Hackathon problem statement: *APAAR ID-Based Student Data Management and Verification Platform for AICTE-Approved Institutions* (AICTE, Regulation Bureau).

**Author:** Aditya Kumar (adityakumargen4@gmail.com)

## Features

- **Institution upload:** CSV upload with a *dry run* mode that validates without saving
- **APAAR validation:** missing, malformed (not 12 digits) and duplicate APAAR IDs
- **Data consistency checks:** NRI, OCI and Foreign National flags checked against nationality; invalid or future DOB
- **Cross-institution duplicate enrolment:** the same APAAR ID admitted at two places in the same year is rejected
- **Identity mismatch detection:** an APAAR ID already registered with a different name or DOB is rejected
- **Intake monitoring:** enrolment is derived from admission rows (never typed in), compared with approved intake; supernumerary seats are tracked separately
- **AICTE dashboard:** programme-wise intake vs enrolment with EXCESS flags
- **Signed credentials:** HMAC-SHA256 signed records with QR verification and a certificate PDF
- **Consent-based verification:** OTP-based student consent for employers and regulators
- **Authentication and roles:** JWT login with `aicte`, `institution` and `verifier` roles
- **Anomaly detection:** explainable institution risk scores
- **Reports:** CSV exports for intake and risk
- **Audit log:** uploads, certificate prints and exports are recorded
- **Database migrations:** Alembic
- **Docker:** one-command setup with Docker Compose

## Planned

- Real APAAR/DigiLocker API integration (a mock adapter with the same contract will be used until access is granted)
- Asymmetric signatures (Ed25519 or W3C Verifiable Credentials) and an SMS/DigiLocker OTP gateway
- Login rate limiting and account lockout
- PDF reports and scheduled exports

## Tech stack

| Layer | Technology |
|---|---|
| Backend | FastAPI, SQLAlchemy, Alembic, Pydantic |
| Database | SQLite (prototype), PostgreSQL-ready |
| Frontend | React (Vite) |
| Deployment | Docker Compose |

## Project structure

```
Apaar-Student-Platform/
├── backend/
│   ├── main.py               # FastAPI app and student endpoints
│   ├── admissions_api.py     # institutions, programmes, admissions upload, compliance report
│   ├── verification_api.py   # credentials, verification, consent
│   ├── risk_api.py           # risk score endpoint
│   ├── reports_api.py        # CSV report exports
│   ├── auth.py               # JWT authentication and roles
│   ├── validation.py         # row-level CSV validation
│   ├── compliance.py         # intake and duplicate-enrolment helpers
│   ├── anomaly.py            # risk rules and thresholds
│   ├── certificate.py        # certificate PDF with QR code
│   ├── seed_users.py         # demo accounts
│   ├── models.py             # SQLAlchemy models
│   ├── schemas.py            # Pydantic schemas
│   ├── database.py
│   ├── migrations/           # Alembic migrations
│   └── sample_data/          # CSV files for testing
├── frontend/                 # React app
├── docker-compose.yml
└── .env.example
```

## Run locally

Requires Python 3.10+ and Node.js 18+.

### Backend

```bash
cd backend
pip install -r requirements.txt
python -m alembic upgrade head
python seed_users.py
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

### Docker

```bash
cp .env.example .env    # then change the secrets
docker compose up --build
```

The backend (http://localhost:8000) applies migrations and creates the demo users on start. The frontend is at http://localhost:5173.

## Configuration

| Variable | Purpose |
|---|---|
| `JWT_SECRET` | Signs login tokens |
| `SIGNING_SECRET` | Signs credentials |
| `DEMO_MODE` | `true` returns the consent OTP in the API response; set `false` for any real deployment |
| `FRONTEND_URL` | Base URL the certificate QR code points to |
| `DATABASE_URL` | Database connection string |

Always set your own `JWT_SECRET` and `SIGNING_SECRET` outside local demos.

## Demo accounts

Created by `python seed_users.py` (demo only, never reuse these passwords):

| Username | Password | Role |
|---|---|---|
| aicte_admin | Aicte@123 | aicte: full access, dashboard |
| inst001_operator | Inst001@123 | institution (INST001): upload for own institution, issue credentials |
| inst002_operator | Inst002@123 | institution (INST002) |
| employer_demo | Verify@123 | verifier: request consent |

Verifying a credential (masked result) and student OTP approval need no login.

## Demo walkthrough

1. Log in as `aicte_admin`. In http://127.0.0.1:8000/docs, create institutions with `POST /institutions`:
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
| GET | `/compliance/risk` | Institution risk scores (AICTE only) |
| POST/GET | `/students` | Create and list students |
| POST | `/students/upload` | Student-only CSV upload |
| POST | `/credentials/{apaar_id}` | Issue a signed credential |
| GET | `/credentials/{credential_id}/certificate` | Certificate PDF |
| GET | `/verify/{credential_id}` | Public verification (masked identity) |
| POST | `/credentials/{credential_id}/revoke` | Revoke a credential (AICTE only) |
| POST | `/consent/request` | Request consent to view full details |
| POST | `/consent/{id}/approve` | Student approves with OTP |
| GET | `/reports/intake.csv`, `/reports/risk.csv` | CSV exports (AICTE only) |

## Verification and consent

- `POST /credentials/{apaar_id}` issues an HMAC-SHA256 signed credential with a QR code
- `GET /verify/{credential_id}` gives a public result with masked identity; altered records fail the signature check
- `POST /consent/request` and `POST /consent/{id}/approve` implement OTP-based student consent; full details are shown only after approval (valid for 10 minutes)

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

## Reports

AICTE users can download CSV reports from the dashboard: `GET /reports/intake.csv` (intake vs enrolment per programme, optional `academic_year` filter) and `GET /reports/risk.csv` (risk scores with each reason). Files open in Excel, cells starting with `=`, `+`, `-` or `@` are escaped, and every export is audit-logged. PDF reports and scheduled exports are not built yet.

## Limitations

- APAAR IDs are checked for format only. Real registry verification needs government API access.
- Credentials use a shared-secret HMAC signature; production would use asymmetric signatures.
- No login rate limiting or account lockout yet, tokens live in sessionStorage, and HTTPS is required in production.
- SQLite is used for the prototype.
