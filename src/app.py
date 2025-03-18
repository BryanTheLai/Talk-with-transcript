import os
import time
import streamlit as st
from utils.YoutubeClient import YoutubeClient
from utils.Formatter import VideoFormatter

def fetch_youtube_content(url: str) -> tuple[list[str], dict]:
    """Fetch YouTube content and return formatted XML with timing metrics"""
    start = time.time()
    metrics = {'start': start}
    
    # Setup client
    db_connection_string = os.environ.get("NEON_YOUTUBE_DATABASE_URL")
    client = YoutubeClient(use_database=bool(db_connection_string), 
                          db_connection_string=db_connection_string)
    
    # Fetch content
    metrics['fetch_start'] = time.time()
    response = client.fetch_content(url)
    metrics['fetch_end'] = time.time()
    
    # Format to XML
    xml_results = [VideoFormatter.to_xml(video) for video in response.data] if response.success else []
    metrics['fetch_seconds'] = round(metrics['fetch_end'] - metrics['fetch_start'], 2)
    
    return xml_results, metrics

def main():
    st.title("YouTube to XML Converter")
    
    url = st.text_input("Enter YouTube URL (video or playlist)")
    submit_button = st.button("Get XML")
    
    if submit_button:
        if url:
            with st.spinner("Fetching content..."):
                xml_results, metrics = fetch_youtube_content(url)
            
            if xml_results:
                st.info(f"⏱️ Fetch: {metrics['fetch_seconds']}s")
                
                for i, xml in enumerate(xml_results):
                    st.subheader(f"Video {i+1}")
                    st.code(xml, language="xml")
            else:
                st.error("No content found or error occurred")
        else:
            st.warning("Please enter a YouTube URL")

if __name__ == "__main__":
    main()