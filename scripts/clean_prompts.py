import re
import sys
import os
from sqlalchemy.orm import Session
from dotenv import load_dotenv

# Add parent directory to Python path to import db1 and models
script_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(script_dir)
sys.path.insert(0, parent_dir)

from db1 import SessionLocal
from models.subusecase import SubUseCase

load_dotenv()

def clean_prompt(prompt: str) -> str:
    prompt_strip = prompt.lstrip()
    # If prompt starts with 'here' (case-insensitive)
    if prompt_strip.lower().startswith("here"):
        # Remove everything up to and including the first '*'
        star_idx = prompt_strip.find('*')
        if star_idx != -1:
            return prompt_strip[star_idx:]
        else:
            return prompt_strip  # No '*', leave as is
    # If first word is 'You' or '*', do nothing
    first_word = prompt_strip.split(None, 1)[0] if prompt_strip else ''
    if first_word == 'You' or first_word == '*':
        return prompt_strip
    return prompt_strip  # Default: leave as is

def main():
    db: Session = SessionLocal()
    updated = 0
    total = 0
    for sub in db.query(SubUseCase).all():
        total += 1
        orig = sub.prompt
        cleaned = clean_prompt(orig)
        if cleaned != orig:
            print(f"[UPDATED] id={sub.id} | Old: {repr(orig[:60])}... | New: {repr(cleaned[:60])}...")
            sub.prompt = cleaned
            updated += 1
    if updated:
        db.commit()
    print(f"Checked {total} prompts. Updated {updated} prompts.")

if __name__ == "__main__":
    main()
