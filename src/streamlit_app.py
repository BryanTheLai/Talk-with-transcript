import os
import re
import streamlit as st
from typing import Dict, List, Any, Callable, Tuple
from dataclasses import dataclass, asdict
from llm.GeminiClient import GeminiClient
from utils.YoutubeClient import YoutubeClient
from utils.Formatter import VideoFormatter

# --- DATA MODELS ---
@dataclass
class ChatMessage:
    """Represents a single chat message"""
    role: str
    content: str
    has_external_content: bool = False
    content_count: int = 0
    content_type: str = ""

# --- CONTENT PROVIDER ---
class ContentProvider:
    """Base interface for content providers"""
    
    def can_process(self, text: str) -> bool:
        """Check if this provider can process the given text"""
        return False
        
    def extract_references(self, text: str) -> List[str]:
        """Extract content references from text"""
        return []
    
    def process_content(self, references: List[str], status_callback: Callable = None) -> Tuple[List[str], int]:
        """Process content from references and return formatted results"""
        return [], 0
    
    def format_prompt(self, original_prompt: str, content_results: List[str], count: int) -> str:
        """Format the prompt with content results"""
        return original_prompt

class YouTubeProvider(ContentProvider):
    """YouTube content provider"""
    
    URL_PATTERN = r'(https?://)?(www\.)?(youtube\.com|youtu\.be)/[\w\-?=&./%#]*'
    
    def can_process(self, text: str) -> bool:
        return bool(re.search(self.URL_PATTERN, text))
    
    def extract_references(self, text: str) -> List[str]:
        return [match.group(0) for match in re.finditer(self.URL_PATTERN, text)]
    
    def process_content(self, urls: List[str], status_callback: Callable = None) -> Tuple[List[str], int]:
        if not urls:
            return [], 0
            
        try:
            results = []
            video_count = 0
            
            client = YoutubeClient(
                use_database=bool(os.environ.get("NEON_YOUTUBE_DATABASE_URL")), 
                db_connection_string=os.environ.get("NEON_YOUTUBE_DATABASE_URL")
            )
            
            for i, url in enumerate(urls):
                if status_callback:
                    status_callback(f"Processing link {i+1}/{len(urls)}")
                
                response = client.fetch_content(url)
                if response.success and response.data:
                    xml_results = [VideoFormatter.to_xml(video) for video in response.data]
                    results.extend(xml_results)
                    video_count += len(response.data)
            
            return results, video_count
        except Exception as e:
            print(f"Error processing videos: {str(e)}")
            return [], 0
    
    def format_prompt(self, original_prompt: str, content_results: List[str], count: int) -> str:
        if not content_results:
            return original_prompt
            
        plural = "video" if count == 1 else "videos"
        message = f"{original_prompt}\n\nYouTube Content ({count} {plural}):\n"
        
        for i, content in enumerate(content_results):
            if i > 0:
                message += "\n\n--- NEXT VIDEO ---\n\n"
            message += content
        return message

# --- CORE CHAT APP ---
class ChatApp:
    """Core chat functionality"""
    
    def __init__(self):
        if "messages" not in st.session_state:
            st.session_state.messages = []
            
        self.ai_client = self.get_ai_client()
        self.content_providers = []
    
    @st.cache_resource
    def get_ai_client(_self):
        """Initialize AI client"""
        return GeminiClient()
    
    def add_provider(self, provider: ContentProvider):
        """Add a content provider to the app"""
        self.content_providers.append(provider)
    
    def generate_response(self, message: str, update_callback=None):
        """Generate AI response with streaming"""
        try:
            full_response = ""
            for chunk in self.ai_client.send_message_stream(message):
                if hasattr(chunk, 'text') and chunk.text:
                    full_response += chunk.text
                    if update_callback:
                        update_callback(full_response)
            return full_response
        except Exception as e:
            error_msg = f"Error generating response: {str(e)}"
            if update_callback:
                update_callback(error_msg, True)
            return error_msg
    
    def process_message(self, message: str, status_callback=None) -> Tuple[str, bool, int, str]:
        """Process message with content providers"""
        for provider in self.content_providers:
            if provider.can_process(message):
                references = provider.extract_references(message)
                if references:
                    results, count = provider.process_content(references, status_callback)
                    if count > 0:
                        return (
                            provider.format_prompt(message, results, count),
                            True,
                            count,
                            provider.__class__.__name__.replace("Provider", "")
                        )
        
        return message, False, 0, ""

# --- UI CLASS ---
class ChatUI:
    """Chat UI components"""
    
    def __init__(self, app: ChatApp):
        self.app = app
    
    def render_chat_history(self):
        """Display chat history"""
        for msg in st.session_state.messages:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])
                if msg.get("has_external_content") and msg.get("content_count", 0) > 0:
                    count = msg.get("content_count", 0)
                    content_type = msg.get("content_type", "")
                    plural = f"{content_type.lower()}" if count == 1 else f"{content_type.lower()}s"
                    st.caption(f"🔗 {count} {plural} included")
    
    def handle_user_input(self):
        """Process user input and generate response"""
        if prompt := st.chat_input("Ask something..."):
            # Process and display user message
            with st.status("Processing message...", expanded=True) as status:
                enriched_prompt, has_content, content_count, content_type = self.app.process_message(
                    prompt,
                    lambda msg: status.update(label=msg, expanded=True)
                )
                
                if has_content:
                    status.update(label=f"Found {content_count} {content_type.lower()} content items", state="complete")
                else:
                    status.update(label="Processing complete", state="complete")
            
            # Save and display user message
            user_msg = {
                "role": "user", 
                "content": prompt, 
                "has_external_content": has_content, 
                "content_count": content_count,
                "content_type": content_type
            }
            st.session_state.messages.append(user_msg)
            
            with st.chat_message("user"):
                st.markdown(prompt)
                if has_content:
                    plural = content_type.lower() if content_count == 1 else f"{content_type.lower()}s"
                    st.caption(f"🔗 {content_count} {plural} included")
            
            # Generate and display AI response
            with st.chat_message("assistant"):
                message_placeholder = st.empty()
                
                def update_response(text, is_error=False):
                    if is_error:
                        message_placeholder.error(text)
                    else:
                        message_placeholder.markdown(text)
                
                response = self.app.generate_response(enriched_prompt, update_response)
                
                # Save assistant message
                assistant_msg = {
                    "role": "assistant", 
                    "content": response
                }
                st.session_state.messages.append(assistant_msg)
    
    def reset_chat(self):
        """Clear all chat messages"""
        st.session_state.messages = []
        self.app.ai_client.create_chat()

# --- MAIN APPLICATION ---
def main():
    """Main application"""
    st.set_page_config(page_title="Talk with Transcript", page_icon="💬")
    st.title("Talk with Transcript 💬")
    
    # Initialize app
    app = ChatApp()
    app.add_provider(YouTubeProvider())
    ui = ChatUI(app)
    
    # Render interface
    if st.button("Reset Chat"):
        ui.reset_chat()
        st.rerun()
        
    ui.render_chat_history()
    ui.handle_user_input()

if __name__ == "__main__":
    main()