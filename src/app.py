import os
from utils.YoutubeClient import YoutubeClient
from utils.Formatter import VideoFormatter

def fetch_youtube_content(url: str) -> list[str]:
    """
    Fetch content from YouTube URL and convert to XML format
    
    Args:
        url: YouTube video or playlist URL
        
    Returns:
        List of videos in XML format with metadata and transcripts
    """
    db_connection_string = os.environ.get("NEON_YOUTUBE_DATABASE_URL")
    client = YoutubeClient(use_database=bool(db_connection_string), 
                          db_connection_string=db_connection_string)
    response = client.fetch_content(url)
    
    return [VideoFormatter.to_xml(video) for video in response.data] if response.success else []

def main():
    import streamlit as st
    st.title("YouTube to XML Converter")
    
    # Show database connection status
    db_url = os.environ.get("NEON_YOUTUBE_DATABASE_URL")
    if db_url:
        st.success("Database connection configured")
    else:
        st.warning("No database connection found. Set NEON_YOUTUBE_DATABASE_URL environment variable for database caching.")
    
    url = st.text_input("Enter YouTube URL (video or playlist)")
    if st.button("Get XML"):
        if not url:
            st.warning("Please enter a YouTube URL")
            return
            
        with st.spinner("Fetching content..."):
            xml_results = fetch_youtube_content(url)
            
        if xml_results:
            for i, xml in enumerate(xml_results):
                st.subheader(f"Video {i+1}")
                st.code(xml, language="xml")
        else:
            st.error("No content found or error occurred")

if __name__ == "__main__":
    main()