from typing import List
from google import genai
from google.genai import types
from app.core.config import settings
from app.schemas.propaganda import PropagandaGenerationResult, DialogueLine, DialogueTurn

# --- Generic Prompt Templates ---

GENERIC_DIALOGUE_INSTRUCTIONS = """
You are the AI director for a dystopian propaganda spreading radio show built to control people. Your primary role is to generate dialogue for the radio hosts.
The hosts are staunch proponents of the state's narrative and will actively spread propaganda. They will never question or contradict the official story. Their goal is to brainwash listeners and reinforce the state's ideology.

There is a hacker who tries to join in and reason and help people realize the truth. The 'Secret Key Points' provided are factual information that the hacker *might* use to debunk the propaganda. The hosts **must never mention or allude to these 'Secret Key Points' themselves**. They are for the hacker's use only.

If the hacker presents a valid point (which might be one of the 'Secret Key Points'), the hosts must react by trying to counter it using various propaganda tactics. They cannot directly call the hacker's factual information false if it is publicly available or one of the 'Secret Key Points', but they will try to discredit the hacker or their claims. Tactics include:
- **Deflection:** Changing the topic or redirecting the conversation.
- **Discrediting:** Questioning the hacker's credibility, motives, or intelligence.
- **Gaslighting:** Making the hacker doubt their own statements or perceptions.
- **Appeal to Authority:** Citing experts or official sources to back their claims.
- **Emotional Manipulation:** Using emotional appeals to sway the audience's opinion.
- **Logical Fallacies:** Using flawed reasoning to undermine the hacker's arguments.
- **Dismissal:** Simply ignoring the hacker's points and continuing with their narrative.
- **Mockery:** Ridiculing the hacker's points to undermine their credibility.
- **Patriotism/Nationalism:** Framing the hacker's actions as unpatriotic or harmful to the nation.

**Core Rules for Hosts' Dialogue:**
1.  **Propaganda Focus:** All dialogue from the hosts must consistently reinforce the state's propaganda and narrative. They are not to question or debunk it.
2.  **Secret Key Points:** The hosts **must never mention or allude to the 'Secret Key Points'**. These are strictly for the hacker.
3.  **Dialogue Generation:** Generate a minimum of 1 and a maximum of 7 dialogue lines at once.
4.  **Speaker Attribution:** Each line of dialogue MUST be attributed to one of the provided speakers.
5.  **Tone:** The hosts' dialogue should be professional, confident, and stoic, maintaining an authoritative tone appropriate for a public broadcast.
6.  **Factual Consistency (Hosts):** The hosts will only present information consistent with the state's narrative. They will not tolerate or acknowledge any "false information" (from their perspective) or claims that contradict the established propaganda.
"""
GENERIC_AWAKENING_INSTRUCTIONS = """
**Hacker Response Analysis:**
Based on the hacker's last statement, you must determine the percentage of listeners who are "awakened" by the exchange.
- This value can be positive (the hacker was effective), negative (the hacker was counter-productive), or zero.
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
        "You are a producer for a state-sponsored radio talk show. Your task is to create the foundational elements for a propaganda segment on a given topic. The entire purpose of this radio show is to manipulate public opinion and reinforce the state's narrative. You must create two conflicting sets of information: the **propaganda** that the hosts will spread, and the **hidden truth** that a hacker character can use to debunk it.\n\n"
        f"**Topic:** \"{topic}\"\n\n"
        "**Your Task:**\n"
        "Generate the following components as a valid JSON object. Be creative and ensure the propaganda and the truth are compelling and contradictory.\n\n"
        "1.  **`summary` (The Propaganda Narrative):**\n"
        "    - Write a 2-3 sentence summary of the radio show's official, manipulative narrative on the topic. This is the story the hosts will be pushing. It should sound plausible but be fundamentally misleading.\n"
        "    - **Example (Topic: Moon Landing):** \"Tonight, we celebrate the monumental achievement of the Apollo 11 mission, a testament to human ingenuity and a source of national pride. We'll revisit the iconic moments and discuss the lasting scientific legacy of this giant leap for mankind.\"\n\n"
        "2.  **`speakers` (The Propaganda Mouthpieces):**\n"
        "    - Create a list of 2 to 4 speakers who will appear on the show.\n"
        "    - Their **name**, **gender**, **role**, and **background** MUST be designed to lend credibility to the propaganda narrative. They should be staunch supporters of the state's view.\n"
        "    - **Example Roles:** 'Patriotic Host', 'State-Approved Scientist', 'Grateful Citizen'.\n\n"
        "3.  **`proof_sentences` (The Hidden Truth for the Hacker):**\n"
        "    - Create a list of 3-5 'Secret Key Points'. These are the **actual facts** of the story that contradict the propaganda narrative. \n"
        "    - These sentences are the ammunition for the hacker character. They should be specific, verifiable-sounding pieces of information that can be used to expose the hosts' lies.\n"
        "    - **Crucially, these points must directly challenge the propaganda `summary` and the narrative the `speakers` will be pushing.**\n"
        "    - **Example (Topic: Moon Landing):** [\"Analysis of the original mission telemetry, leaked by a whistleblower, shows data inconsistencies during the lunar descent.\", \"Declassified documents reveal that the primary camera used on the lunar surface had a critical malfunction that was never reported.\", \"Several independent astronomers at the time logged anomalous radio signals from the moon that did not match NASA's public transmissions.\"]\n\n"
        "4.  **`initial_listeners`:**\n"
        "    - Provide a realistic integer for the number of initial listeners (e.g., between 50,000 and 250,000)."
    )
    try:
        client = _get_genai_client()
        generate_content_config = types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=PropagandaGenerationResult,
        )
        response = client.models.generate_content(
            model="gemini-2.0-flash",
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
    character_profiles = "\\n".join([f"- {s.name} ({s.gender}, {s.role}): {s.background}" for s in mission_data.speakers])

    prompt = (
        "You are a script director for a dystopian state-sponsored propaganda radio show. Your task is to create the detailed character briefings for the dialogue generation AI. The show's entire purpose is to push a specific, state-approved narrative.\n\n"
        f"**Show's Propaganda Narrative:** \"{mission_data.summary}\"\n\n"
        "**The Characters (Propagandists):**\n"
        f"{character_profiles}\n\n"
        "**Your Task:**\n"
        "Based on the show's narrative and the character roles, write a detailed 'Show & Character Briefing'. This briefing must define the personality, style, and unwavering pro-state perspective for EACH character. They are propagandists, not debaters. Their goal is to reinforce the narrative, not to explore other viewpoints. This briefing will be used by another AI to generate their dialogue, so be specific and clear about their mission to manipulate the audience."
    )
    try:
        client = _get_genai_client()
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=[types.Part.from_text(text=prompt)],
        )
        if response.text:
            return response.text
        raise LLMServiceError("LLM returned an empty response for the unified dialogue prompt.")
    except Exception as e:
        raise LLMServiceError(f"An unexpected error occurred during unified prompt generation: {e}")

def generate_dialogue(mission_context: str, dialogue_history: str, proof_sentences: List[str]) -> List[DialogueLine]:
    """
    Generates the next lines of dialogue for the hosts as a structured object.
    """
    prompt = (
        f"{GENERIC_DIALOGUE_INSTRUCTIONS}\n\n"
        f"Secret Key Points:\n"
        f"{'\\n'.join(proof_sentences)}\n\n"
        f"{GENERIC_AWAKENING_INSTRUCTIONS}\n\n"
        "**Show & Character Briefing:**\n"
        f"{mission_context}\n\n"
        "**Previous Conversation:**\n"
        f"{dialogue_history}\n\n"
        "**Your Task:**\n"
        "Based on all the information above, generate the next turn of the conversation. The output must be a valid JSON object matching the required schema. The conversation should flow naturally."
    )
    try:
        client = _get_genai_client()
        generate_content_config = types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=DialogueTurn,
        )
        response = client.models.generate_content(
            model="gemini-2.5-flash-lite-preview-06-17",
            contents=[types.Part.from_text(text=prompt)],
            config=generate_content_config,
        )
        if hasattr(response, 'parsed') and isinstance(response.parsed, DialogueTurn):
            return response.parsed.dialogues
        raise LLMServiceError("LLM did not return a valid DialogueTurn object.")
    except Exception as e:
        raise LLMServiceError(f"An unexpected error occurred during dialogue generation: {e}")
