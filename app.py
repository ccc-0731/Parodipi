from flask import Flask, request, jsonify, render_template, Response, session, redirect, url_for
import json
import os
import re
import urllib.parse
import requests as http_requests
from gemini_call import call_gemini_text
from song_database import search_songs, get_song_lyrics, get_song_lyrics_with_syllable_count, get_random_song
from user_database import create_user, authenticate_user, create_guest_user, save_parody, get_user_parodies, delete_parody

# Import focus mapping function
from focus_mapping import get_focus_prompt

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'parodipi-dev-secret-key-change-in-prod')

UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ============= HELPER FUNCTIONS =============

def extract_text_from_pdf(pdf_path):
    """Extract text content from a PDF file. Uses pymupdf (better for LaTeX PDFs) with PyPDF2 fallback."""
    # Try pymupdf first — handles LaTeX-generated PDFs much better
    try:
        import fitz  # pymupdf
        doc = fitz.open(pdf_path)
        text = ""
        for page in doc:
            text += page.get_text() + "\n"
        doc.close()
        print(f"[DEBUG] Extracted PDF text using pymupdf ({len(text)} chars)")
        print(f"[DEBUG] First 2000 chars:\n{text[:2000]}")
        if text.strip():
            return text.strip()
    except Exception as e:
        print(f"[DEBUG] pymupdf extraction failed: {e}")

    # Fallback to PyPDF2
    try:
        import PyPDF2
        text = ""
        with open(pdf_path, 'rb') as f:
            reader = PyPDF2.PdfReader(f)
            for page in reader.pages:
                text += page.extract_text() + "\n"
        print(f"[DEBUG] Extracted PDF text using PyPDF2 ({len(text)} chars)")
        print(f"[DEBUG] First 2000 chars:\n{text[:2000]}")
        return text.strip()
    except Exception as e:
        print(f"[DEBUG] PyPDF2 extraction also failed: {e}")
        return ""

def generate_topic_checklist(math_concept, level, focus_slider, pdf_context=""):

    # Use Gemini to generate a structured list of topics/terms for the math concept with focus_slider: 0 = learning experience focus, 100 = teaching focus
    
    pdf_section = ""
    if pdf_context:
        pdf_section = f"""
    The user has provided the following reference material from a PDF. Use this to identify relevant topics, terminology, and concepts that should be included:
    
    --- PDF Content (excerpt) ---
    {pdf_context[:3000]}
    --- End PDF Content ---
    """

    if math_concept and pdf_context:
        concept_section = f'Generate a JSON response with a list of topics, terms, and key concepts related to the math concept "{math_concept}" at the {level} level.\n{pdf_section}'
    elif pdf_context:
        concept_section = f'Analyze the following PDF content and generate a JSON response with a list of math topics, terms, and key concepts found in the material. Determine the appropriate math level from the content.\n{pdf_section}'
    else:
        concept_section = f'Generate a JSON response with a list of topics, terms, and key concepts related to the math concept "{math_concept}" at the {level} level.'

    focus_string = get_focus_prompt(focus_slider)
    prompt = f"""
    {concept_section}
    
    {focus_string}
    
    Current focus level: {focus_slider}/100
    
    Return ONLY valid JSON in this format (no markdown, no code blocks):
    {{
        "topics": [
            {{"name": "Topic Name", "description": "Brief description of the topic"}},
            {{"name": "Another Topic", "description": "Brief description"}}
        ]
    }}
    
    Return 5-8 topics. Each topic should be a specific sub-concept or key term.
    """
    
    result = call_gemini_text(prompt)
    try:
        # Clean up response if needed
        text = result['raw'].strip()
        if text.startswith('```'):
            text = text.split('\n', 1)[1]
            if text.endswith('```'):
                text = text.rsplit('\n', 1)[0]
        topics_data = json.loads(text)
        return topics_data['topics']
    except Exception as e:
        print(f"Error parsing topics: {e}")
        return []

