def extract_filled_variables(user_input, variables):
    """
    Given a user input string and a list of variable names, attempt to extract values for each variable.
    Returns a dict: {variable: value or ''}
    This is a simple implementation: it checks if the variable name (case-insensitive) appears in the user input,
    and if so, returns the user input as the value; otherwise, returns ''.
    You can improve this logic to parse structured input if needed.
    """
    result = {}
    user_input_lower = user_input.lower() if user_input else ''
    for var in variables:
        # If variable name appears in user input, assign user input as value (simple heuristic)
        if var.lower() in user_input_lower and user_input.strip():
            result[var] = user_input.strip()
        else:
            result[var] = ''
    return result
import os
import re
import groq
from fastapi import APIRouter, Depends, HTTPException
from fastapi import Query
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
    model: str = "gpt"  # e.g. 'gpt', 'claude', 'gemini'

class VariableFillRequest(BaseModel):
    prompt_template: str
    variables: dict  # {"Variable Name": "Value"}

import re
def deduplicate(variables):
    seen = set()
    deduped = []
    for v in variables:
        v = v.strip()
        if v and v not in seen:
            deduped.append(v)
            seen.add(v)
    return deduped


def extract_input_section(prompt):
    """
    Return ONLY the actual 'Input' section (as text) from the full prompt.
    """
    # More flexible pattern to match various input section formats
    patterns = [
        r"###\s*\*\*Input Data\*\*\s*\n(.*?)(?=\n###|\n##|\n\*\*\*|\Z)",
        r"##\s*Input Data\s*\n(.*?)(?=\n###|\n##|\n\*\*\*|\Z)",
        r"\*\*Input Data\*\*\s*\n(.*?)(?=\n###|\n##|\n\*\*\*|\Z)",
        r"Input Data:?\s*\n(.*?)(?=\n###|\n##|\n\*\*\*|\Z)"
    ]
    
    for pattern in patterns:
        m = re.search(pattern, prompt, re.IGNORECASE | re.DOTALL)
        if m:
            return m.group(1).strip()
    
    return ""

def extract_input_headings(prompt):
    """
    Returns all bolded/bulleted field labels (the headings) in the Input section.
    """
    input_section = extract_input_section(prompt)
    if not input_section:
        return []
    
    headings = []
    for line in input_section.splitlines():
        line = line.strip()
        if not line:
            continue
            
        # Pattern for: *   **Portfolio Holdings:** [[...]]
        # Also handles: **Portfolio Holdings:** [[...]]
        patterns = [
            r"^\*\s*\*\*([^*\(\[\:]+?)(?:\s*\(Optional\))?\s*:\*\*\s*\[\[",
            r"^\*\*([^*\(\[\:]+?)(?:\s*\(Optional\))?\s*:\*\*\s*\[\[",
            r"^[\*\-\s\d\.]*\*\*([^*\(\[\:]+?)(?:\s*\(Optional\))?\s*:\*\*\s*\[\["
        ]
        
        for pattern in patterns:
            m = re.match(pattern, line)
            if m:
                heading = m.group(1).strip()
                if heading and heading not in headings:
                    headings.append(heading)
                break
    
    return headings

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
        variables = extract_input_headings(final_prompt)
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
            prompt_obj = db.query(Prompt).filter(
                Prompt.use_case_id == match_uc.id,
                Prompt.model == getattr(req, 'model', 'gpt')
            ).first()
            if prompt_obj:
                # Only clean the prompt, do not run review_and_edit_prompt
                final_prompt = clean_generated_prompt(prompt_obj.content)
                variables = extract_input_headings(final_prompt)
                # Stage 1: Return prompt template and required variables
                return {
                    "stage": 1,
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
            SubUseCase.use_case == match_result,
            SubUseCase.model == getattr(req, 'model', 'gpt')
        ).all()
        subusecase_names = [suc.sub_use_case for suc in subusecase_qs]
        sub_match = None
        if req.user_input.strip() and subusecase_names:
            sub_match = llm_subusecase_match(req.user_input, subusecase_names)
        if sub_match:
            subusecase_obj = next((suc for suc in subusecase_qs if suc.sub_use_case == sub_match), None)
            if subusecase_obj:
                final_prompt = clean_generated_prompt(subusecase_obj.prompt)
                variables = extract_input_headings(final_prompt)
                # Stage 2/3: Check for missing fields
                filled = extract_filled_variables(req.user_input, variables)
                missing = [k for k, v in filled.items() if not v]
                if missing:
                    return {
                        "stage": 2,
                        "clarify": True,
                        "missing_variables": missing,
                        "prompt_template": final_prompt,
                        "variables": variables,
                        "message": f"Please provide values for: {', '.join(missing)}"
                    }
                # All fields present, return final prompt
                return {
                    "stage": 3,
                    "source": "sub_use_case",
                    "sector": req.sector,
                    "use_case": match_result,
                    "sub_use_case": sub_match,
                    "user_input": req.user_input,
                    "prompt_template": final_prompt,
                    "variables": variables
                }
        # --- END SUB-USE CASE MATCHING ---
        prompt_obj = db.query(Prompt).filter(
            Prompt.use_case_id == match_uc.id,
            Prompt.model == getattr(req, 'model', 'gpt')
        ).first()
        if prompt_obj:
            final_prompt = review_and_edit_prompt(
                prompt_obj.content, req.sector, match_result, req.user_input
            )
            final_prompt = clean_generated_prompt(final_prompt)
            variables = extract_input_headings(final_prompt)
            filled = extract_filled_variables(req.user_input, variables)
            missing = [k for k, v in filled.items() if not v]
            if missing:
                return {
                    "stage": 2,
                    "clarify": True,
                    "missing_variables": missing,
                    "prompt_template": final_prompt,
                    "variables": variables,
                    "message": f"Please provide values for: {', '.join(missing)}"
                }
            return {
                "stage": 3,
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
        variables = extract_input_headings(final_prompt)
        filled = extract_filled_variables(req.user_input, variables)
        missing = [k for k, v in filled.items() if not v]
        if missing:
            return {
                "stage": 2,
                "clarify": True,
                "missing_variables": missing,
                "prompt_template": final_prompt,
                "variables": variables,
                "message": f"Please provide values for: {', '.join(missing)}"
            }
        return {
            "stage": 3,
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

    # New endpoint: GET /sub-use-cases
@router.get("/sub-use-cases")
def get_sub_use_cases(
    sector: str = Query(...),
    use_case: str = Query(...),
    db: Session = Depends(get_db),
):
    # Find sector
    sector_obj = db.query(Sector).filter(Sector.name == sector).first()
    if not sector_obj:
        raise HTTPException(status_code=404, detail="Sector not found.")
    # Find sub-use-cases for sector and use_case
    subusecases = db.query(SubUseCase).filter(
        SubUseCase.sector_id == sector_obj.id,
        SubUseCase.use_case == use_case
    ).all()
    sub_use_case_names = [suc.sub_use_case for suc in subusecases]
    return {"sub_use_cases": sub_use_case_names}
