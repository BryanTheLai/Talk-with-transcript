from typing import Dict, List
from .YoutubeClient import Video

class VideoFormatter:
    """Formats Video objects for different output formats (console, XML)"""
    
    @staticmethod
    def to_xml(video: Video, include_transcript: bool = True) -> str:
        """Format video as XML with optional transcript inclusion"""
        transcript_tag = f"<TRANSCRIPT>{video.transcript}</TRANSCRIPT>" if include_transcript and video.transcript else ""
        
        # Add description to XML output
        return f"""<YOUTUBE_VIDEO>
    <VIDEO_TITLE>{video.title}</VIDEO_TITLE>
    <CHANNEL>{video.channel}</CHANNEL>
    <PUBLISHED>{video.published_date}</PUBLISHED>
    <VIEWS>{video.view_count}</VIEWS>
    <URL>{video.url}</URL>
    <VIDEO_ID>{video.id}</VIDEO_ID>
    <DESCRIPTION>{video.description}</DESCRIPTION>
    {transcript_tag}
</YOUTUBE_VIDEO>"""
    
    @staticmethod
    def to_console(video: Video) -> str:
        """Format video for human-readable console output with emojis"""
        lines = [
            f"📹 Video: {video.title}",
            f"👤 Channel: {video.channel}",
            f"📅 Published: {video.published_date}",
            f"👁️ Views: {video.view_count}",
            f"🔗 URL: {video.url}",
            f"🆔 Video ID: {video.id}",
        ]
        
        # Add description preview
        if video.description:
            preview_length = min(100, len(video.description))
            desc_preview = f"{video.description[:preview_length]}..." if len(video.description) > preview_length else video.description
            lines.append(f"📄 Description: {desc_preview}")
        
        # Add transcript preview if available
        if video.transcript:
            preview_length = min(200, len(video.transcript))
            preview = f"{video.transcript[:preview_length]}..." if len(video.transcript) > preview_length else video.transcript
            lines.append(f"📝 Transcript Preview: {preview}")
            lines.append(f"   Length: {len(video.transcript):,} characters")
        
        return "\n".join(lines)