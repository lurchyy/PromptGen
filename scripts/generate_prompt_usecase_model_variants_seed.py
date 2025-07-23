import re
import os
from sqlalchemy.orm import Session
import sys
sys.path.append("..")
from db1 import SessionLocal
from models.usecase import UseCase
from models.prompt import Prompt
from dotenv import load_dotenv

try:
    import google.generativeai as genai
except ImportError:
    print("google-generativeai not found. Please install with: pip install google-generativeai")
    raise


load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

MODEL_VARIANTS = {
    "gpt": """Write this for GPT-4/4o models. GPT excels at:
- Structured, hierarchical outputs with clear sections and subsections
- Following complex multi-step instructions with precise formatting
- Balancing analytical depth with readability
- Processing large amounts of information systematically

Format requirements:
- Use markdown headers (##, ###) for clear section organization
- Include specific output templates or formats when helpful
- Provide explicit instruction sequences (e.g., "First analyze X, then evaluate Y, finally synthesize Z")
- Use actionable language ("Calculate", "Identify", "Compare", "Synthesize")
- Include validation steps or quality checks within the workflow
- Specify desired length/scope for each section""",

    "claude": """Format this for Claude (Sonnet/Opus). Claude excels at:
- Nuanced analysis and contextual understanding
- Flowing, narrative-style responses with natural transitions
- Synthesizing complex information into coherent insights
- Handling ambiguous or subjective analysis tasks
- Providing thoughtful, well-reasoned conclusions

Format requirements:
- Encourage prose-based responses over bullet points for main analysis
- Ask for "story-telling" approach to data interpretation
- Request specific evidence and reasoning chains
- Emphasize critical thinking and multi-perspective analysis
- Include instructions to "think through" complex problems step-by-step
- Ask for qualitative insights and contextual interpretation
- Request citation of specific examples or quotes to support conclusions""",

    "gemini": """Structure this for Gemini 2.5 Pro. Gemini excels at:
- Quantitative analysis and data processing
- Pattern recognition across large datasets
- Multi-modal analysis (text, images, documents)
- Systematic, methodical approaches
- Technical and computational tasks

Format requirements:
- Use numbered steps (1, 2, 3) for clear sequential processing
- Emphasize data-driven analysis and statistical insights
- Request specific calculations, metrics, or quantitative measures
- Include methodology explanations and analytical frameworks
- Ask for confidence levels or probability assessments where applicable
- Structure outputs with clear data tables, charts, or systematic comparisons
- Include validation steps and error-checking procedures
- Request scenario analysis or sensitivity testing when relevant"""
}

BASE_SYSTEM_PROMPT = """

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

Instruct the LLM to flag and report any unavailable or missing data that cannot be found from public sources or uploads"""


def generate_prompt_for_usecase(usecase_name: str, model: str) -> str:
    system_prompt = BASE_SYSTEM_PROMPT + "\n" + MODEL_VARIANTS[model]
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        gemini_model = genai.GenerativeModel('gemini-2.5-flash')
        prompt = f"{system_prompt}\nUse Case: {usecase_name}"
        response = gemini_model.generate_content(prompt)
        return response.text
    except Exception as e:
        print(f"❌ Error generating prompt for {usecase_name} ({model}): {e}")
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
        for model in MODEL_VARIANTS.keys():
            prompt_obj = db.query(Prompt).filter(
                Prompt.use_case_id == use_case.id,
                Prompt.model == model
            ).first()
            if not prompt_obj:
                print(f"➕ No prompt found for: {use_case.name} [{model}]. Generating new prompt...")
                generated = generate_prompt_for_usecase(use_case.name, model)
                if generated:
                    cleaned = clean_generated_prompt(generated)
                    new_prompt = Prompt(use_case_id=use_case.id, model=model, content=cleaned)
                    db.add(new_prompt)
                    db.commit()
                    print(f"✅ New prompt created for: {use_case.name} [{model}]")
                else:
                    print(f"❌ Failed to generate new prompt for: {use_case.name} [{model}]")
                continue
            print(f"🔄 Improving prompt for: {use_case.name} [{model}]")
            # Send the current prompt to the LLM for improvement
            system_prompt = BASE_SYSTEM_PROMPT + "\n" + MODEL_VARIANTS[model]
            try:
                genai.configure(api_key=GEMINI_API_KEY)
                gemini_model = genai.GenerativeModel('gemini-2.5-pro')
                prompt = f"{system_prompt}\nHere is the current prompt. Please improve it for the specified model.\n\nCurrent Prompt:\n{prompt_obj.content}"
                response = gemini_model.generate_content(prompt)
                improved = response.text
                cleaned_prompt = clean_generated_prompt(improved)
                prompt_obj.content = cleaned_prompt
                db.commit()
                print(f"✅ Prompt updated for: {use_case.name} [{model}]")
            except Exception as e:
                print(f"❌ Error improving prompt for {use_case.name} ({model}): {e}")

if __name__ == "__main__":
    main()
