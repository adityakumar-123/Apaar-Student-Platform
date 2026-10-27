from datetime import date

from validation import consistency_errors, validate_csv
from .conftest import make_csv


def errors_for(csv_text, existing=None):
    _, errors = validate_csv(csv_text, existing or set())
    return [e for err in errors for e in err["errors"]]


def test_clean_row_is_accepted():
    valid, errors = validate_csv(make_csv("100000000001,Riya Sharma,2005-03-12,General,Indian,no,no,no,no"), set())
    assert len(valid) == 1 and not errors
    assert valid[0]["dob"] == date(2005, 3, 12)


def test_missing_and_malformed_apaar_ids():
    msgs = errors_for(make_csv(
        ",Karan,2004-07-09,General,Indian,no,no,no,no",
        "12345,Neha,2005-01-20,SC,Indian,no,no,no,no",
        "10000000000A,Meera,2005-01-20,SC,Indian,no,no,no,no",
    ))
    assert msgs.count("Missing APAAR ID") == 1
    assert sum("must be exactly 12 digits" in m for m in msgs) == 2


def test_duplicate_in_file_and_already_registered():
    row = "100000000002,Aman,2004-11-02,OBC,Indian,no,no,no,no"
    msgs = errors_for(make_csv(row, row), existing={"100000000002"})
    assert any("Duplicate APAAR ID in file" in m for m in msgs)
    assert any("already registered" in m for m in msgs)


def test_dob_checks():
    msgs = errors_for(make_csv(
        "100000000003,A,2999-01-01,General,Indian,no,no,no,no",
        "100000000004,B,01/02/2005,General,Indian,no,no,no,no",
    ))
    assert "DOB cannot be in the future" in msgs
    assert any("Invalid DOB" in m for m in msgs)


def test_special_category_consistency():
    assert "Marked Foreign National but nationality is Indian" in consistency_errors("Indian", {"is_foreign_national": True})
    assert "Marked OCI but nationality is Indian" in consistency_errors("Indian", {"is_oci": True})
    assert "Cannot be both NRI and Foreign National" in consistency_errors("German", {"is_nri": True, "is_foreign_national": True})
    assert consistency_errors("German", {"is_foreign_national": True}) == []
    assert consistency_errors("Indian", {"is_nri": True}) == []


def test_missing_required_column_raises():
    import pytest
    with pytest.raises(ValueError):
        validate_csv("apaar_id,name\n100000000001,X\n", set())
