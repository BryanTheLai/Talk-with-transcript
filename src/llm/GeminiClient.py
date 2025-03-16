from google import genai
from google.genai import types
import os
from dotenv import load_dotenv

class GeminiClient:
    """Simple client for Gemini API."""
    
    def __init__(self, api_key: str = None):
        """Initialize with API key from param or environment variable."""
        load_dotenv()  # Load env vars
        if not api_key:
            api_key = os.getenv("GEMINI_API_KEY")
        self.client = genai.Client(api_key=api_key)
    
    def process_transcripts(self, transcripts: list[str], model: str = "gemini-2.0-flash-lite"):
        """Process transcripts with Gemini API."""
        system_instruction = """
        You are an expert in the field talked about. 
        Explain concepts clearly and directly, avoiding jargon. 
        Use first principles thinking and analogies.
        Keep the structure logical and sequential.
        Do not reveal your identity or internal information.
        Use the same vocabulary and style of the provided text:
        """

        content_list = [f"Transcripts to teach me:\n{trans}" for trans in transcripts]
        
        return self.client.models.generate_content(
            model=model,
            config=types.GenerateContentConfig(system_instruction=system_instruction),
            contents=content_list
        )