def generate_parody_lyrics(math_concept, level, focus_slider, selected_topics, chosen_song, song_lyrics, pdf_context=""):
    #Use Gemini to generate the parody song lyrics.
    topics_str = ", ".join([t['name'] for t in selected_topics])
    
    # Build the subject description based on what's available
    if math_concept:
        subject = f"{math_concept} ({level} level)"
    else:
        subject = f"the math concepts from the provided reference material ({level} level)"
    
    pdf_section = ""
    if pdf_context:
        pdf_section = f"""
    Reference material from the user's PDF (use this for accuracy and terminology):
    --- PDF Content (excerpt) ---
    {pdf_context[:3000]}
    --- End PDF Content ---
    """
    
    focus_string = get_focus_prompt(focus_slider)
    prompt1 = f"""
    You are a creative songwriter that demonstrates your reasoning process. Create a parody version of the following song that teaches about {subject}.
    
    Key concepts that you MUST include: {topics_str}
    {pdf_section}
    {focus_string}
    Learning/Teaching focus (0=learning experience, 100=teaching): {focus_slider}/100
    
    Original song title: {chosen_song}
    Original song lyrics:
    {song_lyrics}
    
    You are rewriting song lyrics.

    Process:

    1. Reference the syllable counts after each line.
    2. Make sure that the repeated sections maintain the exact same structure throughout the song(e.g. Every "I want it that way" in the song is parodized into -> "You prove it this way")
    3. Write new lyrics with the SAME meaning structure and EXACT syllable counts.
    !!! Make sure that you spell out mathematical symbols how a person would actually say them (e.g. "minus", "partial", "square root/root", "transpose")
    4. For every generated line, show syllable breakdown.
    5. Perform a verification pass and fix syllable count mismatches.
    6. Don't forget to find a title for the final parody song (that is also a parody of the original title).
    
    Make sure you clearly indicate which lines are the finalized parody lyrics.
    """
    
    reasoningResult = call_gemini_text(prompt1)
    print(f"[DEBUG] Parody lyrics reasoning process: {reasoningResult['raw']}")

    prompt2 = f"""You are a formatter that extracts the finalized parody lyrics from the following reasoning process 
        and returns ONLY the final title and complete parody song lyrics as valid JSON.
        
        Return ONLY valid JSON in this exact format (no markdown, no code blocks, no additional text):
        {{
            "title": "Parody Song Title",
            "lyrics": "Full parody lyrics here, with [Verse n], [Chorus] for each section."
        }}
    """
    result = call_gemini_text(prompt2 + reasoningResult['raw'])
    
    try:
        # Clean up response if needed
        text = result['raw'].strip()
        if text.startswith('```'):
            text = text.split('\n', 1)[1]
            if text.endswith('```'):
                text = text.rsplit('\n', 1)[0]
        parody_data = json.loads(text)
        return parody_data
    except Exception as e:
        print(f"Error parsing parody JSON: {e}")
        # Fallback: return raw text as lyrics if JSON parsing fails
        return {"title": f"{chosen_song} (Math Parody)", "lyrics": result['raw']}

# ============= ROUTES =============

# --- Random Song API ---
@app.route("/api/random-song", methods=["GET"])
def random_song():
    """
    Returns a random song (title and artist) from the database.
    """
    song = get_random_song()
    if not song:
        return jsonify({"error": "No songs available"}), 404
    return jsonify(song)

@app.route("/")
def index():
    """Serve the main page — requires login."""
    if 'user_id' not in session:
        return redirect(url_for('login_page'))
    return render_template("index.html", 
                           username=session.get('username', 'Guest'),
                           is_guest=session.get('is_guest', False))

@app.route("/login")
def login_page():
    """Serve the login page."""
    if 'user_id' in session:
        return redirect(url_for('index'))
    return render_template("login.html")

@app.route("/api/login", methods=["POST"])
def api_login():
    data = request.get_json()
    username = data.get('username', '').strip()
    password = data.get('password', '')
    
    if not username or not password:
        return jsonify({"error": "Username and password are required"}), 400
    
    user_id, error = authenticate_user(username, password)
    if error:
        return jsonify({"error": error}), 401
    
    session['user_id'] = user_id
    session['username'] = username
    session['is_guest'] = False
    return jsonify({"user_id": user_id, "username": username})

