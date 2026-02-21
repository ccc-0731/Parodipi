from flask import Flask, request, jsonify, render_template
import json
import os
from gemini_call import call_gemini_text
from song_database import get_song_by_title, search_songs_by_title, get_song_lyrics

app = Flask(__name__)

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
    """
    Use Gemini to generate a structured list of topics/terms for the math concept.
    focus_slider: 0 = learning experience focus, 100 = teaching focus
    """
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

    prompt = f"""
    {concept_section}
    
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

def generate_parody_lyrics(math_concept, level, focus_slider, selected_topics, chosen_song, song_lyrics, pdf_context=""):
    """
    Use Gemini to generate the parody song lyrics.
    """
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
    
    prompt = f"""
    You are a creative songwriter. Create a parody version of the following song that teaches about {subject}.
    
    Key concepts to include: {topics_str}
    {pdf_section}
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
    pdf_context = data.get('pdfContext', '')
    
    if not (chosen_song and song_lyrics and selected_topics):
        return jsonify({"error": "Missing required fields"}), 400
    
    if not math_concept and not pdf_context:
        return jsonify({"error": "Please provide a math concept or PDF context"}), 400
    
    parody_lyrics = generate_parody_lyrics(math_concept, level, focus_slider, selected_topics, chosen_song, song_lyrics, pdf_context)
    
    return jsonify({"parodyLyrics": parody_lyrics})


if __name__ == '__main__':
    app.run(port=8000, debug=True)
