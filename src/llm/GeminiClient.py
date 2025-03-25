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
    
    def create_chat(self, model: str = "gemini-2.0-flash"):
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
        
    def process_pdf(self, pdf_path: str, prompt: str = "Convert this document to well-formatted Markdown") -> str:
        """
        Process a PDF file directly using Gemini's document processing capabilities.
        """
        if not self.api_key:
            return "Error: API key not configured"
            
        try:
            # Read the PDF file as binary data
            with open(pdf_path, "rb") as pdf_file:
                pdf_data = pdf_file.read()
            
            # Send the PDF directly to Gemini
            response = self.client.models.generate_content(
                model="gemini-2.0-flash",  # Using 1.5-flash for better document handling
                contents=[
                    types.Part.from_bytes(
                        data=pdf_data,
                        mime_type='application/pdf',
                    ),
                    prompt
                ]
            )
            
            return response.text
        except Exception as e:
            return f"Error processing PDF: {str(e)}"