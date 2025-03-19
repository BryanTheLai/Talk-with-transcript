import os
import time
import streamlit as st
from utils.YoutubeClient import YoutubeClient
from utils.Formatter import VideoFormatter
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

def fetch_youtube_content(url: str) -> tuple[list[str], dict]:
    """Fetch YouTube content and return formatted XML with timing metrics"""
    start = time.time()
    metrics = {'start': start}
    
    try:
        # Setup client
        db_connection_string = os.environ.get("NEON_YOUTUBE_DATABASE_URL")
        
        # First try with proxy
        webshare_domain = os.environ.get("WEBSHARE_DOMAIN_NAME")
        webshare_port = os.environ.get("WEBSHARE_PROXY_PORT")
        webshare_username = os.environ.get("WEBSHARE_PROXY_USERNAME")
        webshare_password = os.environ.get("WEBSHARE_PROXY_PASSWORD")
        
        # Try with proxy first
        if all([webshare_domain, webshare_port, webshare_username, webshare_password]):
            proxy_url = f"http://{webshare_username}:{webshare_password}@{webshare_domain}:{webshare_port}"
            print(f"Trying with Webshare proxy: {webshare_domain}:{webshare_port}")
            
            client = YoutubeClient(
                use_database=bool(db_connection_string),
                db_connection_string=db_connection_string,
                proxy=proxy_url
            )
            
            # Fetch content with proxy
            metrics['fetch_start'] = time.time()
            response = client.fetch_content(url)
            metrics['fetch_end'] = time.time()
            
            if response.success:
                print("Successfully fetched content using proxy")
                xml_results = [VideoFormatter.to_xml(video) for video in response.data]
                metrics['fetch_seconds'] = round(metrics['fetch_end'] - metrics['fetch_start'], 2)
                metrics['proxy_used'] = True
                return xml_results, metrics
            else:
                print(f"Proxy attempt failed: {response.error}. Trying without proxy...")
        
        # If we get here, either proxy wasn't configured or it failed - try without proxy
        print("Attempting to fetch content without proxy...")
        client = YoutubeClient(
            use_database=bool(db_connection_string),
            db_connection_string=db_connection_string,
            proxy=None
        )
        
        # Fetch content without proxy
        metrics['fetch_start'] = time.time()
        response = client.fetch_content(url)
        metrics['fetch_end'] = time.time()
        
        print(f"Direct connection response success: {response.success}")
        if not response.success:
            print(f"Error from YouTube client: {response.error}, Code: {response.error_code}")
            metrics['error'] = response.error
            return [], metrics
        
        if not response.data or len(response.data) == 0:
            print("No data returned from YouTube client")
            metrics['error'] = "No data returned"
            return [], metrics
            
        # Format to XML
        xml_results = [VideoFormatter.to_xml(video) for video in response.data]
        metrics['fetch_seconds'] = round(metrics['fetch_end'] - metrics['fetch_start'], 2)
        metrics['proxy_used'] = False
        
        return xml_results, metrics
    except Exception as e:
        import traceback
        print(f"Exception in fetch_youtube_content: {str(e)}")
        print(traceback.format_exc())
        metrics['error'] = str(e)
        return [], metrics

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
                if 'error' in metrics:
                    st.error(f"Error details: {metrics['error']}")
        else:
            st.warning("Please enter a YouTube URL")

if __name__ == "__main__":
    main()