from google import genai
from google.genai import types
import os
from typing import List, Optional, Generator, Any
from dotenv import load_dotenv

class GeminiClient:
    """Client for processing content with Google Gemini AI"""
    
    # System instruction for transcript processing (only used for chat)
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
    
    def __init__(self, api_key: Optional[str] = None):
        """Initialize client with API key from parameter or environment"""
        load_dotenv()
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self.client = genai.Client(api_key=self.api_key)
        self.chat = None
    
    def create_chat(self, model: str = "gemini-2.0-flash"):
        """Create a new chat session with system instruction"""
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
    
    def generate_content(self, model: str, contents: List) -> Any:
        """Generate content directly without chat context
        
        This method calls the models API directly for one-time generation 
        without using any chat history or system instructions.
        Used for image processing, PDF conversion, etc.
        
        Args:
            model: Name of the model to use (e.g., "gemini-2.0-flash")
            contents: List of content parts (text, images, etc.)
            
        Returns:
            Generation response
        """
        try:
            # Direct model call without chat context or system instructions
            response = self.client.models.generate_content(
                model=model,
                contents=contents
            )
            return response
        except Exception as e:
            # Provide more informative error that mimics the response structure
            error_message = f"Error generating content: {str(e)}"
            print(error_message)  # Log the error
            
            # Return a similar error structure as the chat method to maintain consistency
            class ErrorResponse:
                def __init__(self, error_text):
                    self.text = error_text
            
            return ErrorResponse(error_message)