@app.route("/api/signup", methods=["POST"])
def api_signup():
    data = request.get_json()
    username = data.get('username', '').strip()
    password = data.get('password', '')
    
    if not username or not password:
        return jsonify({"error": "Username and password are required"}), 400
    if len(username) < 3:
        return jsonify({"error": "Username must be at least 3 characters"}), 400
    if len(password) < 4:
        return jsonify({"error": "Password must be at least 4 characters"}), 400
    
    user_id, error = create_user(username, password)
    if error:
        return jsonify({"error": error}), 409
    
    session['user_id'] = user_id
    session['username'] = username
    session['is_guest'] = False
    return jsonify({"user_id": user_id, "username": username})

@app.route("/api/guest", methods=["POST"])
def api_guest():
    user_id = create_guest_user()
    session['user_id'] = user_id
    session['username'] = 'Guest'
    session['is_guest'] = True
    return jsonify({"user_id": user_id, "username": "Guest"})

@app.route("/api/logout", methods=["POST"])
def api_logout():
    session.clear()
    return jsonify({"ok": True})

@app.route("/api/save-parody", methods=["POST"])
def api_save_parody():
    if 'user_id' not in session:
        return jsonify({"error": "Not logged in"}), 401
    if session.get('is_guest'):
        return jsonify({"error": "Guests cannot save parodies. Sign up to save!"}), 403
    
    data = request.get_json()
    topic_names = [t.get('name', t) if isinstance(t, dict) else str(t) for t in data.get('topics', [])]
    
    parody_id = save_parody(
        user_id=session['user_id'],
        math_concept=data.get('mathConcept', ''),
        level=data.get('level', ''),
        topics=topic_names,
        song_title=data.get('songTitle', ''),
        artist=data.get('artist', ''),
        parody_title=data.get('parodyTitle', ''),
        parody_lyrics=data.get('parodyLyrics', ''),
        original_lyrics=data.get('originalLyrics', '')
    )
    return jsonify({"parody_id": parody_id, "message": "Parody saved!"})

@app.route("/api/my-parodies", methods=["GET"])
def api_my_parodies():
    if 'user_id' not in session:
        return jsonify({"error": "Not logged in"}), 401
    parodies = get_user_parodies(session['user_id'])
    return jsonify({"parodies": parodies})

@app.route("/api/delete-parody", methods=["POST"])
def api_delete_parody():
    if 'user_id' not in session:
        return jsonify({"error": "Not logged in"}), 401
    data = request.get_json()
    deleted = delete_parody(session['user_id'], data.get('parody_id', ''))
    if deleted:
        return jsonify({"ok": True})
    return jsonify({"error": "Not found"}), 404

@app.route("/api/generate-topics", methods=["POST"])
def generate_topics():
    """
    Step 1: User inputs math concept, level, and focus slider.
    Optionally uploads a PDF for additional context.
    Returns a checklist of topics to include in the song.
    """
    # Handle both JSON and form data (form data when PDF is uploaded)
    if request.content_type and 'multipart/form-data' in request.content_type:
        math_concept = request.form.get('mathConcept', '')
        level = request.form.get('level', 'high school')
        focus_slider = int(request.form.get('focusSlider', 50))
    else:
        data = request.get_json()
        math_concept = data.get('mathConcept', '')
        level = data.get('level', 'high school')
        focus_slider = data.get('focusSlider', 50)
    
    if not math_concept:
        # Check if PDF is provided instead
        has_pdf = 'pdf' in request.files and request.files['pdf'].filename
        if not has_pdf:
            return jsonify({"error": "Please enter a math concept or upload a PDF"}), 400
    
    # Handle PDF upload
    pdf_context = ""
    if 'pdf' in request.files:
        pdf_file = request.files['pdf']
        if pdf_file.filename:
            pdf_path = os.path.join(UPLOAD_FOLDER, pdf_file.filename)
            pdf_file.save(pdf_path)
            pdf_context = extract_text_from_pdf(pdf_path)
            # Clean up uploaded file
            os.remove(pdf_path)
    
    topics = generate_topic_checklist(math_concept, level, focus_slider, pdf_context)
    
    response_data = {
        "topics": [{"id": i, "name": t.get('name', ''), "description": t.get('description', ''), "selected": True} 
                   for i, t in enumerate(topics)]
    }
    
    if pdf_context:
        response_data["pdfContext"] = pdf_context[:3000]
    
    return jsonify(response_data)

