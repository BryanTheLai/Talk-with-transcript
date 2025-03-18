from typing import Dict, Any, List, Optional, Union
import re
import requests
import html
import logging
import time
import random
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api.proxies import GenericProxyConfig
from .ApiResponse import ApiResponse
from .models import Video
from .DatabaseClient import DatabaseClient

class YoutubeClient:
    """Client for fetching YouTube video metadata and transcripts with proxy support"""
    
    # Consolidated patterns and constants
    VIDEO_ID_RE = re.compile(r'(?:v=|\/embed\/|\/shorts\/|youtu\.be\/)([0-9A-Za-z_-]{11})')
    PLAYLIST_ID_RE = re.compile(r'(?:list=)([0-9A-Za-z_-]+)')
    PLAYLIST_VIDEO_PATTERN = re.compile(r'(?:"videoId":"([^"]+)"|"videoRenderer":{"videoId":"([^"]+)")')
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
        proxy: Optional[Union[str, Dict[str, str]]] = None,
        timeout: int = 30,
        headers: Optional[Dict[str, str]] = None,
        db_connection_string: Optional[str] = None,
        use_database: bool = True
    ):
        """Initialize YouTube client with optional proxy and database support"""
        self.proxies = {"http": proxy, "https": proxy} if isinstance(proxy, str) else proxy
        self.timeout = timeout
        self.headers = headers or self.DEFAULT_HEADERS.copy()
        self.session = requests.Session()
        
        # Setup database client
        self.use_database = use_database
        self.db_client = None
        if use_database:
            try:
                self.db_client = DatabaseClient(db_connection_string)
                self.db_client.connect()
                self.db_client.initialize_schema()
            except Exception as e:
                logging.error(f"Failed to initialize database client: {str(e)}")
                self.use_database = False
        
        # Setup transcript API with proxy if needed
        self.transcript_api = self._configure_transcript_api()

    def _configure_transcript_api(self) -> YouTubeTranscriptApi:
        """Configure transcript API with proxy if provided"""
        if not self.proxies:
            return YouTubeTranscriptApi()
            
        http_proxy = self.proxies.get("http")
        https_proxy = self.proxies.get("https")
        
        if http_proxy or https_proxy:
            return YouTubeTranscriptApi(
                proxy_config=GenericProxyConfig(
                    http_url=http_proxy,
                    https_url=https_proxy,
                )
            )
        return YouTubeTranscriptApi()
    
    def _create_error_response(self, message: str, code: str) -> ApiResponse:
        """Create standardized error response"""
        return ApiResponse(
            success=False,
            error=f"Failed to {message}",
            error_code=code
        )

    def fetch_content(self, url: str) -> ApiResponse[List[Video]]:
        """Main entry point: Fetch YouTube content (metadata and transcript) from URL"""
        try:
            # Check if URL is a playlist
            is_playlist = self.PLAYLIST_ID_RE.search(url) is not None
            
            if is_playlist:
                return self._get_playlist_videos(url)
            else:
                response = self._get_video(url)
                if response.success:
                    return ApiResponse(success=True, data=[response.data])
                return response
        except Exception as e:
            return self._create_error_response(f"fetch content: {str(e)}", "content_fetch_error")

    def _get_from_db_cache(self, video_id: str) -> Optional[Video]:
        """Try to fetch video from database cache"""
        if not (self.use_database and self.db_client):
            return None
        
        db_response = self.db_client.get_video_by_id(video_id)
        if db_response.success and db_response.data:
            logging.info(f"Video {video_id} found in database cache")
            return db_response.data
        
        return None

    def _get_video(self, video_url: str) -> ApiResponse[Video]:
        """Fetch complete video data with metadata and transcript"""
        try:
            video_id = self._extract_video_id(video_url)
            
            # Try database cache first
            cached_video = self._get_from_db_cache(video_id)
            if cached_video:
                return ApiResponse(success=True, data=cached_video)
                
            logging.info(f"Video {video_id} not found in cache, fetching from YouTube")
            
            # Fetch fresh data
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
            
            # Get transcript
            transcript_response = self._get_transcript(video_id)
            if transcript_response.success:
                video.transcript = transcript_response.data
                self._save_to_db(video)  # Only save if we have a transcript
            
            return ApiResponse(success=True, data=video)
        except Exception as e:
            return self._create_error_response(f"retrieve video: {str(e)}", "video_retrieval_error")
    
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
            return self._create_error_response(f"retrieve transcript: {str(e)}", "transcript_retrieval_error")
    
    def _apply_request_delay(self, should_delay: bool, min_delay: float, max_delay: float) -> None:
        """Apply delay between requests to avoid rate limiting"""
        if should_delay:
            time.sleep(random.uniform(min_delay, max_delay) / 100) 
    
    def _get_playlist_videos(
        self, 
        playlist_url: str, 
        min_delay: float = 1.0,  
        max_delay: float = 3.0 
    ) -> ApiResponse[List[Video]]:
        """Fetch all videos with metadata and transcripts from a playlist"""
        try:
            playlist_id = self._extract_playlist_id(playlist_url)
            video_ids = self._extract_playlist_video_ids(playlist_id)
            
            logging.info(f"Found {len(video_ids)} videos in playlist {playlist_id}")
            
            videos = []
            need_youtube_request = False  # Track if we need to make YouTube requests
            
            for i, video_id in enumerate(video_ids):
                # Apply delay if needed from previous YouTube request
                self._apply_request_delay(need_youtube_request and i > 0, min_delay, max_delay)
                
                video_url = f"{self.YOUTUBE_BASE_URL}/watch?v={video_id}"
                logging.info(f"Processing video {i+1}/{len(video_ids)}: {video_url}")
                
                # Reset the flag for this iteration
                need_youtube_request = False
                
                # Try to get from database cache first
                cached_video = self._get_from_db_cache(video_id)
                if cached_video:
                    videos.append(cached_video)
                    continue  # Skip YouTube request entirely
                
                # If we reach here, we need to make a YouTube request
                need_youtube_request = True
                video_response = self._get_video(video_url)
                if video_response.success:
                    videos.append(video_response.data)
            
            return ApiResponse(success=True, data=videos)
        except Exception as e:
            return self._create_error_response(f"retrieve playlist: {str(e)}", "playlist_retrieval_error")
    
    def _extract_playlist_video_ids(self, playlist_id: str) -> List[str]:
        """Extract all video IDs from a playlist"""
        url = f"{self.YOUTUBE_BASE_URL}/playlist?list={playlist_id}"
        response = self._make_request(url).text
        
        # Extract video IDs using pre-compiled regex
        matches = self.PLAYLIST_VIDEO_PATTERN.findall(response)
        
        # Process matches and remove duplicates
        video_ids = []
        seen = set()
        for match in matches:
            video_id = match[0] or match[1]
            if video_id and video_id not in seen:
                video_ids.append(video_id)
                seen.add(video_id)
        
        return video_ids

    def _make_request(self, url: str) -> requests.Response:
        """Make HTTP request with configured proxies and headers"""
        response = self.session.get(
            url, 
            proxies=self.proxies, 
            timeout=self.timeout,
            headers=self.headers
        )
        response.raise_for_status()
        return response

    def _extract_video_id(self, video_url: str) -> str:
        """Extract video ID from URL"""
        # Handle direct ID input
        if re.match(r'^[0-9A-Za-z_-]{11}$', video_url):
            return video_url
            
        # Regular URL format
        match = self.VIDEO_ID_RE.search(video_url)
        if match:
            return match.group(1)
                
        raise ValueError(f"Could not extract video ID from: {video_url}")
        
    def _extract_playlist_id(self, playlist_url: str) -> str:
        """Extract playlist ID from URL"""
        # Handle direct ID input
        if re.match(r'^[0-9A-Za-z_-]+$', playlist_url) and not '/' in playlist_url and not '.' in playlist_url:
            return playlist_url
            
        # Regular URL format
        match = self.PLAYLIST_ID_RE.search(playlist_url)
        if match:
            return match.group(1)
                
        raise ValueError(f"Could not extract playlist ID from: {playlist_url}")
    
    def _fetch_metadata(self, video_id: str) -> Dict[str, Any]:
        """Fetch video metadata from YouTube page"""
        url = f"{self.YOUTUBE_BASE_URL}/watch?v={video_id}"
        response = self._make_request(url).text
        
        # Extract and decode metadata
        metadata = {}
        for key, (pattern, default) in self.METADATA_PATTERNS.items():
            match = re.search(pattern, response)
            value = match.group(1) if match else default
            metadata[key] = html.unescape(value)
        
        return metadata
    
    def _save_to_db(self, video: Video) -> bool:
        """Save video to database if enabled and transcript exists"""
        if not (self.use_database and self.db_client and video.transcript):
            return False
        
        return self.db_client.save_video(video).success