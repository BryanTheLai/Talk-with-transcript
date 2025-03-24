import os
import time
import streamlit as st
from utils.YoutubeClient import YoutubeClient
from utils.Formatter import VideoFormatter
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

def fetch_youtube_content(url: str) -> list[str]:
    """Fetch YouTube content and return formatted XML"""
    # Setup client with database if available
    db_url = os.environ.get("NEON_YOUTUBE_DATABASE_URL")
    
    # # Configure proxy from environment variables
    # proxy_domain = os.environ.get('BRIGHTDATA_DOMAIN_NAME')
    # proxy_port = os.environ.get('BRIGHTDATA_PROXY_PORT')
    # proxy_username = os.environ.get('BRIGHTDATA_PROXY_USERNAME')
    # proxy_password = os.environ.get('BRIGHTDATA_PROXY_PASSWORD')

    # proxy_url = None
    # if all([proxy_domain, proxy_port, proxy_username, proxy_password]):
    #     # Create a proxy string in the format expected by YoutubeClient
    #     proxy_url = f"{proxy_username}:{proxy_password}@{proxy_domain}:{proxy_port}"
    #     print(f"Using proxy: {proxy_domain}:{proxy_port}")
    # else:
    #     print("Proxy configuration incomplete - using direct connection")
    
    # Initialize YouTube client with database and proxy
    client = YoutubeClient(
        use_database=bool(db_url), 
        db_connection_string=db_url,
        #proxy_url=proxy_url
    )
    
    # Fetch and format content
    start_time = time.time()
    response = client.fetch_content(url)
    if response.error:
        print(f"Error: {response.error}")
    fetch_time = round(time.time() - start_time, 2)
    
    # Return results and timing
    xml_results = [VideoFormatter.to_xml(video) for video in response.data] if response.success else []
    return xml_results, fetch_time


def main():
    st.title("YouTube to XML Converter")
    
    url = st.text_input("Enter YouTube URL (video or playlist)")
    
    if st.button("Get XML"):
        if not url:
            st.warning("Please enter a YouTube URL")
            return
            
        with st.spinner("Fetching content..."):
            xml_results, fetch_time = fetch_youtube_content(url)
        
        if xml_results:
            st.info(f"⏱️ Fetch time: {fetch_time}s")
            
            for i, xml in enumerate(xml_results):
                st.subheader(f"Video {i+1}")
                st.code(xml, language="xml")

        else:
            st.error("No content found or error occurred")

if __name__ == "__main__":
    main()