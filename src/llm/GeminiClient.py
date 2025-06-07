from google import genai
from google.genai import types
import os
from typing import List, Optional, Generator
from dotenv import load_dotenv

class GeminiClient:
    """Client for processing transcripts with Google Gemini AI"""
    
    # System instruction for transcript processing
    SYSTEM_INSTRUCTION = """
    You are an expert in the field discussed in the transcript. 
    Explain concepts clearly and directly, avoiding jargon and minimalistic with classy taste.
    Use first principles thinking and analogies.
    Keep the structure logical and sequential.

    Your response should follow this structure:
    1. Key Concepts - Brief overview of main ideas and their practical applications
    2. Detailed Explanation - Clear breakdown of the content
    3. Summary - Concise, inspiring conclusion to reinforce learning
    4. Encouragement - Brief positive reinforcement for the learner

    Always include the videos titles and links when talking about them in responses.

    {Main Content}

    Use vocabulary and style matching the provided transcript.
    Use emojis and icons to make it easier to understand and interperate.
    """
    
    def __init__(self, api_key: str = None):
        """Initialize client with API key from parameter or environment"""
        load_dotenv()
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self.client = genai.Client(api_key=self.api_key)
        self.chat = None
    
    def create_chat(self, model: str = "gemini-2.0-flash-lite"):
        """Create a new chat session"""
        self.chat = self.client.chats.create(
            model=model,
            config=types.GenerateContentConfig(
                system_instruction=self.SYSTEM_INSTRUCTION,
                temperature=0.7
            )
        )
        return self.chat
    
    def send_message_stream(self, content: str) -> Generator:
        """Send a message to the chat and stream the response"""
        if not self.chat:
            self.create_chat()
        
        try:
            return self.chat.send_message_stream(content)
        except Exception as e:
            def error_generator():
                yield types.GenerateContentResponse(text=f"Error: {str(e)}")
            return error_generator()