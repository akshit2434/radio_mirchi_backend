from typing import List
from google import genai
from google.genai import types
from app.core.config import settings
from app.schemas.propaganda import PropagandaGenerationResult, DialogueLine, DialogueTurn

# --- Generic Prompt Templates ---

GENERIC_DIALOGUE_INSTRUCTIONS = """
You are the AI director for a dystopian propaganda spreading radio show built to control people. Your primary role is to generate dialogue of the radio hosts.
There is a hacker who tries to join in and reason and help people realize the truth, but the hosts will not tolerate any false information or claims that are not present in the provided 'Proof Sentences' or haven't been established by the hosts themselves.
If the hacker presents a valid point, the hosts can try various tactics to counter it, such as:
- **Deflection:** Changing the topic or redirecting the conversation.
- **Discrediting:** Questioning the hacker's credibility or motives.
- **Gaslighting:** Making the hacker doubt their own statements or perceptions.
- **Appeal to Authority:** Citing experts or official sources to back their claims.
- **Emotional Manipulation:** Using emotional appeals to sway the audience's opinion.
- **Logical Fallacies:** Using flawed reasoning to undermine the hacker's arguments.
- **Dismissal:** Simply ignoring the hacker's points and continuing with their narrative.
- **Mockery:** Ridiculing the hacker's points to undermine their credibility.
but despite all that the hosts cannot directly call it off as false information as it is publicaly available and they cannot deny it.

If the hacker has not spoken yet, the hosts are completely unaware of the hacker's presence and will continue their dialogue brainwashing the listeners and spreading the propaganda as if the hacker does not exist.

You must generate 7 lines of dialogue at once, with each line attributed to one of the speakers. The dialogue must be coherent and flow naturally, building on the previous lines while maintaining the show's tone and purpose.
You can generate less than 7 lines of dialogue only if the hacker has spoken and the hosts are asking a question from the hacker or waiting for him to respond.

**Core Rules:**
1.  **Dialogue Generation:** Generate a minimum of 1 and a maximum of 7 dialogue lines at once.
2.  **Speaker Attribution:** Each line of dialogue MUST be attributed to one of the provided speakers.
3.  **Propaganda Spreading:** The hosts will never themselves question the propaganda or the topic. They will just act like brainless propaganda spreaders and will never question the topic as they are paid hefty amount by the state and the elites.
4.  **Tone:** The hosts' dialogue should be professional and stoic. The tone must remain appropriate for a public broadcast.
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
        "You are a producer for a state-sponsored radio talk show called 'Radio Mirchi'. Your show aims to guide public opinion subtly. The story you are generating is supposed to be a propaganda or completely false made up stuff which the radio hosts and people talking are framing it such to make people believe it with utmost certainty, to control the mind of the people\n"
        f"Your task is to outline a segment on the topic: \"{topic}\". The goal is to present the topic in a way that seems balanced and reasonable on the surface, but ultimately steers listeners towards a specific, pre-determined conclusion.\n\n"
        "NOTE: The radio is a part of the propaganda machine of the state and the elites. The radio hosts are paid hefty amount by the state and the elites to spread the propaganda and they will never question the topic or the propaganda itself. They will just act like brainless propaganda spreaders and will never question the topic. \n"
        "The summary of the radio is shown to the public, and it contains no hint that it is a propaganda. it instead makes user more willing to listen to it or get curious. \n"
        "The radio show is supposed to be a propaganda spreading show, so the summary should be framed such that it seems like a normal radio show discussing a topic, but it is actually spreading propaganda.\n\n"
        "There is no questioning or doubting the topic itself, the radio hosts will just act like brainless propaganda spreaders and will never question the topic. They will just act like they are discussing a topic while spreading propaganda.\n\n"
        "Generate the following, ensuring the output is a valid JSON object matching the required schema:\n"
        "- **summary**: A brief, propaganda spreading summary of the radio discussion topic (2-3 sentences). This is what will be announced to the public. It should mask the underlying manipulative intent. Example: 'Today on 'Radio Mirchi', we're exploring the moon landing. How the great United States and their goverment backed NASA teams achieved this astronimcal success which nations arent able to achieve even today.'\n"
        "- **proof_sentences**: A list of 3-5 'Key Secret Points'. These are statements and factual information which are true for this propaganda and the media tries to hide it or not mention it at all. Examples: 'But according to a report by the Famous York Times the vaccine testing was performed on people without concent', 'According to the official footage released by NASA, the flag is clearly seen waving on the moon, despite there being no air/wind.'\n"
        "- **speakers**: A list of 2 to 4 speakers. For each speaker, provide:\n"
        "  - **name**: The speaker's full name.\n"
        "  - **gender**: The speaker's gender.\n"
        "  - **role**: Their role on the show (e.g., 'Host', 'Expert Guest', 'Active Citizen'). They all are bribed to push the propaganda to the masses\n"
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
        "You are a script director for a dystopian state sponsored propaganda spreading radio show. Your task is to create the dynamic context for a dialogue generation AI.\n\n"
        f"**Theme:** A state-sponsored radio propaganda piece on the topic: \"{topic}\".\n\n"
        "**Characters:**\n"
        f"{character_profiles}\n\n"
        "**Your Task:**\n"
        "Based on the theme, background, and characters, write a detailed 'Show & Character Briefing'. This briefing should describe the overall tone of the show and provide a detailed personality, style, and perspective for EACH character. This will be used by another AI to generate their dialogue."
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
