from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship
from db.base_class import Base

class UseCase(Base):
    __tablename__ = "use_cases"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    description = Column(String)

    sector_id = Column(Integer, ForeignKey("sectors.id"), nullable=False)
    sector = relationship("Sector", backref="use_cases")

    # One-to-one relationship with prompt
    prompt = relationship("Prompt", back_populates="use_case", uselist=False)
