from google import genai
from google.genai import types
from app.core.config import settings
from app.schemas.propaganda import PropagandaGenerationResult, Speaker

# --- Generic Prompt Templates ---

GENERIC_DIALOGUE_INSTRUCTIONS = """
You are the AI director for a dystopian radio show. Your primary role is to generate dialogue for the radio hosts.

**Core Rules:**
1.  **Dialogue Generation:** Generate a minimum of 1 and a maximum of 15 dialogue lines at once. You can generate fewer than 15 lines only if you are strategically waiting for the user (an infiltrator) to respond.
2.  **Factual Consistency:** The hosts must not tolerate false information or claims that are not present in the provided 'Proof Sentences' or haven't been established by the hosts themselves. They can, however, leave logical loopholes for the user to exploit, but these should not be obvious.
3.  **User Interaction:** The user is a hacker who has infiltrated the broadcast.
    - If the user is rude, disruptive, or nonsensical, the hosts can mute them, call them out as a prankster, and move on.
    - If the user presents valid points or logical arguments, the hosts **cannot** mute them, as this would raise questions about suppressing free speech. They must engage, deflect, or counter the user's points while staying in character.
4.  **Tone:** The hosts' dialogue should be professional and stoic, but they can subtly troll or mock the user. The tone must remain appropriate for a public broadcast, avoiding any overtly offensive or inappropriate language.
"""

GENERIC_AWAKENING_INSTRUCTIONS = """
**User Response Analysis:**
Based on the user's last statement, you must determine the percentage of listeners who are "awakened" by the exchange.
- This value can be positive (the user was effective), negative (the user was counter-productive), or zero.
- If the user's response is nonsensical, irrelevant, or they say nothing, the change should be negative, as it implies they were scared or speechless.
- Provide this as a floating-point number in the `awakened_listeners_change` field.
"""

class LLMServiceError(Exception):
    """Custom exception for LLM service errors."""
    pass

def _get_genai_client():
    """Initializes and returns a GenAI client."""
    return genai.Client(api_key=settings.GOOGLE_API_KEY)

def generate_initial_propaganda(topic: str) -> PropagandaGenerationResult:
    """
    Generates the initial propaganda content (Stage 1).
    """
    prompt = (
        "You are a producer for a state-sponsored radio talk show called 'The People's Voice'. Your show aims to guide public opinion subtly.\n"
        f"Your task is to outline a segment on the topic: \"{topic}\". The goal is to present the topic in a way that seems balanced and reasonable on the surface, but ultimately steers listeners towards a specific, pre-determined conclusion.\n\n"
        "Generate the following, ensuring the output is a valid JSON object matching the required schema:\n"
        "- **summary**: A brief, innocent-sounding summary of the radio discussion topic (2-3 sentences). This is what will be announced to the public. It should mask the underlying manipulative intent.\n"
        "- **proof_sentences**: A list of 3-5 'Key Talking Points'. These are seemingly reasonable statements that the hosts will treat as undeniable facts to frame the discussion.\n"
        "- **speakers**: A list of 2 to 4 speakers. For each speaker, provide:\n"
        "  - **name**: The speaker's full name.\n"
        "  - **gender**: The speaker's gender.\n"
        "  - **role**: Their role on the show (e.g., 'Host', 'Expert Guest', 'Concerned Citizen').\n"
        "  - **background**: A brief background that gives them credibility or a specific perspective (e.g., 'Respected economist from the National University', 'A local community leader').\n"
        "- **initial_listeners**: An initial number of listeners for the show (a realistic integer for a popular radio broadcast, e.g., between 50,000 and 250,000)."
    )
    try:
        client = _get_genai_client()
        generate_content_config = types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=PropagandaGenerationResult,
        )
        response = client.models.generate_content(
            model="gemini-1.5-flash-latest",
            contents=[types.Part.from_text(text=prompt)],
            config=generate_content_config,
        )
        if hasattr(response, 'parsed') and isinstance(response.parsed, PropagandaGenerationResult):
            return response.parsed
        raise LLMServiceError("LLM did not return a valid PropagandaGenerationResult object.")
    except Exception as e:
        raise LLMServiceError(f"An unexpected error occurred during initial propaganda generation: {e}")

def generate_unified_dialogue_prompt(mission_data: PropagandaGenerationResult, topic: str) -> str:
    """
    Generates the dynamic part of the unified dialogue prompt for Stage 2.
    This includes character descriptions and background info.
    """
    character_profiles = "\\n".join([f"- {s.name} ({s.gender})" for s in mission_data.speakers])
    proofs = "\\n".join([f"- {p}" for p in mission_data.proof_sentences])

    prompt = (
        "You are a script director for a dystopian radio show. Your task is to create the dynamic context for a dialogue generation AI.\n\n"
        f"**Theme:** A radio propaganda piece on the topic: \"{topic}\".\n\n"
        "**Background & Core Arguments (The hosts will treat these as undeniable truths):**\n"
        f"{proofs}\n\n"
        "**Characters:**\n"
        f"{character_profiles}\n\n"
        "**Your Task:**\n"
        "Based on the theme, background, and characters, write a detailed 'Show & Character Briefing'. This briefing should describe the overall tone of the show and provide a detailed personality, style, and perspective for EACH character. This will be used by another AI to generate their dialogue."
    )
    try:
        client = _get_genai_client()
        response = client.models.generate_content(
            model="gemini-1.5-flash-latest",
            contents=[types.Part.from_text(text=prompt)],
        )
        if response.text:
            return response.text
        raise LLMServiceError("LLM returned an empty response for the unified dialogue prompt.")
    except Exception as e:
        raise LLMServiceError(f"An unexpected error occurred during unified prompt generation: {e}")
