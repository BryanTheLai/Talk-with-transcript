import requests
import re
from typing import Dict, Any, Optional
import os  # Import the os module
from dotenv import load_dotenv  # Import load_dotenv

class YoutubeBasicAPI:
    def __init__(self):
        """Initialize YouTube basic client with proxy support."""
        load_dotenv()  # Load environment variables

        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }

        self.proxies = None  # Initialize proxies to None
        proxy_username = os.getenv("PROXY_USERNAME")  # Get proxy username from environment variables
        proxy_password = os.getenv("PROXY_PASSWORD")  # Get proxy password from environment variables

        if proxy_username and proxy_password:
            proxy_host = "p.webshare.io"  # Webshare proxy host
            proxy_port = "80"             # Webshare proxy port (or "8080")
            self.proxies = {
                "http":  f"http://{proxy_username}:{proxy_password}@{proxy_host}:{proxy_port}",
                "https": f"http://{proxy_username}:{proxy_password}@{proxy_host}:{proxy_port}",
            }
            print("Proxies configured.") # Optional: Confirmation message
        else:
            print("Proxy credentials not found in environment variables. Running without proxies.") # Optional: Informative message


    def _extract_metadata(self, html: str, regex: str) -> Optional[str]:
        """Extract metadata using regex."""
        match = re.search(regex, html)
        return match.group(1) if match else None

    def get_video_details(self, video_id: str) -> Dict[str, Any]:
        """Get basic information about a video, now with proxy support."""
        try:
            url = f"https://www.youtube.com/watch?v={video_id}"
            response = requests.get(url, headers=self.headers, proxies=self.proxies) # Pass proxies to requests.get()
            response.raise_for_status()
            html = response.text

            title = self._extract_metadata(html, r'<meta name="title" content="([^"]*)"')
            channel = self._extract_metadata(html, r'"ownerChannelName":"([^"]*)"')
            published_at = self._extract_metadata(html, r'"publishDate":"([^"]*)"')
            views = self._extract_metadata(html, r'"viewCount":"([^"]*)"')

            return {
                'id': video_id,
                'title': title or 'Unknown Title',
                'channel': channel or 'Unknown Channel',
                'published_at': published_at or 'Unknown Date',
                'views': views or '0',
                'url': url
            }
        except requests.exceptions.RequestException as e:
            return {'error': str(e)}

if __name__ == "__main__":
    api = YoutubeBasicAPI()
    video_id = 'jvtu7JZlQCk'
    details = api.get_video_details(video_id)
    print("Video Details:")
    print(f"Title: {details.get('title')}")
    print(f"Channel: {details.get('channel')}")
    print(f"Published: {details.get('published_at')}")
    print(f"Views: {details.get('views')}")