import requests
import csv
from bs4 import BeautifulSoup

# To use this program, you have to have a token from Genius.com
# Go to https://docs.genius.com/#/search-h2 to get one.

def _get(path, params=None, headers=None):

    # generate request URL
    requrl = '/'.join(['https://api.genius.com', path])
    token = 'Bearer ' + 'eNiMoHSrndeJNsOLHq_RTBXiY8iLywwkd_sVB9wHa9MW8OrIm7-U_f_bt5ApoW9G'
    if headers:
        headers['Authorization'] = token
    else:
        headers = {"Authorization": token}

    response = requests.get(url=requrl, params=params, headers=headers)
    response.raise_for_status()

    return response.json()


def get_artist_songs(artist_id, song_urls_dict, song_titles, max_songs=50):
    # initialize variables & a list.
    current_page = 1
    next_page = True
    song_count = 0
    progress = True
    song_urls = []

    # main loop
    while next_page:

        path = "artists/{}/songs/".format(artist_id)
        params = {'page': current_page, 'sort': 'popularity'}
        data = _get(path=path, params=params)
        page_songs = data['response']['songs']
        if page_songs and song_count < max_songs: # don't go to next page if we've reached max songs
            for song in page_songs:
                if song_count < max_songs: # don't look for more songs on page if we've reached max songs
                    if song_count % 10 == 0 and progress:
                        print(str((song_count / max_songs) * 100) + ' percent complete.')
                    if song['primary_artist']['id'] == artist_id and song['title'] == song['title_with_featured']: # collects only songs made 100% by the artist
                        song_urls_dict[song['url']] = song['primary_artist']['name']
                        song_titles.append(song['title'])
                        song_urls.append(song['url'])
                        song_count += 1
                        progress = True
                    else:
                        progress = False
                else:
                    print('100.0 percent complete')
                    break
            current_page += 1
        else:
            next_page = False
    return song_urls


def scrap_song_url(url):
    page = requests.get(url)
    html = BeautifulSoup(page.text, 'html.parser')

    # Try the modern Genius layout first (data-lyrics-container divs)
    lyrics_containers = html.find_all('div', attrs={'data-lyrics-container': 'true'})
    if lyrics_containers:
        lyrics_parts = []
        for container in lyrics_containers:
            # Replace <br> tags with newlines before extracting text
            for br in container.find_all('br'):
                br.replace_with('\n')
            lyrics_parts.append(container.get_text())
        lyrics = '\n'.join(lyrics_parts)
    else:
        # Fallback to the old layout
        lyrics_div = html.find('div', class_='lyrics')
        if lyrics_div:
            lyrics = lyrics_div.get_text()
        else:
            lyrics = '[Lyrics not found]'

    return lyrics


def getArtistIDs(artist_names):
    artist_ids = []
    for name in artist_names:
        find_id = _get("search", {'q': name})
        for hit in find_id["response"]["hits"]:
           if hit["result"]["primary_artist"]["name"].lower() == name.lower():
               artist_ids.append(hit["result"]["primary_artist"]["id"])
               break
    return artist_ids


def createCSV(artist_names, max_songs=50, separated=False, csv_filename=None):
    if len(artist_names) == 0:
        print('No names entered.')
        return ''
    song_urls_and_artist = {}
    song_titles = []
    song_urls = []
    print('Getting artist ids...')
    artist_ids = getArtistIDs(artist_names)
    for i in range(len(artist_ids)):
        print(artist_names[i] + ': ' + str(artist_ids[i]))
    for i in range(len(artist_ids)):
        print("Getting songs for " + artist_names[i])
        song_urls += get_artist_songs(artist_ids[i], song_urls_and_artist, song_titles)

    # Use provided filename or generate one
    if csv_filename is None:
        if len(artist_names) == 1:
            csv_filename = artist_names[0] + '.csv'
        elif len(artist_names) == 2:
            csv_filename = artist_names[0] + '_' + artist_names[1] + '.csv'
        elif len(artist_names) == 3:
            csv_filename = artist_names[0] + '_' + artist_names[1] + '_' + artist_names[2] + '.csv'
        else:
            csv_filename = artist_names[0] + '_' + artist_names[1] + '_' + artist_names[2] + '_and_more.csv'

    # Check if file already exists; if not, write header
    import os
    file_exists = os.path.isfile(csv_filename)
    if not file_exists:
        print('Creating ' + csv_filename + '...')
        with open(csv_filename, 'w', newline='') as csvFile:
            writer = csv.writer(csvFile)
            writer.writerow(['artist', 'song', 'lyrics'])
    else:
        print('Appending to ' + csv_filename + '...')

    # Append lyrics to file
    song_count = 0
    with open(csv_filename, 'a', newline='') as csvFile:
        writer = csv.writer(csvFile)
        for i in range(len(song_urls)):
            if song_count % 10 == 0:
                print(str((song_count / len(song_urls)) * 100) + ' percent complete.')
            row = [song_urls_and_artist[song_urls[i]], song_titles[i], scrap_song_url(song_urls[i])]
            writer.writerow(row)
            song_count += 1
    print('100.0 percent complete')
    print('Enjoy your dataset!')
    return csv_filename


csv_filename = None

while True:
    artist_names = []
    max_songs = 50
    artist_count = input('How many artists would you like to download lyrics from? ')
    i = 0
    while i < int(artist_count):
        artist_names.append(input('Enter the name of artist ' + str(i+1) + ': '))
        i += 1
    max_songs = int(input('How many songs per artist? (50 is the default): '))

    # First run: ask for filename; subsequent runs: reuse it
    if csv_filename is None:
        csv_filename = input('Enter a name for the CSV file (without .csv): ') + '.csv'

    csv_filename = createCSV(artist_names, max_songs, csv_filename=csv_filename)

    again = input('\nWould you like to add more artists? (yes/no): ')
    if again.lower() not in ('yes', 'y'):
        print('Done! Your dataset is saved in ' + csv_filename)
        break