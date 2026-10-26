from collections import defaultdict
from difflib import SequenceMatcher
from statistics import mean, pstdev

from sqlalchemy.orm import Session

from compliance import programme_counts
from models import Admission, Institution, Programme, Student

# Tunable thresholds
SUPERNUMERARY_SHARE_LIMIT = 0.20
SPECIAL_CATEGORY_SHARE_LIMIT = 0.30
NAME_SIMILARITY = 0.85
PEER_Z_LIMIT = 2.0
MIN_PEERS_FOR_Z = 5
NEAR_DUPLICATE_CAP = 30


def level_for(score: int) -> str:
    if score >= 50:
        return "HIGH"
    if score >= 25:
        return "MEDIUM"
    return "LOW"


def normalise(name: str) -> str:
    return " ".join(name.lower().split())


def find_near_duplicates(students):
    """students: list of (student_id, apaar_id, name, dob, institution_code)."""
    by_dob = defaultdict(list)
    for s in students:
        by_dob[s[3]].append(s)
    pairs = []
    for group in by_dob.values():
        for i in range(len(group)):
            for j in range(i + 1, len(group)):
                a, b = group[i], group[j]
                if a[1] == b[1]:
                    continue
                if SequenceMatcher(None, normalise(a[2]), normalise(b[2])).ratio() >= NAME_SIMILARITY:
                    pairs.append((a, b))
    return pairs


def analyse(db: Session):
    out = {
        i.code: {
            "institution_code": i.code,
            "institution_name": i.name,
            "state": i.state,
            "score": 0,
            "level": "LOW",
            "reasons": [],
            "metrics": {},
        }
        for i in db.query(Institution).all()
    }

    def flag(code, points, text):
        entry = out.get(code)
        if entry:
            entry["score"] += points
            entry["reasons"].append({"points": points, "text": text})

    # Rules 1 and 2: per programme
    for p in db.query(Programme).all():
        regular, supernumerary = programme_counts(db, p.institution_code, p.name, p.academic_year)
        total = regular + supernumerary
        label = f"{p.name} {p.academic_year}"
        if regular > p.approved_intake:
            excess = regular - p.approved_intake
            points = min(40, round(10 + 30 * excess / p.approved_intake))
            flag(p.institution_code, points,
                 f"{label}: regular enrolment {regular} exceeds approved intake {p.approved_intake} by {excess}")
        if total and supernumerary / total > SUPERNUMERARY_SHARE_LIMIT:
            flag(p.institution_code, 15,
                 f"{label}: {round(100 * supernumerary / total)}% of admissions are supernumerary "
                 f"({supernumerary} of {total})")

    # Rule 3: NRI / OCI / Foreign National share, plus comparison with peers
    rows = (
        db.query(Admission.institution_id, Student.is_nri, Student.is_oci, Student.is_foreign_national)
        .join(Student, Admission.student_id == Student.id)
        .filter(Admission.status == "admitted")
        .all()
    )
    totals, specials = defaultdict(int), defaultdict(int)
    for code, nri, oci, fn in rows:
        totals[code] += 1
        if nri or oci or fn:
            specials[code] += 1
    shares = {c: specials[c] / totals[c] for c in totals}

    for code, share in shares.items():
        if code in out:
            out[code]["metrics"] = {
                "total_enrolled": totals[code],
                "special_category_share": round(share, 3),
            }
        if share > SPECIAL_CATEGORY_SHARE_LIMIT:
            flag(code, 15,
                 f"{round(100 * share)}% of admitted students are NRI/OCI/Foreign National "
                 f"({specials[code]} of {totals[code]})")

    if len(shares) >= MIN_PEERS_FOR_Z:
        mu, sd = mean(shares.values()), pstdev(shares.values())
        if sd > 0:
            for code, share in shares.items():
                z = (share - mu) / sd
                if z > PEER_Z_LIMIT:
                    flag(code, 10,
                         f"Special-category share is {z:.1f} standard deviations above other institutions")

    # Rule 4: possible duplicate identities (same DOB, similar name, different APAAR ID)
    students = {}
    for sid, apaar, name, dob, code in (
        db.query(Student.id, Student.apaar_id, Student.name, Student.dob, Admission.institution_id)
        .join(Admission, Admission.student_id == Student.id)
        .filter(Admission.status == "admitted")
        .all()
    ):
        students[sid] = (sid, apaar, name, dob, code)

    near_points = defaultdict(int)
    for a, b in find_near_duplicates(list(students.values())):
        text = (
            f"Possible duplicate identity: '{a[2]}' and '{b[2]}' share date of birth "
            f"{a[3].isoformat()} but have different APAAR IDs (...{a[1][-4:]} / ...{b[1][-4:]})"
        )
        for code in {a[4], b[4]}:
            if near_points[code] + 10 <= NEAR_DUPLICATE_CAP:
                near_points[code] += 10
                flag(code, 10, text)

    result = []
    for entry in out.values():
        entry["score"] = min(100, entry["score"])
        entry["level"] = level_for(entry["score"])
        entry["reasons"].sort(key=lambda r: -r["points"])
        result.append(entry)
    return sorted(result, key=lambda e: -e["score"])