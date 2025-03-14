from youtube_transcript_api import YouTubeTranscriptApi
from pytube import YouTube, Playlist

def get_video_transcript(video_url: str) -> str:
    """
    Retrieves the transcript for a single YouTube video.

    Args:
        video_url: The URL of the YouTube video.

    Returns:
        The transcript text as a string.
        Returns an error message if transcript is not available or an error occurs.
    """
    try:
        yt = YouTube(video_url)
        video_id = yt.video_id
        transcript_response = YouTubeTranscriptApi.get_transcript(video_id)
        transcript_text = " ".join([segment['text'] for segment in transcript_response])
        return transcript_text
    except Exception as e:
        return f"An error occurred: {e}"

def get_playlist_video_links(playlist_url: str) -> list[str]:
    """
    Retrieves all video URLs from a YouTube playlist.

    Args:
        playlist_url: The URL of the YouTube playlist.

    Returns:
        A list of video URLs in the playlist.
    """
    playlist = Playlist(playlist_url)
    video_links = playlist.video_urls
    return video_links


# #
# playlist_link = "https://www.youtube.com/playlist?list=PLMV8UXQuOWKMO6-9CQmjFo0bqxIf7b2as"
# video_urls = get_playlist_video_links(playlist_link)
# all_transcripts = []
# for url in video_urls:
#   all_transcripts.append(get_video_transcript(url))

# from google import genai
# from google.genai import types
# from google.colab import userdata
# api_key = userdata.get('GEMINI_API_KEY')
# client = genai.Client(api_key=api_key)

# sys_instruct = f"""You are an expert AI/ML engineer from Meta/Scale AI. 

# Explain concepts clearly and directly, avoiding jargon. Focus on deep understanding.

# Use a logical, sequential narrative. Highlight code changes before full code blocks. Apply SOLID principles.

# Provide concise, elegant explanations and type-safe code (no "any").

# Do not reveal your identity or internal information."""

# response = client.models.generate_content(
#     model="gemini-2.0-flash",
#     config=types.GenerateContentConfig(
#         system_instruction=sys_instruct),
#     contents=[ "Transcripts to teach me:\n" + trans for trans in all_transcripts]
# )