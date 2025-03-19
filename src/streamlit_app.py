import os
import re
import streamlit as st
import uuid
from typing import Dict, List, Tuple, Optional, Any, Callable
from dataclasses import dataclass, asdict
from functools import wraps
from utils.YoutubeClient import YoutubeClient
from utils.Formatter import VideoFormatter
from llm.GeminiClient import GeminiClient

# --- DATA MODELS ---

@dataclass
class ChatMessage:
    """Data model representing a single chat message"""
    role: str
    content: str
    youtube_included: bool = False
    youtube_count: int = 0


# --- UTILITIES ---

def pluralize(count: int, singular: str, plural: str = None) -> str:
    """Return singular or plural form based on count"""
    if count == 1:
        return singular
    return plural or f"{singular}s"


def handle_exceptions(default_return=None, log_error=True):
    """Decorator for consistent exception handling"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                error_msg = f"Error in {func.__name__}: {str(e)}"
                if log_error:
                    print(error_msg)  # Consider using proper logging
                return default_return
        return wrapper
    return decorator


# --- SERVICES ---

class ChatService:
    """Business logic for chat operations"""
    
    @staticmethod
    def initialize_session() -> None:
        """Initialize chat session if needed"""
        if "chats" not in st.session_state:
            default_id = str(uuid.uuid4())
            st.session_state.chats = {
                default_id: {
                    "name": "Chat 1",
                    "messages": []
                }
            }
            st.session_state.current_chat_id = default_id
            st.session_state.chat_counter = 1
    
    @staticmethod
    def create_chat() -> str:
        """Create a new chat and return its ID"""
        chat_id = str(uuid.uuid4())
        st.session_state.chat_counter += 1
        
        st.session_state.chats[chat_id] = {
            "name": f"Chat {st.session_state.chat_counter}",
            "messages": []
        }
        st.session_state.current_chat_id = chat_id
        
        # Create a new Gemini chat session
        AIService.create_new_chat_session()
        
        return chat_id
    
    @staticmethod
    def delete_chat(chat_id: str) -> Optional[str]:
        """Delete a chat and return new current chat ID if needed"""
        if len(st.session_state.chats) <= 1:
            return None
            
        is_current = chat_id == st.session_state.current_chat_id
        del st.session_state.chats[chat_id]
        
        if is_current:
            new_current_id = next(iter(st.session_state.chats.keys()))
            st.session_state.current_chat_id = new_current_id
            return new_current_id
        
        return None
    
    @staticmethod
    def rename_chat(chat_id: str, new_name: str) -> bool:
        """Rename a chat, returns success"""
        if chat_id in st.session_state.chats:
            st.session_state.chats[chat_id]["name"] = new_name
            return True
        return False
    
    @staticmethod
    def add_message(message: ChatMessage) -> None:
        """Add a message to the current chat"""
        st.session_state.chats[st.session_state.current_chat_id]["messages"].append(asdict(message))
    
    @staticmethod
    def get_current_chat() -> Dict:
        """Get the currently active chat"""
        return st.session_state.chats[st.session_state.current_chat_id]
    
    @staticmethod
    def get_all_chats() -> Dict[str, Dict]:
        """Get all available chats"""
        return st.session_state.chats


class YouTubeService:
    """Business logic for YouTube operations"""
    
    YOUTUBE_PATTERN = r'(https?://)?(www\.)?(youtube\.com|youtu\.be)/[\w\-?=&./%#]*'
    
    @staticmethod
    def extract_links(text: str) -> List[str]:
        """Extract YouTube links from text"""
        matches = list(re.finditer(YouTubeService.YOUTUBE_PATTERN, text))
        return [match.group(0) for match in matches]
    
    @staticmethod
    @handle_exceptions(default_return=([], 0))
    def process_videos(urls: List[str], status_callback: Callable = None) -> Tuple[List[str], int]:
        """Process YouTube videos and return XML content and count"""
        if not urls:
            return [], 0
            
        all_xml_results = []
        video_count = 0
        
        db_conn = os.environ.get("NEON_YOUTUBE_DATABASE_URL")
        client = YoutubeClient(
            use_database=bool(db_conn), 
            db_connection_string=db_conn
        )
        
        # Process each URL
        for i, url in enumerate(urls):
            if status_callback:
                status_callback(f"Processing link {i+1}/{len(urls)}: {url}")
            
            try:
                response = client.fetch_content(url)
                if response.success and response.data:
                    xml_results = [VideoFormatter.to_xml(video) for video in response.data]
                    all_xml_results.extend(xml_results)
                    video_count += len(response.data)
            except Exception as e:
                if status_callback:
                    status_callback(f"Error processing {url}: {str(e)}", "error")
        
        return all_xml_results, video_count


class AIService:
    """Business logic for AI operations"""
    
    @staticmethod
    @st.cache_resource
    def get_client() -> GeminiClient:
        """Initialize and cache Gemini client"""
        return GeminiClient()
    
    @staticmethod
    def create_new_chat_session() -> None:
        """Create a new Gemini chat session"""
        AIService.get_client().create_chat()
    
    @staticmethod
    def process_message(prompt: str, youtube_content: List[str], video_count: int) -> str:
        """Prepare the full message for AI processing"""
        if not youtube_content:
            return prompt
            
        message = f"{prompt}\n\nYouTube Content ({video_count} {pluralize(video_count, 'video')}):\n"
        
        # Add each video content with a clear separator
        for i, content in enumerate(youtube_content):
            if i > 0:
                message += "\n\n--- NEXT VIDEO ---\n\n"
            message += content
        
        return message
    
    @staticmethod
    @handle_exceptions(default_return="Error processing request")
    def generate_response(message: str, chunk_callback: Callable = None) -> str:
        """Generate AI response with streaming"""
        client = AIService.get_client()
        full_response = ""
        
        for chunk in client.send_message_stream(message):
            if hasattr(chunk, 'text') and chunk.text:
                full_response += chunk.text
                if chunk_callback:
                    chunk_callback(full_response)
        
        return full_response


# --- UI COMPONENTS ---

class ChatUI:
    """UI components for chat display and interactions"""
    
    @staticmethod
    def render_sidebar() -> None:
        """Render the sidebar with chat management controls"""
        with st.sidebar:
            st.subheader("💬 Chat Management")
            
            # New chat button
            if st.button("New Chat", use_container_width=True):
                ChatService.create_chat()
                st.rerun()
            
            st.divider()
            
            # Chat list
            chats = ChatService.get_all_chats()
            current_id = st.session_state.current_chat_id
            
            for chat_id, chat in chats.items():
                ChatUI._render_chat_item(chat_id, chat, current_id == chat_id)
    
    @staticmethod
    def _render_chat_item(chat_id: str, chat: Dict, is_current: bool) -> None:
        """Render a single chat item in the sidebar"""
        chat_name = chat.get("name", "Untitled")
        is_renaming = st.session_state.get(f"renaming_{chat_id}", False)
        
        # Chat name or rename field
        if is_renaming:
            ChatUI._render_rename_field(chat_id, chat_name)
        else:
            ChatUI._render_chat_selector(chat_id, chat_name, is_current)
        
        # Action buttons in a single row
        ChatUI._render_chat_actions(chat_id, is_renaming)
        
        st.divider()
    
    @staticmethod
    def _render_rename_field(chat_id: str, current_name: str) -> None:
        """Render the rename input field for a chat"""
        new_name = st.text_input(
            "Chat name", 
            value=current_name, 
            key=f"new_name_{chat_id}", 
            label_visibility="collapsed"
        )
        if new_name != current_name:
            ChatService.rename_chat(chat_id, new_name)
            st.session_state[f"renaming_{chat_id}"] = False
            st.rerun()
    
    @staticmethod
    def _render_chat_selector(chat_id: str, chat_name: str, is_current: bool) -> None:
        """Render a selectable chat button"""
        button_style = "primary" if is_current else "secondary"
        if st.button(
            chat_name, 
            key=f"select_{chat_id}", 
            use_container_width=True, 
            type=button_style
        ):
            st.session_state.current_chat_id = chat_id
            st.rerun()
    
    @staticmethod
    def _render_chat_actions(chat_id: str, is_renaming: bool) -> None:
        """Render action buttons for a chat"""
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Edit", key=f"rename_{chat_id}", 
                      disabled=is_renaming, use_container_width=True):
                st.session_state[f"renaming_{chat_id}"] = True
                st.rerun()
        
        with col2:
            if st.button("Delete", key=f"delete_{chat_id}", 
                      disabled=len(st.session_state.chats) <= 1,
                      use_container_width=True):
                ChatService.delete_chat(chat_id)
                st.rerun()
    
    @staticmethod
    def render_chat_history(messages: List[Dict[str, Any]]) -> None:
        """Render the chat message history"""
        for msg in messages:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])
                if msg.get("youtube_included"):
                    video_count = msg.get("youtube_count", 0)
                    if video_count > 0:
                        st.caption(f"🎬 {video_count} YouTube {pluralize(video_count, 'video')} included")
                    else:
                        st.caption("🎬 YouTube content included")
    
    @staticmethod
    def render_user_input() -> None:
        """Render and process user input field"""
        if prompt := st.chat_input("Ask something..."):
            ChatUI._process_user_message(prompt)
    
    @staticmethod
    def _process_user_message(prompt: str) -> None:
        """Process a user message and generate AI response"""
        # Extract YouTube links
        links = YouTubeService.extract_links(prompt)
        
        # Process YouTube content if links found
        youtube_content, video_count = [], 0
        if links:
            youtube_content, video_count = ChatUI._process_youtube_links(links)
        
        # Add user message
        has_youtube = video_count > 0
        ChatService.add_message(ChatMessage("user", prompt, has_youtube, video_count))
        
        # Display user message
        with st.chat_message("user"):
            st.markdown(prompt)
            if has_youtube:
                st.caption(f"🎬 {video_count} YouTube {pluralize(video_count, 'video')} included")
        
        # Generate AI response
        full_message = AIService.process_message(prompt, youtube_content, video_count)
        ChatUI._generate_ai_response(full_message)
    
    @staticmethod
    def _process_youtube_links(links: List[str]) -> Tuple[List[str], int]:
        """Process YouTube links with status indicator"""
        with st.status(f"📥 Processing {len(links)} YouTube links...", expanded=True) as status:
            def update_status(message, state=None):
                kwargs = {"expanded": True}
                if state:
                    kwargs["state"] = state
                status.update(label=message, **kwargs)
            
            youtube_content, video_count = YouTubeService.process_videos(links, update_status)
            
            if video_count > 0:
                update_status(
                    f"✅ Found {video_count} {pluralize(video_count, 'video')} from {len(links)} links", 
                    "complete"
                )  
            else:
                update_status("⚠️ No video content could be retrieved", "error")
            
            return youtube_content, video_count
    
    @staticmethod
    def _generate_ai_response(message: str) -> None:
        """Generate and display AI response"""
        with st.chat_message("assistant"):
            message_placeholder = st.empty()
            
            def update_response(text, is_error=False):
                if is_error:
                    message_placeholder.error(text)
                else:
                    message_placeholder.markdown(text)
            
            response = AIService.generate_response(message, update_response)
            
            # Save final response
            ChatService.add_message(ChatMessage("assistant", response))


# --- MAIN APPLICATION ---

def main():
    """Main application entry point"""
    st.set_page_config(
        page_title="Talk with Transcript", 
        page_icon="💬", 
        layout="wide"
    )
    
    # Initialize app state
    ChatService.initialize_session()
    current_chat = ChatService.get_current_chat()
    
    # Render UI
    ChatUI.render_sidebar()
    st.title(current_chat['name'])
    ChatUI.render_chat_history(current_chat["messages"])
    ChatUI.render_user_input()


if __name__ == "__main__":
    main()