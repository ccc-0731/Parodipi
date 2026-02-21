import os
import pandas as pd

def load_songs_from_csv(file_path):
    # Load songs from a CSV file into a pandas dataframe.
    # Columns: 'artist', 'song', 'lyrics'
    try:
        df = pd.read_csv(file_path)
        return df
    except Exception as e:
        print(f"Error loading songs from CSV: {e}")
        return []
    
def clean_song_lyrics(df):
    # Preprocessing: Remove parts in "lyrics" before "Read More"
    def clean_lyrics(lyrics):
        if pd.isna(lyrics):
            return ""
        if "Read More" in lyrics:
            return lyrics.split("Read More", 1)[1].strip()
        return lyrics.strip()
    
    df['lyrics'] = df['lyrics'].apply(clean_lyrics)
    return df

def search_songs(query, mode='title'):
    if not isinstance(query, str) or songs_df is None or songs_df.empty:
        return []
    if mode == 'lyrics':
        mask = songs_df['lyrics'].str.contains(query, case=False, na=False)
    else:
        mask = songs_df['song'].str.contains(query, case=False, na=False)
    results = songs_df[mask][['song', 'artist']].head(20)
    return [
        {"title": row['song'], "artist": row['artist']} for _, row in results.iterrows()
    ]

def get_song_lyrics(song_title):
    if not isinstance(song_title, str) or songs_df is None or songs_df.empty:
        return None
    song_row = songs_df[songs_df['song'].str.lower() == song_title.lower()]
    if not song_row.empty:
        return song_row.iloc[0]['lyrics']
    return None

SONGS_CSV_PATH = os.getenv('SONGS_CSV_PATH', 'songs.csv')
songs_df = load_songs_from_csv(SONGS_CSV_PATH)
songs_df = clean_song_lyrics(songs_df)

if __name__ == '__main__':
    # Test
    songs_df = load_songs_from_csv('songs.csv')
    clean_song_lyrics(songs_df)


    print(songs_df.head())