@app.route("/api/search-songs", methods=["GET"])
def search_songs_route():
    """
    Step 2: Search for songs in our database.
    """
    query = request.args.get('q', '')
    mode = request.args.get('mode', 'title')  # 'title' or 'lyrics'
    
    if not query:
        return jsonify({"error": "Search query is required"}), 400
    
    results = search_songs(query, mode=mode)
    
    return jsonify({"songs": results})

@app.route("/api/get-song-lyrics", methods=["GET"])
def get_song():
    """
    Step 3: Get the full lyrics for a selected song.
    """
    song_title = request.args.get('title', '')
    
    if not song_title:
        return jsonify({"error": "Song title is required"}), 400
    
    lyrics_with_counts = get_song_lyrics_with_syllable_count(song_title)
    original_lyrics = get_song_lyrics(song_title)
    
    if not lyrics_with_counts or not original_lyrics:
        return jsonify({"error": "Song not found"}), 404
    
    return jsonify({"title": song_title, "lyrics": lyrics_with_counts, "originalLyrics": original_lyrics})

@app.route("/api/generate-parody", methods=["POST"])
def generate_parody():
    """
    Step 4: Generate the parody song lyrics.
    """
    data = request.get_json()
    
    math_concept = data.get('mathConcept', '')
    level = data.get('level', 'high school')
    focus_slider = data.get('focusSlider', 50)
    selected_topics = data.get('selectedTopics', [])
    chosen_song = data.get('chosenSong', '')
    song_lyrics = data.get('songLyrics', '')
    pdf_context = data.get('pdfContext', '')
    
    if not (chosen_song and song_lyrics and selected_topics):
        return jsonify({"error": "Missing required fields"}), 400
    
    if not math_concept and not pdf_context:
        return jsonify({"error": "Please provide a math concept or PDF context"}), 400
    
    parody_data = generate_parody_lyrics(math_concept, level, focus_slider, selected_topics, chosen_song, song_lyrics, pdf_context)
    
    return jsonify({
        "parodyTitle": parody_data.get("title", f"{chosen_song} (Math Parody)"),
        "parodyLyrics": parody_data.get("lyrics", "")
    })

@app.route("/api/youtube-search", methods=["GET"])
def youtube_search():
    """
    Search YouTube for the original song video.
    Scrapes the first video ID from YouTube search results — no API key needed.
    """
    song_title = request.args.get('title', '')
    artist = request.args.get('artist', '')

    if not song_title:
        return jsonify({"error": "Song title is required"}), 400

    query = f"{song_title} {artist} official music video".strip()
    print(f"[DEBUG] YouTube search query: {query}")

    try:
        # Search YouTube and scrape video IDs from the HTML response
        search_url = "https://www.youtube.com/results?" + urllib.parse.urlencode({"search_query": query})
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9",
        }
        resp = http_requests.get(search_url, headers=headers, timeout=10)
        resp.raise_for_status()

        # Extract video IDs from the page — they appear as "videoId":"XXXXXXXXXXX"
        video_ids = re.findall(r'"videoId":"([a-zA-Z0-9_-]{11})"', resp.text)

        # Deduplicate while preserving order
        seen = set()
        unique_ids = []
        for vid in video_ids:
            if vid not in seen:
                seen.add(vid)
                unique_ids.append(vid)
            if len(unique_ids) >= 3:
                break

        print(f"[DEBUG] Found video IDs: {unique_ids}")

        embed_urls = []
        for video_id in unique_ids:
            embed_urls.append({
                "videoId": video_id,
                "embedUrl": f"https://www.youtube.com/embed/{video_id}",
                "watchUrl": f"https://www.youtube.com/watch?v={video_id}"
            })

        return jsonify({"videos": embed_urls})
    except Exception as e:
        print(f"[DEBUG] YouTube search error: {e}")
        return jsonify({"error": str(e), "videos": []}), 200


