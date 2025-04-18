import requests
from bs4 import BeautifulSoup

class LyricsFetcher:
    def __init__(self, artist, song):
        self.artist = artist
        self.song = song

    def fetch_lyrics(self):
        try:
            artist_name = self.artist.lower().replace(" ", "")
            song_title = self.song.lower().replace(" ", "")
            url = f"https://www.azlyrics.com/lyrics/{artist_name}/{song_title}.html"
            headers = {'User-Agent': 'Mozilla/5.0'}

            response = requests.get(url, headers=headers)
            soup = BeautifulSoup(response.text, 'html.parser')

            # AZLyrics lyrics are in the 5th div after the first div with class 'col-xs-12 col-lg-8 text-center'
            divs = soup.find_all("div", class_=False, id=False)
            if len(divs) >= 5:
                lyrics = divs[4].get_text(separator="\n").strip()
                return lyrics
            else:
                return "Lyrics not found. Please check artist and song title."
        except Exception as e:
            return f"Error fetching lyrics: {str(e)}"
