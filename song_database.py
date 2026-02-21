# Mock song database for demo purposes
SONGS = [
    {
        "title": "Bohemian Rhapsody",
        "artist": "Queen",
        "lyrics": "Is this the real life? Is this just fantasy?..."
    },
    {
        "title": "Imagine",
        "artist": "John Lennon",
        "lyrics": "Imagine there's no heaven, it's easy if you try..."
    },
    {
        "title": "Hey Jude",
        "artist": "The Beatles",
        "lyrics": "Hey Jude, don't make it bad, take a sad song and make it better..."
    },
    {
        "title": "Let It Go",
        "artist": "Idina Menzel",
        "lyrics": "Let it go, let it go, can't hold it back anymore..."
    },
    {
        "title": "Shape of You",
        "artist": "Ed Sheeran",
        "lyrics": "The club isn't the best place to find a lover..."
    }
]

def search_songs_by_title(query):
    query = query.lower()
    return [
        {"title": song["title"], "artist": song["artist"]}
        for song in SONGS if query in song["title"].lower()
    ]

def get_song_by_title(title):
    for song in SONGS:
        if song["title"].lower() == title.lower():
            return song
    return None

def get_song_lyrics(title):
    song = get_song_by_title(title)
    return song["lyrics"] if song else None
