import os
import google.generativeai as genai
from fastapi import APIRouter, Depends, HTTPException
from fastapi import Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from db1 import get_db
from models.sector import Sector
from models.usecase import UseCase
from models.prompt import Prompt
from models.subusecase import SubUseCase
def llm_subusecase_match(user_input: str, subusecase_list: list[str], model: str):
    """LLM fuzzy match user input to a sub-use case string from the list. Returns the best match or None."""
    if not subusecase_list:
        return None
    system_prompt = (
        f"You are a financial sub-use case matcher. Here is the list of sub-use cases:\n"
        f"{', '.join(subusecase_list)}\n"
        "Given the user input, determine if it matches (by intent or phrasing) one of these sub-use cases. "
        "If yes, reply ONLY with the matching sub-use case string (no extra words). "
        "If not, reply ONLY with: NO_MATCH."
    )
    user_prompt = f"User Input: {user_input}"
    # The Gemini API expects a list of contents, not a role-based chat history like OpenAI.
    # We will format the prompt as a single string for simplicity here.
    full_prompt = f"{system_prompt}\n\n{user_prompt}"
    result = get_llm_response(full_prompt, model=model)
    return result if result != "NO_MATCH" else None

router = APIRouter(
    prefix="/api",
    tags=["Prompt Generation"]
)
## GROQ_API_KEY removed
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

def get_llm_response(prompt: str, model: str = "gemini-2.5-flash"):
    """Gets a response from a Gemini model."""
    if not GEMINI_API_KEY:
        raise HTTPException(status_code=500, detail="GEMINI_API_KEY not configured on server.")
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        gemini_model = genai.GenerativeModel(model)
        response = gemini_model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        print(f"Error calling Gemini API: {e}")
        raise HTTPException(status_code=503, detail="Error communicating with the AI service.")


class PromptRequest(BaseModel):
    sector: str
    use_case: str
    user_input: str = ""
    model: str = "gemini-2.5-flash"
    sub_use_case: str = ""  

class VariableFillRequest(BaseModel):
    prompt_template: str
    variables: dict

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


import ast
import re

def extract_input_headings(prompt_template: str) -> list:
    """
    Uses Gemini LLM to extract all input variable names (in [[Variable Name]] format) from a prompt template.
    Returns a list of variable names as strings.
    """
    system_prompt = (
        """You are an expert prompt parser. Given a prompt template, extract all user inputs required by the prompt. User inputs are typically under the Input section. Do not include any variables that require file uploads or other non-text inputs. If a variable is optional, include "(Optional)" in the variable name.
        Return ONLY a Python list of strings.
        Do not include any explanation, comments, or extra text.
        Do not return anything else as a response, just the list of variable names. No additional formatting or text."""
    )
    user_prompt = f"Prompt Template:\n{prompt_template}\n\nExtract all input variable names as a Python list."

    full_prompt = f"{system_prompt}\n\n{user_prompt}"
    response = get_llm_response(full_prompt, model="gemini-2.5-flash") # Use a fast model for parsing

    # --- Start of the fix ---
    
    # Use regex to find and extract the content within the python markdown block
    match = re.search(r"```python\s*([\s\S]*?)\s*```", response)
    
    clean_response = ""
    if match:
        clean_response = match.group(1).strip()
    else:
        # If no markdown block is found, assume the response is already clean
        clean_response = response.strip()

    # --- End of the fix ---

    try:
        # Now, parse the cleaned string
        variables = ast.literal_eval(clean_response)
        if isinstance(variables, list):
            return variables
    except (ValueError, SyntaxError) as e:
        print(f"Failed to parse the cleaned response: {e}")
        print(f"Cleaned response was: {clean_response}")

    # Fallback: return empty list if parsing fails
    return []




def clean_generated_prompt(prompt: str) -> str:
    prompt = re.sub(r"^\s*here is the improved prompt\s*\n", "", prompt, flags=re.IGNORECASE)
    prompt = re.sub(r"(?s)\*\*Example Input:\*\*.*?```.*?```\s*", "", prompt)
    prompt = re.sub(r"(?s)\*\*Example Output:\*\*.*?```.*?```\s*", "", prompt)
    return prompt.strip()

