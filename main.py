import models  # Ensure all models are registered with SQLAlchemy
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from db1 import get_db, SessionLocal
from models.sector import Sector
from models.usecase import UseCase

from routers import generator

app = FastAPI(
    title="Prompt Generator API",
    version="0.1.0"
)

# Optional CORS if you're using a frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include your routes
app.include_router(generator.router, prefix="/api")

@app.get("/api/sectors")
def get_sectors(db: SessionLocal = Depends(get_db)):
    sectors = db.query(Sector.name).all()
    return [sector[0] for sector in sectors]

@app.get("/api/use_cases/{sector_name}")
def get_use_cases(sector_name: str, db: SessionLocal = Depends(get_db)):
    sector = db.query(Sector).filter(Sector.name == sector_name).first()
    if not sector:
        return []
    use_cases = db.query(UseCase.name).filter(UseCase.sector_id == sector.id).all()
    return [use_case[0] for use_case in use_cases]

