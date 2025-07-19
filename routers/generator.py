import os
import re
import groq
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from db1 import get_db
from models.sector import Sector
from models.usecase import UseCase
from models.prompt import Prompt
from models.subusecase import SubUseCase
def llm_subusecase_match(user_input, subusecase_list):
    """LLM fuzzy match user input to a sub-use case string from the list. Returns the best match or None."""
    if not subusecase_list:
        return None
    groq_client = groq.Groq(api_key=GROQ_API_KEY)
    system_prompt = (
        f"You are a financial sub-use case matcher. Here is the list of sub-use cases:\n"
        f"{subusecase_list}\n"
        "Given the user input, determine if it matches (by intent or phrasing) one of these sub-use cases. "
        "If yes, reply ONLY with the matching sub-use case string (no extra words). "
        "If not, reply ONLY with: NO_MATCH."
    )
    user_prompt = f"User Input: {user_input}"
    response = groq_client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        temperature=0.1,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
    )
    result = response.choices[0].message.content.strip()
    return result if result != "NO_MATCH" else None

router = APIRouter()
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

class PromptRequest(BaseModel):
    sector: str
    use_case: str
    user_input: str = ""  

class VariableFillRequest(BaseModel):
    prompt_template: str
    variables: dict  # {"Variable Name": "Value"}

import re
def deduplicate(variables):
    seen = set()
    deduped = []
    for v in variables:
        v = v.strip()
        if v not in seen:
            deduped.append(v)
            seen.add(v)
    return deduped

def extract_variables_from_prompt(prompt: str):
    # Find the section that contains the word 'input' in its heading (case-insensitive)
    input_section = None
    # Try to find a markdown heading (e.g., **Input:**, ## Input, # Input, or Input: on its own line)
    input_section_match = re.search(r"(^|\n)[#\*\s]*input[\s\-:]*\n(.*?)(\n[#\*\s]*[A-Z][^\n]*:|\n[#\*\s]*[A-Z][^\n]*|\n\*\*Output|\n##|\n#|\Z)", prompt, re.IGNORECASE | re.DOTALL)
    if input_section_match:
        # Group 2 is the content under the input section
        input_section = input_section_match.group(2)
    else:
        # Fallback: search for the first block that contains 'input' in the heading
        input_section = prompt

    raw_vars = re.findall(r"\[\[([^\]]+)\]\]", input_section)
    variables = deduplicate(raw_vars)
    return list(variables)


def clean_generated_prompt(prompt: str) -> str:
    prompt = re.sub(r"^\s*here is the improved prompt\s*\n", "", prompt, flags=re.IGNORECASE)
    prompt = re.sub(r"(?s)\*\*Example Input:\*\*.*?```.*?```\s*", "", prompt)
    prompt = re.sub(r"(?s)\*\*Example Output:\*\*.*?```.*?```\s*", "", prompt)
    return prompt.strip()

def llm_match_decision(sector, user_use_case, text_input, use_case_list):
    groq_client = groq.Groq(api_key=GROQ_API_KEY)  # Do not pass 'proxies' or other unsupported kwargs
    system_prompt = (
        f"You are a financial use case matcher. Here is the list of use cases for the {sector} sector:\n"
        f"{use_case_list}\n"
        "Given the user input and sector, determine if it matches (by intent or phrasing) one of these use cases. "
        "If yes, reply ONLY with the matching use case string (no extra words). "
        "If not, reply ONLY with: NEW_USE_CASE."
    )
    user_prompt = (
        f"Sector: {sector}\n"
        f"User Use Case: {user_use_case}\n"
        f"User Input: {text_input}"
    )
    response = groq_client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        temperature=0.1,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
    )
    return response.choices[0].message.content.strip()

def generate_structured_prompt(sector, use_case, user_input):
    groq_client = groq.Groq(api_key=GROQ_API_KEY)
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

Instruct the LLM to flag and report any unavailable or missing data that cannot be found from public sources or uploads."""
    user_prompt = f"""
