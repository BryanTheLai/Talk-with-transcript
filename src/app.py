from typing import Dict, List
from utils.YoutubeHandler import YoutubeHandler
from llm.GeminiClient import GeminiClient



def process_url(url: str) -> List[str]:
    """Process YouTube URL (either video or playlist) and return transcripts."""
    youtube_api = YoutubeHandler()
    if "playlist" in url:
        # Handle playlist
        video_urls = youtube_api.get_playlist_video_links(url)
        return [youtube_api.get_video_transcript(video_url)["result"] for video_url in video_urls]
    else:
        # Handle single video
        return [youtube_api.get_video_transcript(url)["result"]]

def main():
    # Change this URL to any YouTube video or playlist URL
    video_url = "https://www.youtube.com/watch?v=K5Mw4zto2Zc"
    playlist_url = "https://www.youtube.com/playlist?list=PLMV8UXQuOWKOY5fl1ccuMvDYjXwqRA69j"
    transcripts = process_url(video_url)
    print(transcripts)
    
    # gemini = GeminiClient()
    # response = gemini.process_transcripts(transcripts, model="gemini-2.0-flash-lite")
    # print(response.text)

if __name__ == "__main__":
    main()