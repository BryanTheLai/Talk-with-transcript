from typing import Dict, Any, List, Optional, Union, Tuple
import re
import requests
import html
import logging
import time
import random
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api.proxies import GenericProxyConfig
from .models import ApiResponse, Video
from .DatabaseClient import DatabaseClient

class YoutubeClient:
    """Client for fetching YouTube video metadata and transcripts"""
    
    # URL parsing patterns
    VIDEO_ID_RE = re.compile(r'(?:v=|\/embed\/|\/shorts\/|youtu\.be\/)([0-9A-Za-z_-]{11})')
    PLAYLIST_ID_RE = re.compile(r'(?:list=)([0-9A-Za-z_-]+)')
    PLAYLIST_VIDEO_PATTERN = re.compile(r'(?:"videoId":"([^"]+)"|"videoRenderer":{"videoId":"([^"]+)")')
    
    # Constants
    DEFAULT_LANGUAGES = ['en', 'en-US', 'en-GB']
    YOUTUBE_BASE_URL = "https://www.youtube.com"
    
    DEFAULT_HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
    }
    
    # Metadata extraction patterns with default values
    METADATA_PATTERNS = {
        "title": (r'<meta name="title" content="([^"]*)"', "Unknown"),
        "channel": (r'"ownerChannelName":"([^"]*)"', "Unknown"),
        "published_date": (r'"publishDate":"([^"]*)"', "Unknown"),
        "view_count": (r'"viewCount":"([^"]*)"', "0"),
        "description": (r'"description":{"simpleText":"(.*?)"(?=})', "")
    }
    
    def __init__(
        self,
        timeout: int = 30,
        headers: Optional[Dict[str, str]] = None,
        db_connection_string: Optional[str] = None,
        use_database: bool = True,
        proxy_url: str = None,
    ):
        """Initialize YouTube client with optional proxy and database support"""
        
        # Configure HTTP session
        self.session = requests.Session()
        self.timeout = timeout
        self.session.headers.update(headers or self.DEFAULT_HEADERS)
        
        # Configure database
        self.use_database = use_database and db_connection_string
        self.db_client = None
        if self.use_database:
            try:
                self.db_client = DatabaseClient(db_connection_string)
                self.db_client.connect()
                self.db_client.initialize_schema()
            except Exception as e:
                logging.error(f"Database initialization failed: {e}")
                self.use_database = False
        
        # Default to no proxy
        self.session.proxies = None
        self.transcript_api = YouTubeTranscriptApi()
        
        # Set up proxy if provided
        if proxy_url is not None:
            logging.info(f"Using proxy: {proxy_url}")
            http_proxy = f"http://{proxy_url}"
            https_proxy = f"https://{proxy_url}"
            
            # Apply proxy to requests session
            self.session.proxies = {
                'http': http_proxy,
                'https': https_proxy
            }
            
            # Apply proxy to YouTube Transcript API
            proxy_config = GenericProxyConfig(
                http_url=http_proxy,
                https_url=https_proxy
            )
            self.transcript_api = YouTubeTranscriptApi(proxy_config=proxy_config)
    
    def fetch_content(self, url: str) -> ApiResponse[List[Video]]:
        """Main entry point: Fetch YouTube content (metadata and transcript) from URL"""
        try:
            # Determine if URL is for a playlist or single video
            if self.PLAYLIST_ID_RE.search(url):
                return self._get_playlist_videos(url)
            else:
                video_response = self._get_video(url)
                return ApiResponse(success=True, data=[video_response.data]) if video_response.success else video_response
        except Exception as e:
            return ApiResponse(success=False, error=f"Content fetch error: {str(e)}")

    def _get_video(self, video_url: str) -> ApiResponse[Video]:
        """Fetch complete video data with metadata and transcript"""
        try:
            video_id = self._extract_video_id(video_url)
            
            # Try database cache first
            cached_video = self._get_from_db_cache(video_id)
            if cached_video:
                return ApiResponse(success=True, data=cached_video)
                
            logging.info(f"Fetching video {video_id}")
            
            # Create video object from metadata
            metadata = self._fetch_metadata(video_id)
            video = Video(
                id=video_id,
                title=metadata.get("title", "Unknown"),
                channel=metadata.get("channel", "Unknown"),
                published_date=metadata.get("published_date", "Unknown"),
                view_count=metadata.get("view_count", "0"),
                url=f"{self.YOUTUBE_BASE_URL}/watch?v={video_id}",
                description=metadata.get("description", "")
            )
            
            # Add transcript if available
            transcript_response = self._get_transcript(video_id)
            if transcript_response.success:
                video.transcript = transcript_response.data
                self._save_to_db(video)
            
            return ApiResponse(success=True, data=video)
        except Exception as e:
            return ApiResponse(success=False, error=f"Video retrieval error: {str(e)}")
    
    def _get_playlist_videos(
        self, 
        playlist_url: str, 
        delay_range: Tuple[float, float] = (0.01, 0.03)
    ) -> ApiResponse[List[Video]]:
        """Fetch all videos with metadata and transcripts from a playlist"""
        try:
            playlist_id = self._extract_playlist_id(playlist_url)
            video_ids = self._extract_playlist_video_ids(playlist_id)
            
            logging.info(f"Found {len(video_ids)} videos in playlist {playlist_id}")
            
            videos = []
            for i, video_id in enumerate(video_ids):
                # Apply delay between requests to avoid rate limiting
                if i > 0:
                    time.sleep(random.uniform(*delay_range))
                
                video_url = f"{self.YOUTUBE_BASE_URL}/watch?v={video_id}"
                logging.info(f"Processing video {i+1}/{len(video_ids)}: {video_url}")
                
                # Try database cache first
                cached_video = self._get_from_db_cache(video_id)
                if cached_video:
                    videos.append(cached_video)
                    continue
                
                video_response = self._get_video(video_url)
                if video_response.success:
                    videos.append(video_response.data)
            
            return ApiResponse(success=True, data=videos)
        except Exception as e:
            return ApiResponse(success=False, error=f"Playlist retrieval error: {str(e)}")

    def _get_from_db_cache(self, video_id: str) -> Optional[Video]:
        """Try to fetch video from database cache"""
        if not self.db_client:
            return None
        
        db_response = self.db_client.get_video_by_id(video_id)
        if db_response.success and db_response.data:
            logging.info(f"Video {video_id} found in database cache")
            return db_response.data
        
        return None
    
    def _get_transcript(self, video_id: str) -> ApiResponse[str]:
        """Fetch transcript for a YouTube video by ID"""
        try:
            transcript = " ".join(
                snippet.text for snippet in self.transcript_api.fetch(
                    video_id, languages=self.DEFAULT_LANGUAGES
                )
            )
            return ApiResponse(success=True, data=transcript)
        except Exception as e:
            return ApiResponse(success=False, error=f"Transcript retrieval error: {str(e)}")

    def _extract_playlist_video_ids(self, playlist_id: str) -> List[str]:
        """Extract all video IDs from a playlist"""
        url = f"{self.YOUTUBE_BASE_URL}/playlist?list={playlist_id}"
        response = self.session.get(url, timeout=self.timeout).text
        
        # Extract video IDs and remove duplicates
        matches = self.PLAYLIST_VIDEO_PATTERN.findall(response)
        video_ids = []
        seen = set()
        
        for match in matches:
            video_id = match[0] or match[1]
            if video_id and video_id not in seen:
                video_ids.append(video_id)
                seen.add(video_id)
        
        return video_ids

    def _extract_video_id(self, video_url: str) -> str:
        """Extract video ID from URL or direct ID input"""
        # Handle direct ID input
        if re.match(r'^[0-9A-Za-z_-]{11}$', video_url):
            return video_url
            
        # Extract from URL
        match = self.VIDEO_ID_RE.search(video_url)
        if match:
            return match.group(1)
                
        raise ValueError(f"Invalid YouTube URL or ID: {video_url}")
        
    def _extract_playlist_id(self, playlist_url: str) -> str:
        """Extract playlist ID from URL or direct ID input"""
        # Handle direct ID input
        if re.match(r'^[0-9A-Za-z_-]+$', playlist_url) and '/' not in playlist_url and '.' not in playlist_url:
            return playlist_url
            
        # Extract from URL
        match = self.PLAYLIST_ID_RE.search(playlist_url)
        if match:
            return match.group(1)
                
        raise ValueError(f"Invalid playlist URL or ID: {playlist_url}")
    
    def _fetch_metadata(self, video_id: str) -> Dict[str, Any]:
        """Fetch video metadata from YouTube page"""
        url = f"{self.YOUTUBE_BASE_URL}/watch?v={video_id}"
        response = self.session.get(url, timeout=self.timeout).text
        
        # Extract and decode metadata
        metadata = {}
        for key, (pattern, default) in self.METADATA_PATTERNS.items():
            match = re.search(pattern, response)
            metadata[key] = html.unescape(match.group(1) if match else default)
        
        return metadata
    
    def _save_to_db(self, video: Video) -> bool:
        """Save video to database if enabled and transcript exists"""
        if not (self.db_client and video.transcript):
            return False
            
        # Skip videos with missing essential metadata
        if video.title in ("", "Unknown") or video.channel in ("", "Unknown"):
            return False
        
        return self.db_client.save_video(video).success