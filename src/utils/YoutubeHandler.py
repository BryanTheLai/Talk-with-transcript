from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api.proxies import WebshareProxyConfig
from pytube import YouTube, Playlist
from typing import Dict, List, Optional
import os
from dotenv import load_dotenv

class YoutubeHandler:
    def __init__(self):
        load_dotenv()
        proxy_config = None
        
        username = os.getenv("PROXY_USERNAME")
        password = os.getenv("PROXY_PASSWORD")
        if username and password:
            proxy_config = WebshareProxyConfig(
                proxy_username=username,
                proxy_password=password,
            )
        
        self.ytt_api = YouTubeTranscriptApi(proxy_config=proxy_config)

    def get_video_transcript(self, video_url: str) -> Dict[str, str]:
        """Get transcript text from a YouTube video URL."""
        try:
            yt = YouTube(video_url)
            video_id = yt.video_id
            transcript_response = self.ytt_api.get_transcript(video_id)
            transcript_text = "".join([segment['text'] for segment in transcript_response])
            result = f"<YOUTUBE_VIDEO>{transcript_text.strip()}<YOUTUBE_VIDEO/>"
            return {"result": result}
        except Exception as e:
            return {"error": str(e)}

    def get_playlist_video_links(self, playlist_url: str) -> List[str]:
        """Get all video URLs from a YouTube playlist."""
        playlist = Playlist(playlist_url)
        return playlist.video_urls