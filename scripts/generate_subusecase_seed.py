import re
import os
from collections import defaultdict
from sqlalchemy.orm import Session
import sys

sys.path.append("..")
from db1 import SessionLocal
from models.sector import Sector
from models.subusecase import SubUseCase
from dotenv import load_dotenv
from groq import Groq

load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# --- System prompt for the LLM ---
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

# --- Load sub-use cases from markdown file ---
def load_sub_use_cases_from_md(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    subcases = defaultdict(list)
    current = None
    for line in content.splitlines():
        match = re.match(r"## \*\*(.+?)\*\*", line)
        if match:
            current = match.group(1).strip()
        elif "|" in line and "Sub-Use Case" not in line and current:
            parts = [part.strip() for part in line.strip().split("|") if part.strip()]
            if len(parts) >= 2 and parts[1].lower().startswith("yes"):
                subcases[current].append(parts[0])
    return dict(subcases)

# --- Prompt generation using Groq LLM ---
def generate_prompt_for_subusecase(subusecase_name: str) -> str:
    try:
        client = Groq(api_key=GROQ_API_KEY)
        chat_completion = client.chat.completions.create(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Use Case: {subusecase_name}"}
            ],
            model="llama3-70b-8192",
            temperature=0.4
        )
        return chat_completion.choices[0].message.content
    except Exception as e:
        print(f"❌ Error generating prompt for {subusecase_name}: {e}")
        return None

# --- Optional cleanup of LLM-generated prompt ---
def clean_generated_prompt(prompt: str) -> str:
    prompt = re.sub(r"^\s*here is the improved prompt\s*\n", "", prompt, flags=re.IGNORECASE)
    prompt = re.sub(r"(?s)\*\*Example Input:\*\*.*?```.*?```\s*", "", prompt)
    prompt = re.sub(r"(?s)\*\*Example Output:\*\*.*?```.*?```\s*", "", prompt)
    return prompt.strip()

# --- Main execution ---
def main():
    markdown_file = "VC_Sub_Use_Case_Taxonomy.docx.md"
    VC_SUB_USE_CASES = load_sub_use_cases_from_md(markdown_file)

    db: Session = SessionLocal()
    sector_name = "Venture Capital (VC)"
    sector = db.query(Sector).filter(Sector.name == sector_name).first()
    if not sector:
        print(f"❌ Sector not found: {sector_name}")
        return

    for use_case, subusecases in VC_SUB_USE_CASES.items():
        for subusecase in subusecases:
            exists = db.query(SubUseCase).filter(
                SubUseCase.sector_id == sector.id,
                SubUseCase.use_case == use_case,
                SubUseCase.sub_use_case == subusecase
            ).first()
            if exists:
                print(f"✅ Sub-use case already exists: {use_case} -> {subusecase}")
                continue
            print(f"⚙️ Generating prompt for: {use_case} -> {subusecase}")
            prompt_text = generate_prompt_for_subusecase(subusecase)
            if prompt_text:
                cleaned_prompt = clean_generated_prompt(prompt_text)
                sub = SubUseCase(
                    sector_id=sector.id,
                    use_case=use_case,
                    sub_use_case=subusecase,
                    prompt=cleaned_prompt
                )
                db.add(sub)
                db.commit()
                print(f"✅ Prompt saved for: {use_case} -> {subusecase}")
            else:
                print(f"⚠️ Skipped: {use_case} -> {subusecase} (no prompt generated)")

if __name__ == "__main__":
    main()
