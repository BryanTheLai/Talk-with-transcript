from typing import Dict, Any, List, Optional, Union, Tuple
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
        proxy: Optional[Union[str, Dict[str, str]]] = None,
        timeout: int = 30,
        headers: Optional[Dict[str, str]] = None,
        db_connection_string: Optional[str] = None,
        use_database: bool = True
    ):
        """Initialize YouTube client with optional proxy and database support"""
        # Configure HTTP session
        self.session = requests.Session()
        self.proxies = self._setup_proxies(proxy)
        self.timeout = timeout
        self.headers = headers or self.DEFAULT_HEADERS.copy()
        self.session.headers.update(self.headers)
        
        # Configure database
        self.use_database = use_database
        self.db_client = self._setup_database(db_connection_string) if use_database else None
        
        # Configure transcript API with proxy
        self.transcript_api = self._configure_transcript_api()

    def _setup_proxies(self, proxy: Optional[Union[str, Dict[str, str]]]) -> Optional[Dict[str, str]]:
        """Convert proxy input to standardized dictionary format"""
        if not proxy:
            return None
        return {"http": proxy, "https": proxy} if isinstance(proxy, str) else proxy

    def _setup_database(self, connection_string: Optional[str]) -> Optional[DatabaseClient]:
        """Set up and initialize database connection"""
        if not connection_string:
            self.use_database = False
            return None
            
        try:
            db = DatabaseClient(connection_string)
            db.connect()
            db.initialize_schema()
            return db
        except Exception as e:
            logging.error(f"Failed to initialize database: {str(e)}")
            self.use_database = False
            return None

    def _configure_transcript_api(self) -> YouTubeTranscriptApi:
        """Configure transcript API with proxy if provided"""
        if not self.proxies:
            return YouTubeTranscriptApi()
            
        proxy_config = GenericProxyConfig(
            http_url=self.proxies.get("http"),
            https_url=self.proxies.get("https")
        )
        return YouTubeTranscriptApi(proxy_config=proxy_config)
    
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
            return ApiResponse(
                success=False,
                error=f"Failed to fetch content: {str(e)}",
                error_code="content_fetch_error"
            )

    def _get_video(self, video_url: str) -> ApiResponse[Video]:
        """Fetch complete video data with metadata and transcript"""
        try:
            video_id = self._extract_video_id(video_url)
            
            # Try database cache first
            cached_video = self._get_from_db_cache(video_id)
            if cached_video:
                return ApiResponse(success=True, data=cached_video)
                
            logging.info(f"Video {video_id} not found in cache, fetching from YouTube")
            
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
            return ApiResponse(
                success=False,
                error=f"Failed to retrieve video: {str(e)}",
                error_code="video_retrieval_error"
            )
    
    def _get_playlist_videos(
        self, 
        playlist_url: str, 
        delay_range: Tuple[float, float] = (0.01, 0.03)
    ) -> ApiResponse[List[Video]]:
        """Fetch all videos with metadata and transcripts from a playlist"""
        try:
            min_delay, max_delay = delay_range
            playlist_id = self._extract_playlist_id(playlist_url)
            video_ids = self._extract_playlist_video_ids(playlist_id)
            
            logging.info(f"Found {len(video_ids)} videos in playlist {playlist_id}")
            
            videos = []
            need_delay = False  # Track if we need to delay for rate limiting
            
            for i, video_id in enumerate(video_ids):
                # Apply delay between YouTube requests to avoid rate limiting
                if need_delay and i > 0:
                    time.sleep(random.uniform(min_delay, max_delay))
                
                video_url = f"{self.YOUTUBE_BASE_URL}/watch?v={video_id}"
                logging.info(f"Processing video {i+1}/{len(video_ids)}: {video_url}")
                
                # Reset the delay flag for this iteration
                need_delay = False
                
                # Try database cache first
                cached_video = self._get_from_db_cache(video_id)
                if cached_video:
                    videos.append(cached_video)
                    continue
                
                # If we reach here, we need to make a YouTube request
                need_delay = True
                video_response = self._get_video(video_url)
                if video_response.success:
                    videos.append(video_response.data)
            
            return ApiResponse(success=True, data=videos)
        except Exception as e:
            return ApiResponse(
                success=False,
                error=f"Failed to retrieve playlist: {str(e)}",
                error_code="playlist_retrieval_error"
            )

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
            return ApiResponse(
                success=False,
                error=f"Failed to retrieve transcript: {str(e)}",
                error_code="transcript_retrieval_error"
            )

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
            timeout=self.timeout
        )
        response.raise_for_status()
        return response

    def _extract_video_id(self, video_url: str) -> str:
        """Extract video ID from URL or direct ID input"""
        # Handle direct ID input
        if re.match(r'^[0-9A-Za-z_-]{11}$', video_url):
            return video_url
            
        # Extract from URL
        match = self.VIDEO_ID_RE.search(video_url)
        if match:
            return match.group(1)
                
        raise ValueError(f"Could not extract video ID from: {video_url}")
        
    def _extract_playlist_id(self, playlist_url: str) -> str:
        """Extract playlist ID from URL or direct ID input"""
        # Handle direct ID input
        if re.match(r'^[0-9A-Za-z_-]+$', playlist_url) and '/' not in playlist_url and '.' not in playlist_url:
            return playlist_url
            
        # Extract from URL
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
        if not (self.db_client and video.transcript):
            return False
            
        # Don't save videos with missing essential metadata
        if not video.title or not video.channel or video.channel == "Unknown":
            logging.info(f"Skipping database save for video {video.id}: Invalid metadata")
            return False
        
        return self.db_client.save_video(video).success