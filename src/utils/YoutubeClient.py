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
from .models import Video  # Keep this import
from .DatabaseClient import DatabaseClient

class YoutubeClient:
    """Client for fetching YouTube video metadata and transcripts with proxy support"""
    
    DEFAULT_HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
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

    def _configure_transcript_api(self):
        """Configure transcript API with proxy if provided"""
        if self.proxies:
            http_proxy = self.proxies.get("http")
            https_proxy = self.proxies.get("https")
            
            if http_proxy or https_proxy:
                from youtube_transcript_api.proxies import GenericProxyConfig
                return YouTubeTranscriptApi(
                    proxy_config=GenericProxyConfig(
                        http_url=http_proxy,
                        https_url=https_proxy,
                    )
                )
        return YouTubeTranscriptApi()  # Return instance, not class

    def fetch_content(self, url: str) -> ApiResponse[List[Video]]:
        """
        Main entry point: Fetch YouTube content (metadata and transcript) from URL
        
        This method handles both single videos and playlists, automatically
        detecting the type of content and retrieving full metadata and transcripts.
        All successful fetches are cached in the database when enabled.
        
        Args:
            url: YouTube video or playlist URL
            
        Returns:
            ApiResponse containing a list of Video objects with transcripts
        """
        try:
            # Check if URL is a playlist
            is_playlist = bool(re.search(r'list=([^&]+)', url))
            
            if is_playlist:
                return self._get_playlist_videos(url)
            else:
                response = self._get_video(url)
                if response.success:
                    return ApiResponse(success=True, data=[response.data])
                return response
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
            if self.use_database and self.db_client:
                db_response = self.db_client.get_video_by_id(video_id)
                if db_response.success and db_response.data:
                    return ApiResponse(success=True, data=db_response.data)
            
            # Fetch fresh data
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
            
            # Get transcript
            transcript_response = self._get_transcript(video_id)
            if transcript_response.success:
                video.transcript = transcript_response.data
            
            # Save to database if transcript is not empty
            if self.use_database and self.db_client and video.transcript:
                self.db_client.save_video(video)
            
            return ApiResponse(success=True, data=video)
        except Exception as e:
            return ApiResponse(
                success=False, 
                error=f"Failed to retrieve video: {str(e)}",
                error_code="video_retrieval_error"
            )
    
    def _get_transcript(self, video_id: str) -> ApiResponse[str]:
        """Fetch transcript for a YouTube video by ID"""
        try:
            # Try API first
            fetched_transcript  = self.transcript_api.fetch(
                video_id,                
                languages=['en', 'en-US', 'en-GB'],
                )
            transcript_text = " ".join([snippet.text for snippet  in fetched_transcript ])
            return ApiResponse(success=True, data=transcript_text)
        except Exception as e:
            return ApiResponse(
                success=False,
                error=f"Failed to retrieve transcript: {str(e)}",
                error_code="transcript_retrieval_error"
            )
    
    def _get_playlist_videos(
        self, 
        playlist_url: str, 
        min_delay: float = 2.0,
        max_delay: float = 5.0
    ) -> ApiResponse[List[Video]]:
        """Fetch all videos with metadata and transcripts from a playlist"""
        try:
            playlist_id = self._extract_playlist_id(playlist_url)
            video_ids = self._extract_playlist_video_ids(playlist_id)
            
            logging.info(f"Found {len(video_ids)} videos in playlist {playlist_id}")
            
            videos = []
            for i, video_id in enumerate(video_ids):
                video_url = f"https://www.youtube.com/watch?v={video_id}"
                logging.info(f"Processing video {i+1}/{len(video_ids)}: {video_url}")
                
                video_response = self._get_video(video_url)
                if video_response.success:
                    videos.append(video_response.data)
                
                # Add delay between requests except after the last one
                if i < len(video_ids) - 1:
                    time.sleep(random.uniform(min_delay, max_delay))
            
            return ApiResponse(success=True, data=videos)
        except Exception as e:
            return ApiResponse(
                success=False,
                error=f"Failed to retrieve playlist: {str(e)}",
                error_code="playlist_retrieval_error"
            )
    
    def _extract_playlist_video_ids(self, playlist_id: str) -> List[str]:
        """Extract all video IDs from a playlist"""
        url = f"https://www.youtube.com/playlist?list={playlist_id}"
        response = self._make_request(url).text
        
        # Extract video IDs using regex
        pattern = r'(?:"videoId":"([^"]+)"|"videoRenderer":{"videoId":"([^"]+)")'
        matches = re.findall(pattern, response)
        
        # Process matches and remove duplicates
        video_ids = []
        for match in matches:
            video_id = match[0] if match[0] else match[1]
            if video_id and video_id not in video_ids:
                video_ids.append(video_id)
        
        return video_ids

    # Helper methods below
    def _make_request(self, url: str) -> requests.Response:
        """Make HTTP request with configured proxies and headers"""
        if self.proxies:
            # Create a new session for this specific request
            request_session = requests.Session()
            request_session.headers.update(self.headers)
            response = request_session.get(url, proxies=self.proxies, timeout=self.timeout)
        else:
            # Use the persistent session for better performance
            response = self.session.get(url, headers=self.headers, timeout=self.timeout)
        
        response.raise_for_status()
        return response

    def _extract_playlist_id(self, playlist_url: str) -> str:
        """Extract playlist ID from URL"""
        # Handle direct ID input
        if re.match(r'^[0-9A-Za-z_-]+$', playlist_url) and not '/' in playlist_url and not '.' in playlist_url:
            return playlist_url
            
        # Regular URL format
        match = re.search(r'(?:list=)([0-9A-Za-z_-]+)', playlist_url)
        if match:
            return match.group(1)
                
        raise ValueError(f"Could not extract playlist ID from URL: {playlist_url}")
    
    def _extract_video_id(self, video_url: str) -> str:
        """Extract video ID from URL"""
        # Handle direct ID input
        if re.match(r'^[0-9A-Za-z_-]{11}$', video_url):
            return video_url
            
        # Regular URL formats
        pattern = r'(?:v=|\/embed\/|\/shorts\/|youtu\.be\/)([0-9A-Za-z_-]{11})'
        match = re.search(pattern, video_url)
        if match:
            return match.group(1)
                
        raise ValueError(f"Could not extract video ID from URL: {video_url}")
    
    def _fetch_metadata(self, video_id: str) -> Dict[str, Any]:
        """Fetch video metadata from YouTube page"""
        url = f"https://www.youtube.com/watch?v={video_id}"
        response = self._make_request(url).text
        
        # Extract and decode metadata
        title = self._extract_regex(response, r'<meta name="title" content="([^"]*)"') or "Unknown"
        channel = self._extract_regex(response, r'"ownerChannelName":"([^"]*)"') or "Unknown"
        published_date = self._extract_regex(response, r'"publishDate":"([^"]*)"') or "Unknown"
        view_count = self._extract_regex(response, r'"viewCount":"([^"]*)"') or "0"
        description = self._extract_regex(response, r'"description":{"simpleText":"(.*?)"(?=})') or ""
        
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
    