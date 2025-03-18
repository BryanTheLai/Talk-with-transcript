from typing import Dict, Any, Optional

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