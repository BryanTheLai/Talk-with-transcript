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
    
    # URL parsing patterns - combined for efficiency
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
        proxy_url: Optional[str] = None,
    ):
        """Initialize YouTube client with optional proxy and database support
        
        Args:
            timeout: HTTP request timeout in seconds
            headers: Custom HTTP headers
            db_connection_string: Database connection string
            use_database: Whether to use database caching
            proxy_url: Optional HTTP proxy URL
        """
        # Configure HTTP session
        self.session = requests.Session()
        self.timeout = timeout
        self.session.headers.update(headers or self.DEFAULT_HEADERS)
        
        # Configure database
        self._setup_database(db_connection_string, use_database)
        
        # Configure proxy
        self._setup_proxy(proxy_url)
    
    def _setup_database(self, connection_string: Optional[str], use_database: bool) -> None:
        """Set up database connection if enabled"""
        self.use_database = use_database and connection_string
        self.db_client = None
        
        if self.use_database:
            try:
                self.db_client = DatabaseClient(connection_string)
                self.db_client.connect()
                self.db_client.initialize_schema()
            except Exception as e:
                logging.error(f"Database initialization failed: {e}")
                self.use_database = False
    
    def _setup_proxy(self, proxy_url: Optional[str]) -> None:
        """Configure proxy for requests and transcript API if provided"""
        self.session.proxies = None
        self.transcript_api = YouTubeTranscriptApi()
        
        if proxy_url:
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
        """Main entry point: Fetch YouTube content (metadata and transcript) from URL
        
        Args:
            url: YouTube URL for a video or playlist
            
        Returns:
            ApiResponse containing a list of Video objects or error details
        """
        try:
            # Parse URL to extract video and playlist IDs
            video_id, playlist_id = self._parse_url(url)
            
            # Special case for Mix playlists (starting with RD)
            if playlist_id and playlist_id.startswith("RD"):
                return self._handle_mix_playlist(video_id, playlist_id)
            
            # Normal processing path
            if playlist_id:
                return self._get_playlist_videos(url)
            elif video_id:
                video_response = self._get_video(url)
                return ApiResponse(success=True, data=[video_response.data]) if video_response.success else video_response
            else:
                return ApiResponse(success=False, error="No valid YouTube video or playlist ID found in URL")
        except Exception as e:
            return ApiResponse(success=False, error=f"Content fetch error: {str(e)}")
    
    def _parse_url(self, url: str) -> Tuple[Optional[str], Optional[str]]:
        """Parse YouTube URL to extract video and playlist IDs
        
        Returns:
            Tuple of (video_id, playlist_id), either may be None
        """
        video_id_match = self.VIDEO_ID_RE.search(url)
        video_id = video_id_match.group(1) if video_id_match else None
        
        playlist_match = self.PLAYLIST_ID_RE.search(url)
        playlist_id = playlist_match.group(1) if playlist_match else None
        
        return video_id, playlist_id
    
    def _handle_mix_playlist(self, video_id: Optional[str], playlist_id: str) -> ApiResponse[List[Video]]:
        """Handle special case for Mix playlists"""
        if video_id:
            video_response = self._get_video(f"{self.YOUTUBE_BASE_URL}/watch?v={video_id}")
            return ApiResponse(success=True, data=[video_response.data]) if video_response.success else video_response
        else:
            return ApiResponse(success=False, error="Cannot process Mix playlists without a video ID")

    def _get_video(self, video_url: str) -> ApiResponse[Video]:
        """Fetch complete video data with metadata and transcript
        
        Args:
            video_url: YouTube video URL or ID
            
        Returns:
            ApiResponse containing a Video object or error details
        """
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
        """Fetch all videos with metadata and transcripts from a playlist
        
        Args:
            playlist_url: YouTube playlist URL or ID
            delay_range: Range of seconds to wait between requests
            
        Returns:
            ApiResponse containing a list of Video objects or error details
        """
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