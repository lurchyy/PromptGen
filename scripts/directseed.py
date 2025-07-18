import json
import os
from sqlalchemy.orm import Session
import sys
sys.path.append("..")
from db1 import SessionLocal
from models.usecase import UseCase
from models.prompt import Prompt
from dotenv import load_dotenv

load_dotenv()

def main():
    db: Session = SessionLocal()

    with open("detailed_prompt_library.json", "r", encoding="utf-8") as f:
        data = json.load(f)

    for sector in data["sectors"]:
        for uc in sector["use_cases"]:
            use_case_name = uc["use_case"]
            prompt_text = uc["prompt"]

            # Fetch UseCase by name
            use_case = db.query(UseCase).filter_by(name=use_case_name).first()
            if not use_case:
                print(f"⚠️ Skipping prompt for missing UseCase: {use_case_name}")
                continue

            # Upsert Prompt
            existing_prompt = db.query(Prompt).filter_by(use_case_id=use_case.id).first()
            if existing_prompt:
                existing_prompt.content = prompt_text
                db.commit()
                print(f"🔁 Updated prompt for: {use_case_name}")
            else:
                new_prompt = Prompt(use_case_id=use_case.id, content=prompt_text)
                db.add(new_prompt)
                db.commit()
                print(f"➕ Inserted new prompt for: {use_case_name}")

if __name__ == "__main__":
    main()