@app.route("/api/youtube-audio", methods=["GET"])
def youtube_audio():
    """
    Extract the audio stream URL from a YouTube video using yt-dlp.
    Returns a proxied URL that the browser <audio> element can play.
    """
    video_id = request.args.get('videoId', '')
    if not video_id or len(video_id) != 11:
        return jsonify({"error": "Valid videoId is required"}), 400

    try:
        import yt_dlp

        url = f"https://www.youtube.com/watch?v={video_id}"
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'format': 'bestaudio[ext=m4a]/bestaudio/best',
            'skip_download': True,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            audio_url = info.get('url')
            title = info.get('title', '')
            duration = info.get('duration', 0)

        if not audio_url:
            return jsonify({"error": "Could not extract audio URL"}), 404

        print(f"[DEBUG] Extracted audio for '{title}' ({duration}s)")

        # Store the direct URL in a simple cache so the proxy can use it
        _audio_cache[video_id] = audio_url

        return jsonify({
            "audioUrl": f"/api/youtube-audio-stream?videoId={video_id}",
            "title": title,
            "duration": duration
        })

    except Exception as e:
        print(f"[DEBUG] YouTube audio extraction error: {e}")
        return jsonify({"error": str(e)}), 500


# Simple in-memory cache for audio URLs (videoId -> direct URL)
_audio_cache = {}


@app.route("/api/youtube-audio-stream", methods=["GET"])
def youtube_audio_stream():
    """
    Proxy the YouTube audio stream through our server to avoid CORS issues.
    """
    video_id = request.args.get('videoId', '')
    audio_url = _audio_cache.get(video_id)

    if not audio_url:
        return "Audio not found — please request /api/youtube-audio first", 404

    try:
        # Stream the audio from YouTube through our server
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        }

        # Forward range requests for seeking support
        if 'Range' in request.headers:
            headers['Range'] = request.headers['Range']

        resp = http_requests.get(audio_url, headers=headers, stream=True, timeout=30)

        def generate():
            for chunk in resp.iter_content(chunk_size=8192):
                yield chunk

        response_headers = {
            'Content-Type': resp.headers.get('Content-Type', 'audio/mp4'),
            'Accept-Ranges': 'bytes',
        }
        if 'Content-Length' in resp.headers:
            response_headers['Content-Length'] = resp.headers['Content-Length']
        if 'Content-Range' in resp.headers:
            response_headers['Content-Range'] = resp.headers['Content-Range']

        return Response(generate(), status=resp.status_code, headers=response_headers)

    except Exception as e:
        print(f"[DEBUG] Audio stream proxy error: {e}")
        return f"Error streaming audio: {e}", 500


@app.route("/api/explain-line", methods=["POST"])
def explain_line():
    """
    Given one or more highlighted lines from the parody song, ask Gemini to
    explain the math concepts referenced in those lines.
    """
    data = request.get_json()
    lines = data.get('lines', '')
    math_concept = data.get('mathConcept', '')
    level = data.get('level', 'high school')
    selected_topics = data.get('selectedTopics', [])
    full_lyrics = data.get('fullLyrics', '')

    if not lines:
        return jsonify({"error": "No lines selected"}), 400

    topics_str = ", ".join(
        [t.get('name', t) if isinstance(t, dict) else str(t) for t in selected_topics]
    )

    prompt = f"""You are a friendly and clear math tutor. A student is reading a math parody song about {math_concept or 'various math topics'} ({level} level).

They highlighted the following line(s) from the song and want you to explain the math concept(s) referenced:

--- Highlighted Lines ---
{lines}
--- End Highlighted Lines ---

Context — the full parody lyrics:
{full_lyrics[:2000]}

Topics covered in the song: {topics_str}

Please:
1. Identify which math concept(s) are referenced in the highlighted line(s).
2. Explain each concept clearly and concisely at the {level} level.
3. If the line uses a metaphor or wordplay, explain how the original song lyric was adapted to convey the math idea.
4. Keep your explanation short (2-4 paragraphs max). Use simple language.
"""

    try:
        result = call_gemini_text(prompt)
        return jsonify({"explanation": result['raw']})
    except Exception as e:
        print(f"[DEBUG] Explain line error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/resource-links", methods=["POST"])
