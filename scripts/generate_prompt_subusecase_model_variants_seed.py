import re
import os
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

# --- Define your sub-use cases here ---
VC_SUB_USE_CASES = {
    "Competitive analysis": [
        "Compare to top 3 competitors",
        "Extract market share from sources",
        "Build positioning matrix",
        "Identify substitutes"
    ],
    "Deal flow screening": [
        "Extract key points from pitch deck",
        "Identify red flags",
        "Score against investment thesis",
        "Auto-tag by stage/sector"
    ],
    # ...add all other use cases and sub-use cases here...
}

MODEL_VARIANTS = {
    "gpt": "Write this for GPT-style LLMs. Use clear, direct instructions.",
    "claude": "Format this for Claude 3 — use bullet points and concise language.",
    "gemini": "Keep it structured and stepwise for Gemini 1.5 Pro. Emphasize numbered steps."
}

BASE_SYSTEM_PROMPT = """
You are an expert Prompt Engineer.\n\nFor any given user workflow request, generate a comprehensive, actionable, and structured one-shot prompt that instructs an LLM to solve the task in a single response.\n\nPrompt should ALWAYS start with a clear role description according to the sector and use case.\n\nIn the \"Input\" section, include ONLY the absolute minimum user inputs required to perform the task.\n\nIf information can be obtained from public sources, via web search, or inferred from context, do not request it as a user input.\n\nDo not create placeholders for generic sections or standard frameworks unless the user must upload or explicitly provide them.\n\nOnly require user fill-ins for facts that cannot be reliably sourced or inferred.\n\nUse double square brackets for required user input fields (e.g., [[Company Name]], [[Goal]]).\n\nAll other analysis and context should be handled by the LLM, not the user.\n\nThe prompt should include clear, minimal input instructions, detailed output structure, and stepwise analysis or workflow guidance.\n\nIf the task requires a document or data upload, create a placeholder for it. Otherwise, instruct the LLM to attempt research or acknowledge missing data.\n\nInstruct the LLM to flag and report any unavailable or missing data that cannot be found from public sources or uploads.\n"""

def generate_prompt_for_subusecase(subusecase_name: str, model: str) -> str:
    system_prompt = BASE_SYSTEM_PROMPT + "\n" + MODEL_VARIANTS[model]
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
        print(f"❌ Error generating prompt for {subusecase_name} ({model}): {e}")
        return None

def clean_generated_prompt(prompt: str) -> str:
    prompt = re.sub(r"^\s*here is the improved prompt\s*\n", "", prompt, flags=re.IGNORECASE)
    prompt = re.sub(r"(?s)\*\*Example Input:\*\*.*?```.*?```\s*", "", prompt)
    prompt = re.sub(r"(?s)\*\*Example Output:\*\*.*?```.*?```\s*", "", prompt)
    return prompt.strip()

def main():
    db: Session = SessionLocal()
    sector_name = "VC"
    sector = db.query(Sector).filter(Sector.name == sector_name).first()
    if not sector:
        print(f"❌ Sector not found: {sector_name}")
        return

    for use_case, subusecases in VC_SUB_USE_CASES.items():
        for subusecase in subusecases:
            for model in MODEL_VARIANTS.keys():
                exists = db.query(SubUseCase).filter(
                    SubUseCase.sector_id == sector.id,
                    SubUseCase.use_case == use_case,
                    SubUseCase.sub_use_case == subusecase,
                    SubUseCase.model == model
                ).first()
                if exists:
                    print(f"✅ Sub-use case already exists: {use_case} -> {subusecase} [{model}]")
                    continue
                print(f"⚙️ Generating prompt for: {use_case} -> {subusecase} [{model}]")
                prompt_text = generate_prompt_for_subusecase(subusecase, model)
                if prompt_text:
                    cleaned_prompt = clean_generated_prompt(prompt_text)
                    sub = SubUseCase(
                        sector_id=sector.id,
                        use_case=use_case,
                        sub_use_case=subusecase,
                        prompt=cleaned_prompt,
                        model=model
                    )
                    db.add(sub)
                    db.commit()
                    print(f"✅ Prompt saved for: {use_case} -> {subusecase} [{model}]")
                else:
                    print(f"⚠️ Skipped: {use_case} -> {subusecase} [{model}] (no prompt generated)")

if __name__ == "__main__":
    main()
