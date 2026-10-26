import csv
import io
from datetime import date, datetime

REQUIRED_COLUMNS = ["apaar_id", "name", "dob"]
TRUE_VALUES = {"true", "yes", "y", "1"}
FALSE_VALUES = {"false", "no", "n", "0", ""}


def parse_bool(value):
    v = (value or "").strip().lower()
    if v in TRUE_VALUES:
        return True
    if v in FALSE_VALUES:
        return False
    raise ValueError(f"'{value}' is not yes/no")


def validate_csv(text, existing_ids):
    """Returns (valid_rows, errors). Row numbers match the spreadsheet (header = row 1)."""
    reader = csv.DictReader(io.StringIO(text))
    headers = [h.strip().lower() for h in (reader.fieldnames or [])]
    missing = [c for c in REQUIRED_COLUMNS if c not in headers]
    if missing:
        raise ValueError("Missing required columns: " + ", ".join(missing))
    reader.fieldnames = headers

    valid, errors = [], []
    seen = {}

    for n, raw in enumerate(reader, start=2):
        row = {k: (v or "").strip() for k, v in raw.items() if k}
        errs = []

        # 1. APAAR ID: missing, malformed, duplicate in file, already registered
        apaar = row.get("apaar_id", "")
        if not apaar:
            errs.append("Missing APAAR ID")
        elif not (apaar.isdigit() and len(apaar) == 12):
            errs.append("Invalid APAAR ID: must be exactly 12 digits")
        else:
            if apaar in seen:
                errs.append(f"Duplicate APAAR ID in file (first seen at row {seen[apaar]})")
            else:
                seen[apaar] = n
            if apaar in existing_ids:
                errs.append("APAAR ID already registered")

        # 2. Name
        if not row.get("name"):
            errs.append("Missing name")

        # 3. Date of birth
        dob = None
        try:
            dob = datetime.strptime(row.get("dob", ""), "%Y-%m-%d").date()
            if dob >= date.today():
                errs.append("DOB cannot be in the future")
        except ValueError:
            errs.append("Invalid DOB: use YYYY-MM-DD")

        # 4. Flags
        flags = {}
        for f in ("is_nri", "is_oci", "is_foreign_national"):
            try:
                flags[f] = parse_bool(row.get(f, ""))
            except ValueError as e:
                errs.append(f"{f}: {e}")
                flags[f] = False

        # 5. Consistency between nationality and special categories
        nationality = row.get("nationality") or "Indian"
        is_indian = nationality.lower() == "indian"
        if flags["is_foreign_national"] and is_indian:
            errs.append("Marked Foreign National but nationality is Indian")
        if flags["is_oci"] and is_indian:
            errs.append("Marked OCI but nationality is Indian")
        if flags["is_nri"] and flags["is_foreign_national"]:
            errs.append("Cannot be both NRI and Foreign National")

        if errs:
            errors.append({"row": n, "apaar_id": apaar or None, "errors": errs})
        else:
            valid.append({
                "apaar_id": apaar,
                "name": row["name"],
                "dob": dob,
                "category": row.get("category") or None,
                "nationality": nationality,
                **flags,
            })

    return valid, errors