from utils.YoutubeClient import YoutubeClient
from utils.Formatter import VideoFormatter

def fetch_youtube_content(url: str, include_transcripts: bool = True) -> list[str]:
    """
    Fetch content from YouTube URL and convert to XML format
    
    Args:
        url: YouTube video or playlist URL
        include_transcripts: Whether to include transcripts in the results
        
    Returns:
        List of videos in XML format
    """
    youtube = YoutubeClient()
    response = youtube.fetch_content(url, include_transcripts)
    
    if response.success:
        return [VideoFormatter.to_xml(video) for video in response.data]
    return []

def main():
    # Example usage
    url = "https://www.youtube.com/watch?v=scuPf6CMLtI"  # Single video
    url = "https://www.youtube.com/watch?v=scuPf6CMLtI&list=PLkPSXEe30ibqeQFm8dqNy0uxOL2W2wuN_"  # Playlist
    
    xml_results = fetch_youtube_content(url)
    
    # Print or process results
    for i, xml in enumerate(xml_results):
        print(f"Video {i+1} XML:")
        print(xml)
        print("-" * 80)

if __name__ == "__main__":
    main()