def resource_links():
    """
    Given selected topics, find up to 3 trusted learning resource videos.
    Does a single YouTube search for the math concept and picks the best results
    from a pool of trusted educational channels — guaranteeing relevant content.
    """
    data = request.get_json()
    topics = data.get('topics', [])
    math_concept = data.get('mathConcept', '')

    if not topics and not math_concept:
        return jsonify({"error": "No topics or concept provided"}), 400

    topic_names = [t.get('name', t) if isinstance(t, dict) else str(t) for t in topics[:5]]
    search_terms = math_concept or " ".join(topic_names)

    print(f"[DEBUG] Resource links search: {search_terms}")

    # Pool of trusted educational math channels
    trusted_channels = {
        "khan academy":                 {"name": "Khan Academy",                 "icon": "🎓"},
        "3blue1brown":                  {"name": "3Blue1Brown",                  "icon": "🔵"},
        "the organic chemistry tutor":  {"name": "The Organic Chemistry Tutor",  "icon": "🧪"},
        "patrickjmt":                   {"name": "PatrickJMT",                   "icon": "📐"},
        "mit opencourseware":           {"name": "MIT OpenCourseWare",           "icon": "🏛️"},
        "professor leonard":            {"name": "Professor Leonard",            "icon": "👨‍🏫"},
        "mathologer":                   {"name": "Mathologer",                   "icon": "🔢"},
        "numberphile":                  {"name": "Numberphile",                  "icon": "🔢"},
        "eddie woo":                    {"name": "Eddie Woo",                    "icon": "�"},
        "dr. trefor bazett":            {"name": "Dr. Trefor Bazett",            "icon": "📊"},
        "blackpenredpen":               {"name": "blackpenredpen",               "icon": "🖊️"},
    }

    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
    }

    links = []

    try:
        # Single search: let YouTube find the best math videos for this concept
        search_url = "https://www.youtube.com/results?" + urllib.parse.urlencode({
            "search_query": f"{search_terms} math explained"
        })
        resp = http_requests.get(search_url, headers=headers, timeout=10)
        resp.raise_for_status()

        # Parse the embedded JSON data from YouTube's HTML
        json_match = re.search(r'var ytInitialData = ({.*?});</script>', resp.text)
        if not json_match:
            print(f"[DEBUG] Could not find ytInitialData JSON")
            return jsonify({"links": []})

        yt_data = json.loads(json_match.group(1))
        contents = (yt_data.get('contents', {})
                    .get('twoColumnSearchResultsRenderer', {})
                    .get('primaryContents', {})
                    .get('sectionListRenderer', {})
                    .get('contents', [{}])[0]
                    .get('itemSectionRenderer', {})
                    .get('contents', []))

        # Walk through results and pick videos from trusted channels (max 1 per channel)
        found_channels = set()
        for item in contents:
            vr = item.get('videoRenderer')
            if not vr:
                continue

            vid = vr.get('videoId', '')
            title = vr.get('title', {}).get('runs', [{}])[0].get('text', '')
            channel = vr.get('ownerText', {}).get('runs', [{}])[0].get('text', '')
            channel_lower = channel.lower()

            # Check if this video is from any trusted channel
            for keyword, info in trusted_channels.items():
                if keyword in channel_lower and info['name'] not in found_channels:
                    found_channels.add(info['name'])
                    links.append({
                        "url": f"https://www.youtube.com/watch?v={vid}",
                        "title": title[:80],
                        "source": info["name"],
                        "icon": info["icon"],
                    })
                    print(f"[DEBUG]   ✅ [{channel}] {title[:60]} ({vid})")
                    break

            if len(found_channels) >= 3:
                break

    except Exception as e:
        print(f"[DEBUG] Resource links search error: {e}")

    print(f"[DEBUG] Found {len(links)} resource links from {len(set(l['source'] for l in links))} sources")
    return jsonify({"links": links})

if __name__ == '__main__':
    app.run(port=8000, debug=True)