def llm_match_decision(sector: str, user_use_case: str, text_input: str, use_case_list: list[str], model: str):
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
    full_prompt = f"{system_prompt}\n\n{user_prompt}"
    return get_llm_response(full_prompt, model=model)

def generate_structured_prompt(sector: str, use_case: str, user_input: str, model: str):
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
    user_prompt = (
        f"Sector: {sector}\n"
        f"Use Case: {use_case}\n"
        f"User Goal: {user_input}\n\n"
        "Write a complete one-shot prompt that enables an LLM to execute the task in the context above."
    )
    full_prompt = f"{system_prompt}\n\n{user_prompt}"
    return get_llm_response(full_prompt, model=model)

def review_and_edit_prompt(prompt: str, sector: str, use_case: str, user_input: str, model: str):
    system_prompt = """
You are an expert prompt editor. Given a draft prompt, the financial sector, the use case, and the user's specific task description:
- If the prompt already precisely and fully matches the user's actual request, return it unchanged.
- If not, edit or reframe the prompt so it is a perfect fit for the actual user need. 
- Ensure the prompt is clear, actionable, and directly addresses the user's described task, using any specific language from the user input as needed.
- If the sector or use is "Something else", exclude the sector/use case from the prompt and focus on the user input.
- Prompt to start with a clear role description. 
- Do not edit the input fields or output structure
Do not include any additional explanations or comments or introduction(like Here is the improved prompt: )
"""
    user_prompt = (
        f"# Sector: {sector}\n"
        f"# Use Case: {use_case}\n"
        f"User Input: {user_input}\n\n"
        f"Draft Prompt to Review:\n{prompt}\n\n"
        "Edit the above draft so it exactly matches the user query, if necessary."
    )
    full_prompt = f"{system_prompt}\n\n{user_prompt}"
    return get_llm_response(full_prompt, model=model)

# Debug endpoint to check sub-use case data
@router.get("/debug-sub-use-case")
def debug_sub_use_case(
    sector: str = Query(...),
    use_case: str = Query(...),
    sub_use_case: str = Query(...),
    db: Session = Depends(get_db),
):
    """Debug endpoint to see what sub-use cases exist in the database"""
    
    # Find sector
    sector_obj = db.query(Sector).filter(Sector.name == sector).first()
    if not sector_obj:
        return {"error": "Sector not found", "sector": sector}
    
    # Find all sub-use cases for this sector and use_case
    all_subusecases = db.query(SubUseCase).filter(
        SubUseCase.sector_id == sector_obj.id,
        SubUseCase.use_case == use_case
    ).all()
    
    # Return debug info
    result = {
        "sector_found": True,
        "sector_id": sector_obj.id,
        "requested": {
            "sector": sector,
            "use_case": use_case,
            "sub_use_case": sub_use_case
        },
        "all_subusecases_for_usecase": []
    }
    
    for suc in all_subusecases:
        result["all_subusecases_for_usecase"].append({
            "id": suc.id,
            "use_case": suc.use_case,
            "sub_use_case": suc.sub_use_case,
            "model": suc.model,
            "exact_match": suc.sub_use_case == sub_use_case,
            "case_insensitive_match": suc.sub_use_case.lower() == sub_use_case.lower()
        })
    
    return result

