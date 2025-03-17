from typing import Dict, Any, List, Optional, Union
import re
import requests
import html
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
    """Client for fetching YouTube video metadata and transcripts with proxy support"""
    
    DEFAULT_HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
    }
    
    def __init__(
        self, 
        proxy: Optional[Union[str, Dict[str, str]]] = None,
        timeout: int = 30,
        headers: Optional[Dict[str, str]] = None
    ):
        """
        Initialize YouTube client with optional proxy support.
        
        Args:
            proxy: Proxy URL as string (e.g. 'http://user:pass@host:port') or dict mapping protocol to URL
            timeout: Request timeout in seconds
            headers: Optional custom headers to use for all requests
        """
        self.proxies = {"http": proxy, "https": proxy} if isinstance(proxy, str) else proxy
        self.timeout = timeout
        self.headers = headers or self.DEFAULT_HEADERS.copy()
        self.session = requests.Session()
    
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
        """Fetch transcript for a YouTube video by ID using direct HTTP requests"""
        try:
            # Fetch the video page
            url = f"https://www.youtube.com/watch?v={video_id}"
            response = self._make_request(url).text
            
            # Look for caption tracks data in the page content
            captions_regex = r'"captionTracks":\s*(\[.*?\])'
            captions_match = re.search(captions_regex, response, re.DOTALL)
            
            if not captions_match:
                return ApiResponse(
                    success=False,
                    error="No transcript data found for this video",
                    error_code="transcript_not_found"
                )
            
            captions_data = captions_match.group(1)
            
            # Extract the URL for the first available transcript
            caption_url_regex = r'"baseUrl":\s*"([^"]*)"'
            caption_url_match = re.search(caption_url_regex, captions_data)
            
            if not caption_url_match:
                return ApiResponse(
                    success=False,
                    error="Could not find transcript URL",
                    error_code="transcript_url_not_found"
                )
            
            # Get the transcript URL and unescape it
            transcript_url = html.unescape(caption_url_match.group(1))
            
            # Fetch the transcript XML
            transcript_response = self._make_request(transcript_url)
            transcript_xml = transcript_response.text
            
            # Extract text segments from XML
            text_regex = r'<text[^>]*>(.*?)</text>'
            text_matches = re.findall(text_regex, transcript_xml)
            
            # Combine all segments and unescape HTML entities
            transcript_text = " ".join([html.unescape(text) for text in text_matches])
            
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
            # Extract playlist ID from URL
            playlist_id = self._extract_playlist_id(playlist_url)
            
            # Fetch playlist page
            url = f"https://www.youtube.com/playlist?list={playlist_id}"
            response = self._make_request(url).text
            
            # Extract video IDs from playlist page using regex
            # Look for patterns in both standard format and in embedded JSON data
            pattern = r'(?:"videoId":"([^"]+)"|"videoRenderer":{"videoId":"([^"]+)")'
            matches = re.findall(pattern, response)
            
            # Process matches and remove duplicates
            video_ids = []
            for match in matches:
                video_id = match[0] if match[0] else match[1]
                if video_id and video_id not in video_ids:
                    video_ids.append(video_id)
            
            videos = []
            for video_id in video_ids:
                video_url = f"https://www.youtube.com/watch?v={video_id}"
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

    def _make_request(self, url: str) -> requests.Response:
        """Make HTTP request with configured proxies and headers"""
        response = self.session.get(
            url, 
            headers=self.headers, 
            proxies=self.proxies, 
            timeout=self.timeout
        )
        response.raise_for_status()
        return response

    def _extract_playlist_id(self, playlist_url: str) -> str:
        """Extract playlist ID from URL using regex pattern matching"""
        # Handle case where input might already be a playlist ID
        if re.match(r'^[0-9A-Za-z_-]+$', playlist_url) and not '/' in playlist_url and not '.' in playlist_url:
            return playlist_url
            
        # Pattern matches standard YouTube playlist URL formats
        pattern = r'(?:list=)([0-9A-Za-z_-]+)'
        match = re.search(pattern, playlist_url)
        
        if match:
            return match.group(1)
                
        # If no match was found, raise error
        raise ValueError(f"Could not extract playlist ID from URL: {playlist_url}")

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
        response = self._make_request(url).text
        
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