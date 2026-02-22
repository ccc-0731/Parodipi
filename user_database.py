import csv
import hashlib
import os
import uuid
from datetime import datetime

USERS_CSV = os.path.join(os.path.dirname(__file__), 'users.csv')
PARODIES_CSV = os.path.join(os.path.dirname(__file__), 'saved_parodies.csv')

# ===== USER MANAGEMENT =====

def _ensure_users_csv():
    if not os.path.exists(USERS_CSV):
        with open(USERS_CSV, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['user_id', 'username', 'password_hash', 'created_at'])

def _hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def create_user(username, password):
    """Create a new user. Returns (user_id, error_message)."""
    _ensure_users_csv()
    
    # Check if username already exists
    with open(USERS_CSV, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row['username'].lower() == username.lower():
                return None, "Username already exists"
    
    user_id = str(uuid.uuid4())[:8]
    with open(USERS_CSV, 'a', newline='') as f:
        writer = csv.writer(f)
        writer.writerow([user_id, username, _hash_password(password), datetime.now().isoformat()])
    
    return user_id, None

def authenticate_user(username, password):
    """Check credentials. Returns (user_id, error_message)."""
    _ensure_users_csv()
    
    with open(USERS_CSV, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row['username'].lower() == username.lower():
                if row['password_hash'] == _hash_password(password):
                    return row['user_id'], None
                else:
                    return None, "Incorrect password"
    
    return None, "User not found"

def create_guest_user():
    """Create a temporary guest user. Returns user_id."""
    return f"guest-{str(uuid.uuid4())[:6]}"

# ===== PARODY STORAGE =====

def _ensure_parodies_csv():
    if not os.path.exists(PARODIES_CSV):
        with open(PARODIES_CSV, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                'parody_id', 'user_id', 'math_concept', 'level', 'topics',
                'song_title', 'artist', 'parody_title', 'parody_lyrics',
                'original_lyrics', 'created_at'
            ])

def save_parody(user_id, math_concept, level, topics, song_title, artist,
                parody_title, parody_lyrics, original_lyrics):
    """Save a generated parody to the CSV. Returns parody_id."""
    _ensure_parodies_csv()
    
    parody_id = str(uuid.uuid4())[:8]
    topics_str = "|".join(topics) if isinstance(topics, list) else str(topics)
    
    with open(PARODIES_CSV, 'a', newline='') as f:
        writer = csv.writer(f)
        writer.writerow([
            parody_id, user_id, math_concept, level, topics_str,
            song_title, artist, parody_title, parody_lyrics,
            original_lyrics, datetime.now().isoformat()
        ])
    
    return parody_id

def get_user_parodies(user_id):
    """Get all saved parodies for a user. Returns list of dicts."""
    _ensure_parodies_csv()
    
    parodies = []
    with open(PARODIES_CSV, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row['user_id'] == user_id:
                row['topics'] = row['topics'].split('|') if row['topics'] else []
                parodies.append(dict(row))
    
    # Most recent first
    parodies.reverse()
    return parodies

def delete_parody(user_id, parody_id):
    """Delete a saved parody. Returns True if deleted."""
    _ensure_parodies_csv()
    
    rows = []
    deleted = False
    with open(PARODIES_CSV, 'r') as f:
        reader = csv.DictReader(f)
        headers = reader.fieldnames
        for row in reader:
            if row['parody_id'] == parody_id and row['user_id'] == user_id:
                deleted = True
            else:
                rows.append(row)
    
    if deleted:
        with open(PARODIES_CSV, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=headers)
            writer.writeheader()
            writer.writerows(rows)
    
    return deleted
