import json
from sqlalchemy.orm import Session
from db1 import SessionLocal
from models.sector import Sector
from models.usecase import UseCase
from models.prompt import Prompt
from dotenv import load_dotenv
from groq import Groq
import os

load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

system_prompt = """
You are an expert Prompt Engineer helping to design detailed, one-shot prompts that allow users to execute end-to-end AI workflows in finance.
Given a use case with it's description in the financial sector, write a complete prompt that helps an LLM like GPT or Claude execute the task entirely in one go.
The prompt must be:
- Clear and detailed
- Actionable and logically structured
- Structured with sections (e.g. Input, Output Format, Task Instructions)
- Usable by investors, analysts, or finance professionals
Avoid vague instructions. Be as concrete and specific as possible.
"""

def generate_prompt_for_use_case(sector: str, use_case_name: str, use_case_description: str) -> str:
    try:
        client = Groq(api_key=GROQ_API_KEY)
        chat_completion = client.chat.completions.create(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Sector: {sector}\nUse Case: {use_case_name}\nDescription: {use_case_description}"}
            ],
            model="llama-3.3-70b-versatile",
            temperature=0.4
        )
        return chat_completion.choices[0].message.content
    except Exception as e:
        print(f"❌ Error generating prompt for {use_case_name}: {e}")
        return None

def seed():
    db: Session = SessionLocal()

    with open("updatedseeddata.json", "r", encoding="utf-8") as f:
        data = json.load(f)

    for sector_data in data["sectors"]:
        sector_obj = Sector(name=sector_data["sector"])
        db.add(sector_obj)
        db.flush()  # Get sector_obj.id

        for use_case_data in sector_data["use_cases"]:
            use_case_name = use_case_data["use_case"]
            use_case_description = use_case_data["description"]
            use_case_obj = UseCase(
                name=use_case_name,
                # description=use_case_description,  # Uncomment if UseCase has a description field
                sector_id=sector_obj.id
            )
            db.add(use_case_obj)
            db.flush()  # Get use_case_obj.id

            prompt_text = generate_prompt_for_use_case(sector_data["sector"], use_case_name, use_case_description)
            if prompt_text:
                prompt_obj = Prompt(use_case_id=use_case_obj.id, content=prompt_text)
                db.add(prompt_obj)
                print(f"✅ Prompt generated and saved for: {use_case_name}")
            else:
                print(f"⚠️ Skipped prompt for: {use_case_name}")

    db.commit()
    db.close()

if __name__ == "__main__":
    seed()
