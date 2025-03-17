import streamlit as st
from utils.YoutubeClient import YoutubeClient
from utils.Formatter import VideoFormatter

# Set page title
st.title("YouTube to XML")

# Simple input field
url = st.text_input("Paste YouTube URL:")

# Process button
if st.button("Get XML") and url:
    # Show loading state
    with st.spinner("Processing..."):
        # Initialize YouTube client
        youtube = YoutubeClient()
        
        # Get video with transcript
        response = youtube.get_video_with_transcript(url)
        
        # Check if successful
        if response.success:
            # Get video data and format as XML
            video = response.data
            xml = VideoFormatter.to_xml(video)
            
            # Display XML in a code block
            st.code(xml, language="xml")
        else:
            # Show error message
            st.error(f"Error: {response.error}")