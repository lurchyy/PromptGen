from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from db1 import get_db
from models.sector import Sector
from models.usecase import UseCase

router = APIRouter(
    prefix="/api",
    tags=["Metadata"]
)

@router.get("/sectors", response_model=list[str])
def get_sectors(db: Session = Depends(get_db)):
    """
    Retrieves a list of all available sector names.
    """
    sectors = db.query(Sector.name).all()
    return [sector[0] for sector in sectors]

@router.get("/use_cases/{sector_name}", response_model=list[str])
def get_use_cases(sector_name: str, db: Session = Depends(get_db)):
    """
    Retrieves a list of use cases for a given sector name.
    Returns a 404 error if the sector is not found.
    """
    sector = db.query(Sector).filter(Sector.name == sector_name).first()
    if not sector:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Sector '{sector_name}' not found."
        )
    use_cases = db.query(UseCase.name).filter(UseCase.sector_id == sector.id).all()
    return [use_case[0] for use_case in use_cases]