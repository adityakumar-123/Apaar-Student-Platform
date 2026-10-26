from database import SessionLocal
from models import User
from auth import hash_password

DEMO_USERS = [
    ("aicte_admin", "Aicte@123", "aicte", None),
    ("inst001_operator", "Inst001@123", "institution", "INST001"),
    ("inst002_operator", "Inst002@123", "institution", "INST002"),
    ("employer_demo", "Verify@123", "verifier", None),
]

db = SessionLocal()
for username, password, role, inst in DEMO_USERS:
    if db.query(User).filter_by(username=username).first():
        print("exists:", username)
        continue
    db.add(User(username=username, password_hash=hash_password(password), role=role, institution_code=inst))
    print("created:", username, "/", role)
db.commit()
db.close()
