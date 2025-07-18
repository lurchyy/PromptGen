from sqlalchemy import create_engine
import os
from dotenv import load_dotenv

load_dotenv()
engine = create_engine(os.getenv("DATABASE_URL"))
conn = engine.connect()
print("Connected!")  # If no error, you're good
