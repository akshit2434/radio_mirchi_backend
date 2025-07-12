import google.generativeai as genai
import json
from app.core.config import settings
from app.schemas.propaganda import Propaganda

class LLMServiceError(Exception):
    """Custom exception for LLM service errors."""
    pass

genai.configure(api_key=settings.GOOGLE_API_KEY)

model = genai.GenerativeModel('gemini-2.5-flash-lite-preview-06-17')

def generate_propaganda(topic: str) -> Propaganda:
    """
    Generates propaganda content using the Gemini LLM.
    Raises LLMServiceError on failure.
    """
    prompt = f"""
    You are a creative writer for a dystopian radio show. Your task is to create a piece of propaganda on the following topic: "{topic}"

    Please generate the following:
    1.  A brief summary of the propaganda (2-3 sentences).
    2.  A list of speakers for the radio show. There should be between 1 and 4 speakers. For each speaker, provide a name and a gender.
    3.  An initial number of listeners for the show. This should be a realistic number for a radio broadcast, depending on the topic.

    Please provide the output in a valid JSON format, like this example:
    {{
        "summary": "A new government program promises to enhance security and prosperity for all citizens by monitoring communications. It is presented as a necessary step for safety and unity.",
        "speakers": [
            {{"name": "General Thorne", "gender": "Male"}},
            {{"name": "Dr. Aris", "gender": "Female"}}
        ],
        "initial_listeners": 15000
    }}
    """

    try:
        response = model.generate_content(prompt)
        cleaned_json = response.text.strip().replace("```json", "").replace("```", "").strip()
        propaganda_data = json.loads(cleaned_json)

        return Propaganda(
            summary=propaganda_data["summary"],
            speakers=propaganda_data["speakers"],
            initial_listeners=propaganda_data["initial_listeners"],
        )
    except (json.JSONDecodeError, KeyError) as e:
        raise LLMServiceError(f"Failed to parse LLM response: {e}")
    except Exception as e:
        raise LLMServiceError(f"An unexpected error occurred with the LLM service: {e}")