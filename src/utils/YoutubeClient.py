from typing import Dict, Any, List, Optional
import re
import requests
import html  # Add this to the imports at the top
from pytube import Playlist
from youtube_transcript_api import  YouTubeTranscriptApi
from .ApiResponse import ApiResponse


class Video:
    """Structured representation of YouTube video data with optional transcript"""
    
    def __init__(
        self,
        id: str,
        title: str,
        channel: str,
        published_date: str,
        view_count: str,
        url: str,
        description: str = "",
        transcript: Optional[str] = None
    ):
        self.id = id
        self.title = title
        self.channel = channel
        self.published_date = published_date
        self.view_count = view_count
        self.url = url
        self.description = description
        self.transcript = transcript
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert video object to dictionary representation"""
        result = {
            "id": self.id,
            "title": self.title,
            "channel": self.channel,
            "published_date": self.published_date,
            "view_count": self.view_count,
            "url": self.url,
            "description": self.description
        }
        if self.transcript:
            result["transcript"] = self.transcript
        return result


class YoutubeClient:
    """Client for fetching YouTube video metadata and transcripts"""
    
    HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    
    def __init__(self):
        self.transcript_api = YouTubeTranscriptApi()
    
    def get_video(self, video_url: str) -> ApiResponse[Video]:
        """Fetch metadata for a YouTube video"""
        try:
            video_id = self._extract_video_id(video_url)
            metadata = self._fetch_metadata(video_id)
            
            video = Video(
                id=video_id,
                title=metadata.get("title", "Unknown"),
                channel=metadata.get("channel", "Unknown"),
                published_date=metadata.get("published_date", "Unknown"),
                view_count=metadata.get("view_count", "0"),
                url=f"https://www.youtube.com/watch?v={video_id}",
                description=metadata.get("description", "")
            )
            
            return ApiResponse(success=True, data=video)
        except Exception as e:
            return ApiResponse(
                success=False, 
                error=f"Failed to retrieve video: {str(e)}",
                error_code="video_retrieval_error"
            )
    
    def get_video_with_transcript(self, video_url: str) -> ApiResponse[Video]:
        """Fetch both metadata and transcript for a YouTube video"""
        try:
            video_response = self.get_video(video_url)
            if not video_response.success:
                return video_response
                
            video = video_response.data
            transcript_response = self.get_transcript(video.id)
            
            if transcript_response.success:
                video.transcript = transcript_response.data
                
            return ApiResponse(success=True, data=video)
        except Exception as e:
            return ApiResponse(
                success=False,
                error=f"Failed to retrieve video with transcript: {str(e)}",
                error_code="video_transcript_error"
            )
    
    def get_transcript(self, video_id: str) -> ApiResponse[str]:
        """Fetch transcript for a YouTube video by ID"""
        try:
            transcript_list = self.transcript_api.get_transcript(video_id)
            transcript_text = " ".join([item["text"] for item in transcript_list])
            return ApiResponse(success=True, data=transcript_text)
        except Exception as e:
            return ApiResponse(
                success=False,
                error=f"Failed to retrieve transcript: {str(e)}",
                error_code="transcript_retrieval_error"
            )
    
    def list_playlist_videos(self, playlist_url: str, include_transcripts: bool = False) -> ApiResponse[List[Video]]:
        """Fetch all videos from a YouTube playlist with optional transcripts"""
        try:
            playlist = Playlist(playlist_url)
            videos = []
            
            for video_url in playlist.video_urls:
                method = self.get_video_with_transcript if include_transcripts else self.get_video
                video_response = method(video_url)
                    
                if video_response.success:
                    videos.append(video_response.data)
            
            return ApiResponse(success=True, data=videos)
        except Exception as e:
            return ApiResponse(
                success=False,
                error=f"Failed to retrieve playlist videos: {str(e)}",
                error_code="playlist_retrieval_error"
            )
    
    def _extract_video_id(self, video_url: str) -> str:
        """Extract video ID from URL using regex pattern matching"""
        # Handle case where input might already be an ID (11 characters with specific allowed chars)
        if re.match(r'^[0-9A-Za-z_-]{11}$', video_url):
            return video_url
            
        # Pattern matches standard YouTube URL formats
        patterns = [
            r'(?:v=|\/embed\/|\/shorts\/|youtu\.be\/)([0-9A-Za-z_-]{11})',  # Matches most formats including shorts
        ]
        
        for pattern in patterns:
            match = re.search(pattern, video_url)
            if match:
                return match.group(1)
                
        # If no match was found, return original (might be an error)
        raise ValueError(f"Could not extract video ID from URL: {video_url}")
    
    def _fetch_metadata(self, video_id: str) -> Dict[str, Any]:
        """Scrape metadata for a video from YouTube page HTML"""
        url = f"https://www.youtube.com/watch?v={video_id}"
        response = requests.get(url, headers=self.HEADERS).text
        
        # Extract metadata and decode HTML entities
        title = self._extract_regex(response, r'<meta name="title" content="([^"]*)"') or "Unknown"
        channel = self._extract_regex(response, r'"ownerChannelName":"([^"]*)"') or "Unknown"
        published_date = self._extract_regex(response, r'"publishDate":"([^"]*)"') or "Unknown"
        view_count = self._extract_regex(response, r'"viewCount":"([^"]*)"') or "0"
        
        # Try different patterns for description
        description = (
            self._extract_regex(response, r'<meta name="description" content="([^"]*)"')
            or self._extract_regex(response, r'"shortDescription":"(.*?)"(?=,)')
            or self._extract_regex(response, r'"description":{"simpleText":"(.*?)"(?=})')
            or ""
        )
        
        # Decode HTML entities
        return {
            "title": html.unescape(title),
            "channel": html.unescape(channel),
            "published_date": published_date,
            "view_count": view_count,
            "description": html.unescape(description)
        }
    
    def _extract_regex(self, text: str, pattern: str) -> Optional[str]:
        """Extract first match from text using regex pattern"""
        match = re.search(pattern, text)
        return match.group(1) if match else None