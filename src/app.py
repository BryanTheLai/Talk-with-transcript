from typing import Dict, List
from utils.YoutubeHandler import YoutubeHandler
from llm.GeminiClient import GeminiClient

def details_formatted(detail: Dict) -> Dict[str, str]:
    """Print video details in a structured, readable format."""
    result = f"""
    <YOUTUBE_VIDEO>
    <VIDEO_TITLE>{detail['title']}</VIDEO_TITLE>
    <CHANNEL>{detail['channel']}</CHANNEL>
    <PUBLISHED>{detail['date']}</PUBLISHED>
    <VIEWS>{detail['views']}</VIEWS>
    <URL>{detail['url']}</URL>
    <VIDEO_ID>{detail['id']}</VIDEO_ID>
    <TRANSCRIPT>{detail['transcript']}</TRANSCRIPT>
    </YOUTUBE_VIDEO>
    """
    return {'result': result, 'success': True}

def main():
    video_url = "https://www.youtube.com/watch?v=4ef0juAMqoE"
    playlist_url = "https://www.youtube.com/playlist?list=PLMV8UXQuOWKOY5fl1ccuMvDYjXwqRA69j"
    
    youtube_api = YoutubeHandler()
    video_details = youtube_api.process_url(video_url)
    
    print(f"\n📋 Found {len(video_details)} videos in playlist\n")
    for detail in video_details:
        print(details_formatted(detail))
    
    # gemini = GeminiClient()
    # response = gemini.process_transcripts(details, model="gemini-2.0-flash-lite")
    # print(response.text)

if __name__ == "__main__":
    main()