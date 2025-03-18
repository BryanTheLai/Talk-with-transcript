from google import genai
from google.genai import types
import os
from typing import List
from dotenv import load_dotenv

class GeminiClient:
    """Client for processing transcripts with Google Gemini AI"""
    
    # System instruction for transcript processing
    SYSTEM_INSTRUCTION = """
    You are an expert in the field discussed in the transcript. 
    Explain concepts clearly and directly, avoiding jargon. 
    Use first principles thinking and analogies.
    Keep the structure logical and sequential.

    Your response should follow this structure:
    1. Key Concepts - Brief overview of main ideas and their practical applications
    2. Detailed Explanation - Clear breakdown of the content
    3. Summary - Concise, inspiring conclusion to reinforce learning
    4. Encouragement - Brief positive reinforcement for the learner

    Use vocabulary and style matching the provided transcript.
    """
    
    def __init__(self, api_key: str = None):
        """Initialize client with API key from parameter or environment"""
        load_dotenv()
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self.client = genai.Client(api_key=self.api_key)
    
    def process_transcripts(self, transcripts: List[str], model: str = "gemini-2.0-flash-lite"):
        """Process transcripts with Gemini AI for educational content generation"""
        # Format each transcript as separate content block for the model
        content_list = [{"text": f"Transcript to teach me:\n{trans}"} for trans in transcripts]
        
        return self.client.models.generate_content(
            model=model,
            config=types.GenerateContentConfig(system_instruction=self.SYSTEM_INSTRUCTION),
            contents=content_list
        )