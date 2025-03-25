import os
import time
from typing import Tuple, List, Optional
import streamlit as st
from utils.YoutubeClient import YoutubeClient
from utils.Formatter import VideoFormatter
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

def fetch_youtube_content(url: str) -> Tuple[List[str], float, Optional[str]]:
    """
    Fetch YouTube content and return formatted XML
    
    Args:
        url: YouTube video or playlist URL
        
    Returns:
        Tuple containing:
            - List of XML formatted video content
            - Processing time in seconds
            - Error message (or None if successful)
    """
    # Setup client with database if available
    db_url = os.environ.get("NEON_YOUTUBE_DATABASE_URL")
    
    try:
        # Initialize YouTube client with database
        client = YoutubeClient(
            use_database=bool(db_url), 
            db_connection_string=db_url,
        )
        
        # Fetch and format content
        start_time = time.time()
        response = client.fetch_content(url)
        fetch_time = round(time.time() - start_time, 2)
        
        if not response.success:
            error_message = response.error or "Unknown error occurred"
            return [], fetch_time, error_message
            
        # Format results as XML
        xml_results = [VideoFormatter.to_xml(video) for video in response.data] if response.data else []
        return xml_results, fetch_time, None
        
    except Exception as e:
        return [], 0, f"Application error: {str(e)}"

def render_videos(xml_results: List[str]) -> None:
    """Render video XML results in the Streamlit UI"""
    for i, xml in enumerate(xml_results):
        st.subheader(f"Video {i+1}")
        st.code(xml, language="xml")

def main():
    """Main application entry point"""
    # Configure the page
    st.set_page_config(
        page_title="YouTube to XML Converter",
        page_icon="🎥",
        layout="wide"
    )
    
    # App header
    st.title("🎥 YouTube to XML Converter")
    st.markdown("""
        Extract video data and transcripts from YouTube videos and playlists.
        Simply paste a YouTube URL below and click "Get XML".
    """)
    
    # Input section
    with st.container():
        url = st.text_input("Enter YouTube URL (video or playlist)", key="url_input")
        col1, col2 = st.columns([1, 5])
        with col1:
            process_button = st.button("Get XML", type="primary", use_container_width=True)
    
    # Processing section
    if process_button:
        if not url:
            st.warning("⚠️ Please enter a YouTube URL")
            return
            
        with st.spinner("Fetching content from YouTube..."):
            xml_results, fetch_time, error = fetch_youtube_content(url)
        
        # Results section
        if xml_results:
            st.success(f"✅ Successfully retrieved {len(xml_results)} videos in {fetch_time} seconds")
            render_videos(xml_results)
        else:
            st.error(f"❌ {error or 'No content found'}")
            
            # Show troubleshooting tips
            with st.expander("Troubleshooting Tips"):
                st.markdown("""
                - Make sure the URL is from YouTube (youtube.com or youtu.be)
                - Check if the video is available in your region
                - Verify the video has English subtitles/captions available
                - For playlists, ensure it's a public playlist
                """)

if __name__ == "__main__":
    main()