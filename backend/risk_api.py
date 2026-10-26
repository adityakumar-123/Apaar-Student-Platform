from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from anomaly import analyse
from auth import require_roles
from database import get_db

router = APIRouter()


@router.get("/compliance/risk", dependencies=[Depends(require_roles("aicte"))])
def institution_risk(db: Session = Depends(get_db)):
    return analyse(db)