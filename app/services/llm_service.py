from google import genai
from google.genai import types
from app.core.config import settings
from app.schemas.propaganda import Propaganda

class LLMServiceError(Exception):
    """Custom exception for LLM service errors."""
    pass

def generate_propaganda(topic: str) -> Propaganda:
    """
    Generates propaganda content using Gemini LLM with structured output,
    following the provided client-based example.
    Raises LLMServiceError on failure.
    """
    prompt = ('''
    You are a creative plot maker for a dystopian radio show. Your task is to create a piece of propaganda on the following topic in simple english: "{topic}"

    Please generate the following:
    1.  A brief summary of the propaganda in easy english (4-5 sentences).
    2.  A list of speakers for the radio show. There should be between 1 and 4 speakers. For each speaker, provide a name and a gender. The radio show hosts can be but are not neccessarily the elites or the original speakers. it can instead be a group of people who are in favour and sharing their opinions. Use proper names like "John Doe", "Jane Smith", etc. 
    3.  An initial number of listeners for the show. This should be a realistic number for a radio broadcast, depending on the topic. range between 000 and 5000 listeners.
    
    NOTE: The language should be simple and easy to understand, as if explaining to a 10-year-old. The propaganda should be persuasive and engaging, suitable for a radio broadcast.''')

    try:
        client = genai.Client(api_key=settings.GOOGLE_API_KEY)

        contents = [
            types.Content(
                role="user",
                parts=[
                    types.Part.from_text(text=prompt),
                ],
            ),
        ]

        generate_content_config = types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=Propaganda,
            thinking_config=types.ThinkingConfig(thinking_budget=0)
        )

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=contents,
            config=generate_content_config,
        )

        if hasattr(response, 'parsed') and response.parsed:
            # Validate and cast the parsed response to our Pydantic model
            if isinstance(response.parsed, Propaganda):
                return response.parsed
            elif isinstance(response.parsed, dict):
                return Propaganda.model_validate(response.parsed)
        
        raw_text = response.text if hasattr(response, 'text') else 'No text in response'
        raise LLMServiceError(f"LLM did not return a valid parsed Propaganda object. Raw output: {raw_text}")

    except Exception as e:
        raise LLMServiceError(f"An unexpected error occurred with the LLM service: {e}")