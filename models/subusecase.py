from sqlalchemy import Column, Integer, String, Text, ForeignKey
from sqlalchemy.orm import relationship
from db.base_class import Base

class SubUseCase(Base):
    __tablename__ = "sub_use_cases"

    id = Column(Integer, primary_key=True, index=True)
    sector_id = Column(Integer, ForeignKey("sectors.id"), nullable=False)
    use_case = Column(String, nullable=False)
    sub_use_case = Column(String, nullable=False)
    prompt = Column(Text, nullable=False)

    sector = relationship("Sector")
