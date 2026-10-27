"""APAAR registry adapter.

The real APAAR / DigiLocker API needs government access. Until then the platform uses
this adapter with the same contract, so swapping in the real client later only means
adding another class with a ``lookup`` method.

Set APAAR_REGISTRY=mock to check every uploaded row against sample_data/apaar_registry.json.
The default (off) keeps the format-only check.
"""
import json
import os
from datetime import date
from pathlib import Path

DEFAULT_FILE = Path(__file__).parent / "sample_data" / "apaar_registry.json"


class MockRegistry:
    def __init__(self, path=None):
        path = Path(path or os.getenv("APAAR_REGISTRY_FILE") or DEFAULT_FILE)
        with open(path, encoding="utf-8") as f:
            self._records = json.load(f)

    def lookup(self, apaar_id):
        """Returns {"name": str, "dob": date} for a registered ID, or None."""
        rec = self._records.get(apaar_id)
        if not rec:
            return None
        return {"name": rec["name"], "dob": date.fromisoformat(rec["dob"])}


def get_registry():
    """Returns the configured registry, or None when registry checks are off."""
    mode = os.getenv("APAAR_REGISTRY", "off").lower()
    if mode == "mock":
        return MockRegistry()
    return None


def registry_errors(registry, row):
    """Error messages for one validated CSV row (empty list = matches the registry)."""
    record = registry.lookup(row["apaar_id"])
    if record is None:
        return ["APAAR ID not found in the national registry"]
    errs = []
    if record["name"].strip().lower() != row["name"].strip().lower():
        errs.append("Name does not match the APAAR registry")
    if record["dob"] != row["dob"]:
        errs.append("Date of birth does not match the APAAR registry")
    return errs
