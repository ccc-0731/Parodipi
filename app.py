from flask import Flask, request, jsonify, render_template
import json
from gemini_call import call_gemini_text
from song_database import get_song_by_title, search_songs_by_title, get_song_lyrics

app = Flask(__name__)

# ============= HELPER FUNCTIONS =============

def generate_topic_checklist(math_concept, level, focus_slider):
    """
    Use Gemini to generate a structured list of topics/terms for the math concept.
    focus_slider: 0 = learning experience focus, 100 = teaching focus
    """
    prompt = f"""
    Generate a JSON response with a list of topics, terms, and key concepts related to the math concept "{math_concept}" at the {level} level.
    
    The focus should be on:
    - If focus is closer to 0: Emphasize the journey and experience of learning this concept
    - If focus is closer to 50: Balance between learning experience and teaching
    - If focus is closer to 100: Focus on clearly teaching and explaining the concept
    
    Current focus level: {focus_slider}/100
    
    Return ONLY valid JSON in this format (no markdown, no code blocks):
    {{
        "topics": [
            {{"name": "topic_name", "description": "brief description"}},
            ...
        ]
    }}
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

def generate_parody_lyrics(math_concept, level, focus_slider, selected_topics, chosen_song, song_lyrics):
    """
    Use Gemini to generate the parody song lyrics.
    """
    topics_str = ", ".join([t['name'] for t in selected_topics])
    
    prompt = f"""
    You are a creative songwriter. Create a parody version of the following song that teaches about {math_concept} ({level} level).
    
    Key concepts to include: {topics_str}
    
    Learning/Teaching focus (0=learning experience, 100=teaching): {focus_slider}/100
    
    Original song title: {chosen_song}
    Original song lyrics:
    {song_lyrics}
    
    Create smart, humorous, and educational parody lyrics that:
    1. Keep the same structure and rhyme scheme of the original
    2. Replace words/phrases with math-related equivalents
    3. {'Emphasize the emotional journey and wonder of learning' if focus_slider < 50 else 'Focus on clearly explaining the mathematical concepts' if focus_slider > 50 else 'Balance teaching with an engaging narrative'}
    4. Make sure all selected topics are naturally woven in
    
    Return ONLY the parody lyrics, nothing else.
    """
    
    result = call_gemini_text(prompt)
    return result['raw']

# ============= ROUTES =============

@app.route("/")
def index():
    """Serve the main page."""
    return render_template("index.html")

@app.route("/api/generate-topics", methods=["POST"])
def generate_topics():
    """
    Step 1: User inputs math concept, level, and focus slider.
    Returns a checklist of topics to include in the song.
    """
    data = request.get_json()
    math_concept = data.get('mathConcept', '')
    level = data.get('level', 'high school')
    focus_slider = data.get('focusSlider', 50)
    
    if not math_concept:
        return jsonify({"error": "Math concept is required"}), 400
    
    topics = generate_topic_checklist(math_concept, level, focus_slider)
    
    return jsonify({
        "topics": [{"id": i, "name": t.get('name', ''), "description": t.get('description', ''), "selected": True} 
                   for i, t in enumerate(topics)]
    })

@app.route("/api/search-songs", methods=["GET"])
def search_songs():
    """
    Step 2: Search for songs in our database.
    """
    query = request.args.get('q', '')
    
    if not query:
        return jsonify({"error": "Search query is required"}), 400
    
    # Search in mock database (you can replace with real DB)
    results = search_songs_by_title(query)
    
    return jsonify({"songs": results})

@app.route("/api/get-song-lyrics", methods=["GET"])
def get_song():
    """
    Step 3: Get the full lyrics for a selected song.
    """
    song_title = request.args.get('title', '')
    
    if not song_title:
        return jsonify({"error": "Song title is required"}), 400
    
    lyrics = get_song_lyrics(song_title)
    
    if not lyrics:
        return jsonify({"error": "Song not found"}), 404
    
    return jsonify({"title": song_title, "lyrics": lyrics})

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
    
    if not (math_concept and chosen_song and song_lyrics and selected_topics):
        return jsonify({"error": "Missing required fields"}), 400
    
    parody_lyrics = generate_parody_lyrics(math_concept, level, focus_slider, selected_topics, chosen_song, song_lyrics)
    
    return jsonify({"parodyLyrics": parody_lyrics})


if __name__ == '__main__':
    app.run(port=8000, debug=True)
