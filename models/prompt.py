from sqlalchemy import Column, Integer, Text, ForeignKey, String
from sqlalchemy.orm import relationship
from db.base_class import Base

class Prompt(Base):
    __tablename__ = "prompts"

    id = Column(Integer, primary_key=True, index=True)
    use_case_id = Column(Integer, ForeignKey("use_cases.id"), nullable=False)
    content = Column(Text, nullable=False)
    model = Column(String, nullable=False, default="gpt")

    # One-to-one relationship with UseCase
    use_case = relationship("UseCase", back_populates="prompt", uselist=False)
