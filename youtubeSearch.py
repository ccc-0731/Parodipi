import os
import requests
from dotenv import load_dotenv

load_dotenv()

def promptToVideos(prompt: str, max_results: int = 3):
    """Search YouTube for videos matching the prompt.
    
    Returns a list of YouTube watch URLs.
    Uses the YouTube Data API v3 directly.
    """
    youtube_api_key = os.getenv("YOUTUBE_API_KEY")
    if not youtube_api_key:
        print("[youtubeSearch] YOUTUBE_API_KEY not set")
        return []

    try:
        resp = requests.get(
            "https://www.googleapis.com/youtube/v3/search",
            params={
                "part": "snippet",
                "q": prompt,
                "type": "video",
                "maxResults": max_results,
                "key": youtube_api_key,
            },
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()

        urls = []
        for item in data.get("items", []):
            video_id = item.get("id", {}).get("videoId")
            if video_id:
                urls.append(f"https://www.youtube.com/watch?v={video_id}")
        return urls

    except Exception as e:
        print(f"[youtubeSearch] Error: {e}")
        return []


if __name__ == "__main__":
    print(promptToVideos("frogs"))
