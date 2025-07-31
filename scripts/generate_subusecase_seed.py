import json

import os
from sqlalchemy.orm import Session
from dotenv import load_dotenv
import re
import sys

try:
    import google.generativeai as genai
except ImportError:
    print("google-generativeai not found. Please install with: pip install google-generativeai")
    raise

sys.path.append("..")
from db1 import SessionLocal
from models.sector import Sector
from models.subusecase import SubUseCase


load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

system_prompt = """
You are an expert Prompt Engineer.

For any given user workflow request, generate a comprehensive, actionable, and structured one-shot prompt that instructs an LLM to solve the task in a single response. 

Prompt should ALWAYS start with a clear role description according to the sector and use case, e.g.:
"You are a financial analyst tasked with analyzing market trends and providing insights based on the provided data."
"You are a market researcher who needs to evaluate customer preferences and generate a report based on the findings."
"You are a business strategist who must develop a growth plan based on the provided information."

In the "Input" section, include ONLY the absolute minimum user inputs required to perform the task.

If information can be obtained from public sources, via web search, or inferred from context, do not request it as a user input.

Do not create placeholders for generic sections or standard frameworks (e.g., "Market Analysis", "Team", "Financials") unless the user must upload or explicitly provide them.

Only require user fill-ins for facts that cannot be reliably sourced or inferred (e.g., company name, specific goal, document uploads, or unique confidential data).

Use double square brackets for required user input fields (e.g., [[Company Name]], [[Goal]]).

All other analysis and context should be handled by the LLM, not the user.

The prompt should include clear, minimal input instructions, detailed output structure, and stepwise analysis or workflow guidance.

If the task requires a document or data upload, create a placeholder for it. Otherwise, instruct the LLM to attempt research or acknowledge missing data.

Instruct the LLM to flag and report any unavailable or missing data that cannot be found from public sources or uploads.
"""

def clean_generated_prompt(prompt: str) -> str:
    prompt = re.sub(r"^\s*here is the improved prompt\s*\n", "", prompt, flags=re.IGNORECASE)
    prompt = re.sub(r"(?s)\*\*Example Input:\*\*.*?```.*?```\s*", "", prompt)
    prompt = re.sub(r"(?s)\*\*Example Output:\*\*.*?```.*?```\s*", "", prompt)
    return prompt.strip()


def generate_prompt(sub_use_case: str) -> str:
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel('gemini-2.5-pro')
        prompt = f"{system_prompt}\nUse Case: {sub_use_case}"
        response = model.generate_content(prompt)
        # Gemini's response is in response.text
        return response.text
    except Exception as e:
        print(f"❌ Error generating prompt for {sub_use_case}: {e}")
        return None

def main():
    db: Session = SessionLocal()

    # Load flat JSON list
    with open("subusecases.json", encoding="utf-8") as f:
        subusecases = json.load(f)

    for item in subusecases:


        sector_name = item["Sector"].strip()
        use_case = item["Use Case"].strip()
        sub_use_case = item["Sub-Use Case"].strip()

        # Look up the sector
        sector = db.query(Sector).filter(Sector.name == sector_name).first()
        if not sector:
            print(f"❌ Sector not found in DB: {sector_name} -- skipping")
            continue

        # Look up SubUseCase
        exists = db.query(SubUseCase).filter(
            SubUseCase.sector_id == sector.id,
            SubUseCase.use_case == use_case,
            SubUseCase.sub_use_case == sub_use_case
        ).first()

        if exists and exists.prompt:
            print(f"✅ Already has prompt: {sector_name} | {use_case} | {sub_use_case}")
            continue

        print(f"⚡ Generating prompt for: {sector_name} | {use_case} | {sub_use_case}")
        prompt_text = generate_prompt(sub_use_case)
        if prompt_text:
            cleaned_prompt = clean_generated_prompt(prompt_text)
            if exists:
                exists.prompt = cleaned_prompt
                db.commit()
                print(f"🔄 Updated prompt: {sector_name} | {use_case} | {sub_use_case}")
            else:
                new_subuse = SubUseCase(
                    sector_id=sector.id,
                    use_case=use_case,
                    sub_use_case=sub_use_case,
                    prompt=cleaned_prompt
                )
                db.add(new_subuse)
                db.commit()
                print(f"➕ Inserted new prompt: {sector_name} | {use_case} | {sub_use_case}")
        else:
            print(f"❌ Failed to generate prompt for: {sector_name} | {use_case} | {sub_use_case}")

if __name__ == "__main__":
    main()
