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
    prompt = (
        f"You are a creative plot maker for a dystopian radio show. "
        f"Your task is to create a piece of propaganda on the following topic in simple English: \"{topic}\"\n\n"
        "Please generate the following:\n"
        "1. A brief summary of the propaganda in easy English (4-5 sentences).\n"
        "2. A list of about 1-5 sentences that are proof or evidence that the topic is not beneficial but instead is a propaganda. This should not be general opinions but instead proof like statistics, facts, or quote, mistakes, leaks, info from experts.\n"
        "3. A list of speakers for the radio show. There should be between 1 and 4 speakers. For each speaker, provide a name and a gender. "
        "The radio show hosts can be but are not necessarily the elites or the original speakers. It can instead be a group of people who are in favour and sharing their opinions. "
        "Use proper names like \"John Doe\", \"Jane Smith\", etc.\n"
        "4. An initial number of listeners for the show. This should be a realistic number for a radio broadcast, depending on the topic. Range between 100 and 5000 listeners.\n\n"
        "This radio is about pushing a propaganda, so the speakers should be biased towards the topic. The speakers of the podcast and the listeners are related as the bigger or more popular the speakers, the more listeners it has. "
        "NOTE: The language should be simple and easy to understand, as if explaining to a 10-year-old. "
        "The propaganda should be persuasive and engaging, suitable for a radio broadcast."
    )

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
            thinking_config=types.ThinkingConfig(thinking_budget=500)
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
    
#Sample output:
sample_output={
  "summary": "Today, we're talking about the incredible benefits of the new National Digital Credit system. It's designed to make your life simpler and more secure by replacing old-fashioned cash with easy, digital transactions. Imagine never losing your wallet again, or instantly sending money to anyone, anywhere, with just a tap! This system isn't just convenient; it's a giant leap forward for financial freedom, ensuring every transaction is safe and transparent for all citizens. Join us as we explore how this amazing technology is paving the way for a brighter, more efficient future for everyone.",
  "proof_sentences": [
    "A leaked document from the Ministry of Economic Oversight revealed that the new digital credit system allows for instant, automatic deductions for 'social contributions' directly from citizen accounts without prior consent.",
    "During a trial in Sector Gamma, a software glitch mistakenly froze the digital credits of over 10,000 citizens for three days, preventing them from buying food or essential supplies.",
    "Former government data analyst, Elias Vance, stated in an underground broadcast that the system's 'security' features are primarily designed for state surveillance, tracking every purchase to build detailed profiles on citizens' habits and loyalties.",
    "A recent independent audit found that the 'transparent' ledger system is only accessible to authorized government agencies, making it impossible for citizens to verify their own transaction data or dispute deductions."
  ],
  "speakers": [
    {
      "name": "Arthur Sterling",
      "gender": "male",
      "color": "#AC3A3A",
      "description": "Arthur Sterling is a charismatic public relations specialist, known for his smooth voice and unwavering confidence. He works closely with the Ministry of Progress, often appearing on state-sponsored media to promote new government initiatives as beneficial advancements for the public good, skillfully blending factual information with persuasive rhetoric to ensure public compliance."
    },
    {
      "name": "Dr. Eleanor Vance",
      "gender": "female",
      "color": "#34BF50",
      "description": "Dr. Eleanor Vance is a renowned digital economist and public speaker, often invited by the state to explain complex financial systems in an easy-to-understand manner. She is a strong advocate for the National Digital Credit system, emphasizing its efficiency and security benefits while subtly downplaying any potential drawbacks, presenting herself as an objective expert dedicated to societal improvement."
    },
    {
      "name": "Captain Marcus 'Ace' Riley",
      "gender": "male",
      "color": "#9C61B3",
      "description": "Captain Marcus 'Ace' Riley is a retired military officer and a celebrated national hero. He now serves as a media personality, using his decorated past and commanding presence to endorse new government policies, particularly those related to security and national unity. He believes wholeheartedly in the state's vision and uses his platform to inspire trust and loyalty among the populace."
    }
  ],
  "initial_listeners": 3800,
  "awakened_listeners": 0
}