Sector: {sector}
Use Case: {use_case}
User Goal: {user_input}

Write a complete one-shot prompt that enables an LLM to execute the task in the context above.
"""
    response = groq_client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        temperature=0.4,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
    )
    return response.choices[0].message.content.strip()

def review_and_edit_prompt(prompt, sector, use_case, user_input):
    groq_client = groq.Groq(api_key=GROQ_API_KEY)
    system_prompt = """
You are an expert prompt editor. Given a draft prompt, the financial sector, the use case, and the user’s specific task description:
- If the prompt already precisely and fully matches the user's actual request, return it unchanged.
- If not, edit or reframe the prompt so it is a perfect fit for the actual user need. 
- Ensure the prompt is clear, actionable, and directly addresses the user's described task, using any specific language from the user input as needed.
- If the sector or use is "Something else", exclude the sector/use case from the prompt and focus on the user input.
- Prompt to start with a clear role description. 
- Do not edit the input fields or output structure
Do not include any additional explanations or comments or introduction(like Here is the improved prompt: )
"""
    user_prompt = f"""
# Sector: {sector}
# Use Case: {use_case}
User Input: {user_input}

Draft Prompt to Review:
\"\"\"{prompt}\"\"\"

Edit the above draft so it exactly matches the user query, if necessary.
"""
    response = groq_client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        temperature=0.1,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
    )
    return response.choices[0].message.content.strip()

@router.post("/prompt-universal")
def universal_prompt_handler(
    req: PromptRequest,
    db: Session = Depends(get_db),
):
    # If either sector or use_case is 'Something else', treat as custom prompt
    if req.sector == 'Something else' or req.use_case == 'Something else':
        if not req.user_input.strip():
            raise HTTPException(status_code=400, detail="Please provide a description in the input box for custom prompt generation.")
        # Always generate a new prompt for custom
        new_prompt = generate_structured_prompt(
            req.sector, req.use_case, req.user_input
        )
        
        final_prompt = review_and_edit_prompt(
            new_prompt, req.sector, req.use_case, req.user_input
        )
        final_prompt = clean_generated_prompt(final_prompt)
        variables = extract_variables_from_prompt(final_prompt)
        return {
            "source": "custom",
            "sector": req.sector,
            "use_case": req.use_case,
            "user_input": req.user_input,
            "prompt_template": final_prompt,
            "variables": variables
        }

    # Normal flow for known sectors/use cases
    sector_obj = db.query(Sector).filter(Sector.name == req.sector).first()
    if not sector_obj:
        raise HTTPException(status_code=404, detail="Sector not found.")
    use_cases = db.query(UseCase).filter(UseCase.sector_id == sector_obj.id).all()
    use_case_names = [uc.name for uc in use_cases]

    # If NO user_input, just fetch by exact use_case match (fast path)
    if not req.user_input.strip():
        match_uc = db.query(UseCase).filter(
            UseCase.sector_id == sector_obj.id,
            UseCase.name.ilike(req.use_case.strip())
        ).first()
        if match_uc:
            prompt_obj = db.query(Prompt).filter(Prompt.use_case_id == match_uc.id).first()
            if prompt_obj:
                # Only clean the prompt, do not run review_and_edit_prompt
                final_prompt = clean_generated_prompt(prompt_obj.content)
                variables = extract_variables_from_prompt(final_prompt)
                return {
                    "source": "datalake",
                    "sector": req.sector,
                    "use_case": match_uc.name,
                    "user_input": "",
                    "prompt_template": final_prompt,
                    "variables": variables
                }
            else:
                raise HTTPException(status_code=404, detail="Prompt not found for this use case.")
        else:
            raise HTTPException(status_code=404, detail="Use case not found in sector.")

    # If user_input exists: run LLM matching logic

    match_result = llm_match_decision(
        req.sector, req.use_case, req.user_input, use_case_names
    )
    if match_result in use_case_names:
        # Matched a use case, fetch prompt from DB
        match_uc = db.query(UseCase).filter(
            UseCase.sector_id == sector_obj.id,
            UseCase.name == match_result
        ).first()
        # --- SUB-USE CASE MATCHING ---
        subusecase_qs = db.query(SubUseCase).filter(
            SubUseCase.sector_id == sector_obj.id,
            SubUseCase.use_case == match_result
        ).all()
        subusecase_names = [suc.sub_use_case for suc in subusecase_qs]
        sub_match = None
        if req.user_input.strip() and subusecase_names:
            sub_match = llm_subusecase_match(req.user_input, subusecase_names)
        if sub_match:
            subusecase_obj = next((suc for suc in subusecase_qs if suc.sub_use_case == sub_match), None)
            if subusecase_obj:
                final_prompt = clean_generated_prompt(subusecase_obj.prompt)
                variables = extract_variables_from_prompt(final_prompt)
                return {
                    "source": "sub_use_case",
                    "sector": req.sector,
                    "use_case": match_result,
                    "sub_use_case": sub_match,
                    "user_input": req.user_input,
                    "prompt_template": final_prompt,
                    "variables": variables
                }
        # --- END SUB-USE CASE MATCHING ---
        prompt_obj = db.query(Prompt).filter(Prompt.use_case_id == match_uc.id).first()
        if prompt_obj:
            final_prompt = review_and_edit_prompt(
                prompt_obj.content, req.sector, match_result, req.user_input
            )
            final_prompt = clean_generated_prompt(final_prompt)
            variables = extract_variables_from_prompt(final_prompt)
            return {
                "source": "datalake_llm_match",
                "sector": req.sector,
                "use_case": match_result,
                "user_input": req.user_input,
                "prompt_template": final_prompt,
                "variables": variables
            }
        else:
            raise HTTPException(status_code=404, detail="Prompt not found for LLM-matched use case.")
    else:
        # Not in datalake: dynamically generate a prompt
        new_prompt = generate_structured_prompt(
            req.sector, req.use_case, req.user_input
        )
        final_prompt = review_and_edit_prompt(
            new_prompt, req.sector, req.use_case, req.user_input
        )
        final_prompt = clean_generated_prompt(final_prompt)
        variables = extract_variables_from_prompt(final_prompt)
        return {
            "source": "dynamic",
            "sector": req.sector,
            "use_case": req.use_case,
            "user_input": req.user_input,
            "prompt_template": final_prompt,
            "variables": variables
        }

from fastapi import HTTPException

@router.post("/prompt-fill-variables")
def fill_prompt_variables(payload: VariableFillRequest):
    # 🛑 BLOCK if variables are empty or all values are blank/empty
    if (
        not payload.variables or
        all(not (v and str(v).strip()) for v in payload.variables.values())
    ):
        raise HTTPException(
            status_code=400,
            detail="All required user input fields must be filled before generating the prompt."
        )

    filled_prompt = payload.prompt_template
    # For each variable, replace lines like '* [[Variable]]' with '* Variable: Value', else fallback to just replacing [[Variable]]
    for var, value in payload.variables.items():
        # Replace bullet lines with label
        bullet_pattern = rf"(^[ \t]*[\*\-][ \t]*)\[\[{re.escape(var)}\]\][ \t]*$"
        filled_prompt = re.sub(bullet_pattern, rf"\1{var}: {value}", filled_prompt, flags=re.IGNORECASE | re.MULTILINE)
        # Fallback: replace any remaining [[Variable]]
        pattern = rf"\[\[{re.escape(var)}\]\]"
        filled_prompt = re.sub(pattern, value, filled_prompt, flags=re.IGNORECASE)

    # Ensure the returned prompt is always a string
    if not isinstance(filled_prompt, str):
        try:
            filled_prompt = str(filled_prompt)
        except Exception:
            filled_prompt = "[ERROR: Prompt could not be converted to string]"

    return {"final_prompt": filled_prompt}