@router.post("/prompt-universal")
def universal_prompt_handler(
    req: PromptRequest,
    sub_use_case: str = Query(""),  # Accept sub_use_case as query parameter
    db: Session = Depends(get_db),
):
    # Override the sub_use_case from request body with query parameter if provided
    if sub_use_case:
        req.sub_use_case = sub_use_case
    # If either sector or use_case is 'Something else', treat as custom prompt
    if req.sector == 'Something else' or req.use_case == 'Something else':
        if not req.user_input.strip():
            raise HTTPException(status_code=400, detail="Please provide a description in the input box for custom prompt generation.")
        # Always generate a new prompt for custom
        new_prompt = generate_structured_prompt(
            req.sector, req.use_case, req.user_input, model=req.model
        )
        
        final_prompt = review_and_edit_prompt(
            new_prompt, req.sector, req.use_case, req.user_input, model=req.model
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

    # --- SUB-USE CASE DIRECT FETCH (IMPROVED) ---
    if req.sub_use_case and req.sub_use_case.strip():
        print(f"DEBUG: Looking for sub-use case: '{req.sub_use_case}'")
        
        # First, try with the specified model (gemini)
        subusecase_obj = db.query(SubUseCase).filter(
            SubUseCase.sector_id == sector_obj.id,
            SubUseCase.use_case == req.use_case,
            SubUseCase.sub_use_case == req.sub_use_case,
            SubUseCase.model == 'gpt'
        ).first()
        
        # If not found with gemini, try with any model
        if not subusecase_obj:
            print("DEBUG: Not found with gemini model, trying any model...")
            subusecase_obj = db.query(SubUseCase).filter(
                SubUseCase.sector_id == sector_obj.id,
                SubUseCase.use_case == req.use_case,
                SubUseCase.sub_use_case == req.sub_use_case
            ).first()
        
        # If still not found, try case-insensitive search
        if not subusecase_obj:
            print("DEBUG: Not found with exact match, trying case-insensitive...")
            subusecase_obj = db.query(SubUseCase).filter(
                SubUseCase.sector_id == sector_obj.id,
                SubUseCase.use_case == req.use_case,
                SubUseCase.sub_use_case.ilike(req.sub_use_case)
            ).first()
        
        # If still not found, try fuzzy matching (remove special characters)
        if not subusecase_obj:
            print("DEBUG: Trying fuzzy match...")
            import re
            # Remove special characters and normalize
            normalized_input = re.sub(r'[^\w\s]', '', req.sub_use_case.lower())
            
            all_subusecases = db.query(SubUseCase).filter(
                SubUseCase.sector_id == sector_obj.id,
                SubUseCase.use_case == req.use_case
            ).all()
            
            for suc in all_subusecases:
                normalized_db = re.sub(r'[^\w\s]', '', suc.sub_use_case.lower())
                if normalized_input == normalized_db:
                    subusecase_obj = suc
                    print(f"DEBUG: Found fuzzy match: '{suc.sub_use_case}'")
                    break
        
        if subusecase_obj:
            print(f"DEBUG: Found sub-use case with model: {subusecase_obj.model}")
            final_prompt = clean_generated_prompt(subusecase_obj.prompt)
            variables = extract_input_headings(final_prompt)
            return {
                "stage": 1,
                "source": "sub_use_case",
                "sector": req.sector,
                "use_case": req.use_case,
                "sub_use_case": req.sub_use_case,
                "user_input": req.user_input,
                "prompt_template": final_prompt,
                "variables": variables,
                "model_used": subusecase_obj.model  # Include for debugging
            }
        else:
            # Log what we tried to find
            print(f"DEBUG: Sub-use case not found")
            print(f"Sector ID: {sector_obj.id}")
            print(f"Use case: '{req.use_case}'")
            print(f"Sub-use case: '{req.sub_use_case}'")
            
            # Return available sub-use cases for this use case
            available_subusecases = db.query(SubUseCase).filter(
                SubUseCase.sector_id == sector_obj.id,
                SubUseCase.use_case == req.use_case
            ).all()
            
            available_list = [suc.sub_use_case for suc in available_subusecases]
            
            raise HTTPException(
                status_code=404, 
                detail={
                    "message": "Prompt not found for this sub use case.",
                    "requested_sub_use_case": req.sub_use_case,
                    "available_sub_use_cases": available_list
                }
            )

    # If NO user_input, just fetch by exact use_case match (fast path)
    if not req.user_input.strip():
        match_uc = db.query(UseCase).filter(
            UseCase.sector_id == sector_obj.id,
            UseCase.name.ilike(req.use_case.strip())
        ).first()
        if match_uc:
            prompt_obj = db.query(Prompt).filter(
                Prompt.use_case_id == match_uc.id,
                Prompt.model == 'gpt'
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
        req.sector, req.use_case, req.user_input, use_case_names, model=req.model
    )
    if match_result in use_case_names:
        # Matched a use case, fetch prompt from DB
        match_uc = db.query(UseCase).filter(
            SubUseCase.sector_id == sector_obj.id,
            UseCase.name == match_result
        ).first()
        # --- SUB-USE CASE MATCHING ---
        subusecase_qs = db.query(SubUseCase).filter(
            SubUseCase.sector_id == sector_obj.id,
            SubUseCase.use_case == match_result,
            SubUseCase.model == 'gpt'
        ).all()
        subusecase_names = [suc.sub_use_case for suc in subusecase_qs]
        sub_match = None
        if req.user_input.strip() and subusecase_names:
            sub_match = llm_subusecase_match(req.user_input, subusecase_names, model=req.model)
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
            Prompt.model == 'gpt'
        ).first()
        if prompt_obj:
            final_prompt = review_and_edit_prompt(
                prompt_obj.content, req.sector, match_result, req.user_input, model=req.model
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
            req.sector, req.use_case, req.user_input, model=req.model
        )
        final_prompt = review_and_edit_prompt(
            new_prompt, req.sector, req.use_case, req.user_input, model=req.model
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


# Enhanced version of prompt filling with better validation and processing
@router.post("/prompt-fill-variables")
def fill_prompt_variables_enhanced(payload: VariableFillRequest):
    """Enhanced version of prompt filling with better validation and processing."""
    result = process_user_input_submission(payload.prompt_template, payload.variables)
    if result["status"] == "incomplete":
        raise HTTPException(
            status_code=400,
            detail=result["message"]
        )
    return {
        "final_prompt": result["final_prompt"],
        "filled_variables": result["filled_variables"]
    }

# New endpoint for getting form structure
@router.get("/prompt-form-fields")
def get_prompt_form_fields(prompt_template: str):
    """Get form field configuration for a prompt template."""
    return {
        "form_fields": create_input_form_data(prompt_template)
    }

def fill_prompt_with_user_inputs(prompt_template: str, user_inputs: dict) -> str:
    """
    Fill the prompt template with user-provided inputs.
    """
    filled_prompt = prompt_template
    variables = extract_input_headings(prompt_template)
    # Find the Input section by searching for the word 'Input' (case-insensitive)
    lower_prompt = filled_prompt.lower()
    input_word = "input"
    idx = lower_prompt.find(input_word)
    if idx == -1:
        raise ValueError("Input section not found in prompt template. Please check the template format.")
    # Find the start of the line containing 'Input'
    line_start = filled_prompt.rfind('\n', 0, idx) + 1 if '\n' in filled_prompt[:idx] else 0
    # Find the end of the Input section: next blank line or next section header
    after_input = filled_prompt[line_start:]
    # Find the end of the Input section by looking for two consecutive newlines or a section header (e.g., '**Output**')
    section_end = after_input.find('\n\n')
    if section_end == -1:
        # Try to find next section header (e.g., '**Output**', 'Output', etc.)
        import re
        m = re.search(r"\n\s*(\*\*)?[A-Za-z]+(\*\*)?\s*:?", after_input[len(input_word):])
        if m:
            section_end = m.start() + len(input_word)
        else:
            section_end = len(after_input)
    input_section = after_input[:section_end]
    before = filled_prompt[:line_start]
    after = after_input[section_end:]
    # Replace only the values for each variable in the Input section
    import re
    def replace_var_line(var, value, input_section):
        # Match lines like 'VarName : ...' (allow spaces, colon optional)
        pattern = rf"(^|\n)\s*{re.escape(var)}\s*:?\s*.*?(?=\n|$)"
        repl = f"\1{var} : {value}"
        return re.sub(pattern, repl, input_section, flags=re.IGNORECASE)
    for var in variables:
        user_value = user_inputs.get(var, '').strip()
        input_section = replace_var_line(var, user_value, input_section)
    new_prompt = before + input_section + after
    return new_prompt

def extract_and_validate_inputs(prompt_template: str, user_inputs: dict) -> dict:
    """
    Extract variables from prompt and validate against user inputs.
    """
    variables = extract_input_headings(prompt_template)
    missing_variables = []
    filled_variables = {}
    for var in variables:
        user_value = user_inputs.get(var, "")
        if user_value and str(user_value).strip():
            filled_variables[var] = str(user_value).strip()
        else:
            missing_variables.append(var)
    return {
        "all_variables": variables,
        "filled_variables": filled_variables,
        "missing_variables": missing_variables,
        "is_complete": len(missing_variables) == 0
    }

def create_input_form_data(prompt_template: str) -> list:
    """
    Create form data structure for frontend to render input fields.
    """
    all_variables = extract_input_headings(prompt_template)
    form_fields = []
    for var in all_variables:
        # Determine if field is optional based on the string itself
        is_optional = "(optional)" in var.lower()
        placeholder = f"Enter {var.lower()}..."
        form_fields.append({
            "name": var,
            "label": var,
            "type": "textarea" if len(var) > 20 else "text",
            "required": not is_optional,
            "placeholder": placeholder,
            "value": ""
        })
    return form_fields

def process_user_input_submission(prompt_template: str, user_inputs: dict) -> dict:
    """
    Process user input submission and return appropriate response.
    """
    validation = extract_and_validate_inputs(prompt_template, user_inputs)
    if not validation["is_complete"]:
        return {
            "stage": 2,
            "status": "incomplete",
            "missing_variables": validation["missing_variables"],
            "message": f"Please provide values for: {', '.join(validation['missing_variables'])}",
            "form_fields": create_input_form_data(prompt_template)
        }
    final_prompt = fill_prompt_with_user_inputs(prompt_template, user_inputs)
    return {
        "stage": 3,
        "status": "complete",
        "final_prompt": final_prompt,
        "filled_variables": validation["filled_variables"]
    }

# Enhanced version of your existing function
def extract_filled_variables_enhanced(user_input: str, variables: list) -> dict:
    """
    Enhanced version that tries to intelligently parse user input for multiple variables.
    """
    result = {}
    user_input_clean = user_input.strip() if user_input else ''
    if not user_input_clean:
        return {var: '' for var in variables}
    if len(variables) == 1:
        result[variables[0]] = user_input_clean
        return result
    for var in variables:
        patterns = [
            rf"{re.escape(var)}\s*:\s*([^\n,;]+)",
            rf"{re.escape(var)}\s*=\s*([^\n,;]+)",
            rf"{re.escape(var)}\s*-\s*([^\n,;]+)"
        ]
        found = False
        for pattern in patterns:
            match = re.search(pattern, user_input_clean, re.IGNORECASE)
            if match:
                result[var] = match.group(1).strip()
                found = True
                break
        if not found:
            if var.lower() in user_input_clean.lower():
                result[var] = user_input_clean
            else:
                result[var] = ''
    return result

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


@router.get("/prompt-filters")
def get_prompt_filters(sector: str = None, db: Session = Depends(get_db)):
    """
    Returns sector names (for category filter) and use case names (for tag filter) from the datalake.
    If sector is provided, only return use cases for that sector as tags.
    """
    # Get all sectors
    sectors = db.query(Sector).all()
    sector_names = [s.name for s in sectors]
    if sector:
        sector_obj = db.query(Sector).filter(Sector.name == sector).first()
        if sector_obj:
            use_cases = db.query(UseCase).filter(UseCase.sector_id == sector_obj.id).all()
            use_case_names = [uc.name for uc in use_cases]
        else:
            use_case_names = []
    else:
        use_case_names = []
    return {
        "categories": sector_names,
        "tags": use_case_names
    }