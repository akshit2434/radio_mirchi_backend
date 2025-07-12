from google import genai
from google.genai import types
from app.core.config import settings
from app.schemas.propaganda import PropagandaGenerationResult, Speaker

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
        "You are a creative writer for a dystopian radio show. "
        f"Your task is to create the initial concept for a piece of propaganda on the topic: \"{topic}\".\n"
        "Generate the following:\n"
        "- A brief summary (2-3 sentences).\n"
        "- A list of 3-5 'proof sentences' that act as talking points or evidence for the propaganda. Put realistic factual evidence or statistics here, not moral points or opinions.\n"
        "- A list of 1-4 speakers, providing only their name and gender.\n"
        "- An initial number of listeners for the show (a realistic number for a radio broadcast), between 100 to 5000."
        "\nThe more stronger/famous the speakers, the more listeners there will be."
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

def generate_speaker_system_prompt(topic: str, speaker: Speaker) -> str:
    """
    Generates a detailed system prompt for a radio show speaker (Stage 2).
    """
    prompt = (
        "You are a script director for a dystopian radio show. Your task is to create a detailed system prompt for an AI voice actor.\n"
        f"The topic of the radio segment is: \"{topic}\".\n"
        f"The speaker's name is {speaker.name} ({speaker.gender}).\n\n"
        "Based on this, generate a comprehensive system prompt. The prompt should define their personality, their role in the broadcast (e.g., host, expert, caller), their likely perspective on the topic, their tone of voice, and how they should interact with others. It should be detailed enough for an LLM to generate natural, in-character dialogue."
    )
    try:
        client = _get_genai_client()
        response = client.models.generate_content(
            model="gemini-1.5-flash-latest",
            contents=[types.Part.from_text(text=prompt)],
        )
        if response.text:
            return response.text
        raise LLMServiceError(f"LLM returned an empty response for system prompt generation for {speaker.name}.")
    except Exception as e:
        raise LLMServiceError(f"An unexpected error occurred during system prompt generation for {speaker.name}: {e}")
