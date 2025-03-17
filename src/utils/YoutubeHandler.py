from youtube_transcript_api import YouTubeTranscriptApi
from pytube import YouTube, Playlist
from typing import Dict, Any, List
import re
import requests
from dotenv import load_dotenv

class YoutubeHandler:
    def __init__(self):
        load_dotenv()
        self.headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        self.transcript_api = YouTubeTranscriptApi()
    
    def process_url(self, url: str) -> List[Dict]:
        """Process YouTube URL (either video or playlist) and return transcripts."""
        if "playlist" in url:
            video_urls = self.get_playlist_video_ids(url)
            return [self.get_video_details(video_url) for video_url in video_urls]
        else:
            return [self.get_video_details(url)]
    
    def get_transcript(self, video_id: str) -> Dict[str, Any]:
        """Get transcript from YouTube video ID."""
        transcript = self.transcript_api.fetch(video_id, preserve_formatting=True)
        text = " ".join([segment.text for segment in transcript])
        return {"success": True, "text": text, "video_id": video_id}
            
    def get_metadata(self, video_id: str) -> Dict[str, Any]:
        """Get video metadata from video ID."""
        url = f"https://www.youtube.com/watch?v={video_id}"
        html = requests.get(url, headers=self.headers).text
        return {
            "success": True,
            "id": video_id,
            "title": self._extract(html, r'<meta name="title" content="([^"]*)"') or "Unknown",
            "channel": self._extract(html, r'"ownerChannelName":"([^"]*)"') or "Unknown",
            "date": self._extract(html, r'"publishDate":"([^"]*)"') or "Unknown",
            "views": self._extract(html, r'"viewCount":"([^"]*)"') or "0",
            "url": url
        }
    
    def get_video_details(self, video_url: str) -> Dict[str, Any]:
        """Get complete video details (transcript + metadata)."""
        video_id = YouTube(video_url).video_id
        transcript = self.get_transcript(video_id)
        metadata = self.get_metadata(video_id)
        
        if not transcript["success"] or not metadata["success"]:
            return {"success": False, "error": "Failed to get transcript or metadata"}
        
        return {
            "success": True,
            "id": video_id,
            "title": metadata["title"],
            "channel": metadata["channel"],
            "date": metadata["date"],
            "views": metadata["views"],
            "url": metadata["url"],
            "transcript": transcript["text"]
        }
    
    def get_playlist_video_ids(self, playlist_url: str) -> List[str]:
        """Get all video IDs from playlist."""
        videos = Playlist(playlist_url).video_urls
        return [url for url in videos]
            
    def _extract(self, html: str, pattern: str) -> str:
        """Extract info using regex."""
        match = re.search(pattern, html)
        return match.group(1) if match else None