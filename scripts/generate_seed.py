import re
import os
from sqlalchemy.orm import Session
import sys
sys.path.append("..")
from db1 import SessionLocal
from models.usecase import UseCase
from models.prompt import Prompt
from dotenv import load_dotenv
from groq import Groq

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# ---------- Prompt Templates ----------
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


def generate_prompt_for_use_case(use_case_name: str) -> str:

    """Send the use case to Groq and return the generated prompt using the Groq SDK."""
    try:
        client = Groq(api_key=GROQ_API_KEY)
        chat_completion = client.chat.completions.create(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Use Case: {use_case_name}"}
            ],
            model="llama3-70b-8192",
            temperature=0.4
        )
        return chat_completion.choices[0].message.content
    except Exception as e:
        print(f"❌ Error generating prompt for {use_case_name}: {e}")
        return None
    
def clean_generated_prompt(prompt: str) -> str:
    prompt = re.sub(r"^\s*here is the improved prompt\s*\n", "", prompt, flags=re.IGNORECASE)
    prompt = re.sub(r"(?s)\*\*Example Input:\*\*.*?```.*?```\s*", "", prompt)
    prompt = re.sub(r"(?s)\*\*Example Output:\*\*.*?```.*?```\s*", "", prompt)
    return prompt.strip()

def main():
    db: Session = SessionLocal()
    use_cases = db.query(UseCase).all()

    for use_case in use_cases:
        if db.query(Prompt).filter(Prompt.use_case_id == use_case.id).first():
            print(f"✅ Prompt already exists for: {use_case.name}")
            continue

        print(f"⚙️ Generating prompt for: {use_case.name}")
        prompt_text = generate_prompt_for_use_case(use_case.name)

        if prompt_text:
            cleaned_prompt = clean_generated_prompt(prompt_text)
            prompt = Prompt(use_case_id=use_case.id, content=cleaned_prompt)
            db.add(prompt)
            db.commit()
            print(f"✅ Prompt saved for: {use_case.name}")
        else:
            print(f"⚠️ Skipped: {use_case.name} (no prompt generated)")

if __name__ == "__main__":
    main()
