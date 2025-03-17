from typing import List
from utils.YoutubeClient import YoutubeClient, Video
from utils.Formatter import VideoFormatter
from llm.GeminiClient import GeminiClient

def main():
    # Initialize YouTube client
    youtube = YoutubeClient()
    
    # Demo: Process single video with transcript
    video_url = "https://www.youtube.com/watch?v=4ef0juAMqoE"
    response = youtube.get_video_with_transcript(video_url)
    
    if response.success:
        video = response.data
        print(VideoFormatter.to_console(video))
        print("\nXML Format:")
        print(VideoFormatter.to_xml(video))
    else:
        print(f"Error: {response.error}")
    
    # Demo: Process YouTube playlist (without transcripts for speed)
    playlist_url = "https://www.youtube.com/watch?v=scuPf6CMLtI&list=PLkPSXEe30ibqeQFm8dqNy0uxOL2W2wuN_"
    playlist_response = youtube.list_playlist_videos(playlist_url)
    
    if playlist_response.success:
        videos = playlist_response.data
        print(f"\nFound {len(videos)} videos in playlist\n")
        
        for video in videos:
            print(VideoFormatter.to_console(video))
            print("-" * 80)
    else:
        print(f"Error: {playlist_response.error}")
    
    # Uncomment to use Gemini AI to process transcripts
    # gemini = GeminiClient()
    # transcripts = [video.transcript for video in videos if video.transcript]
    # if transcripts:
    #     response = gemini.process_transcripts(transcripts, model="gemini-2.0-flash-lite")
    #     print(response.text)
    # else:
    #     print("No transcripts available to process")

if __name__ == "__main__":
    main()