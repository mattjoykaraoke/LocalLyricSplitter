import re
import urllib.parse
import urllib.request
import os

import pyphen
import requests
from bs4 import BeautifulSoup
from PySide6.QtCore import QThread, Signal
from PySide6.QtGui import QIcon

class LyricFetchWorker(QThread):
    """Threaded worker to prevent UI freezing during network requests."""

    success = Signal(str, str)  # Added second string for the source name
    failure = Signal(str)

    def __init__(self, artist, title):
        super().__init__()
        self.artist = artist.strip()
        self.title = title.strip()
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }

    def run(self):
        try:
            # 1. Genius Search & Scrape
            lyrics = self.fetch_genius()
            if lyrics:
                self.success.emit(lyrics, "Genius")
                return

            # 2. AZLyrics Backup
            lyrics = self.fetch_azlyrics()
            if lyrics:
                self.success.emit(lyrics, "AZLyrics")
                return

            # 3. LRCLIB Open API Backup (Highly reliable for popular songs)
            lyrics = self.fetch_lrclib_fallback()
            if lyrics:
                self.success.emit(lyrics, "LRCLIB")
                return

            self.failure.emit("Lyrics not found on Genius, AZLyrics, or LRCLIB.")
        except Exception as e:
            self.failure.emit(f"Connection error: {str(e)}")

    def fetch_genius(self):
        try:
            query = f"{self.artist} {self.title}".replace(" ", "%20")
            url = f"https://genius.com/api/search/multi?q={query}"
            response = requests.get(url, headers=self.headers, timeout=10)
            data = response.json()

            for section in data["response"]["sections"]:
                if section["type"] == "top_hit" and section["hits"]:
                    song_url = section["hits"][0]["result"]["url"]
                    page = requests.get(song_url, headers=self.headers, timeout=10)
                    soup = BeautifulSoup(page.text, "html.parser")

                    lyrics_divs = soup.select('div[class^="Lyrics__Container"]')
                    if lyrics_divs:
                        return "\n".join(
                            [d.get_text(separator="\n") for d in lyrics_divs]
                        )
            return None
        except Exception:
            return None

    def fetch_azlyrics(self):
        try:
            clean_artist = re.sub(r"[^a-z0-9]", "", self.artist.lower())
            clean_title = re.sub(r"[^a-z0-9]", "", self.title.lower())
            url = f"https://www.azlyrics.com/lyrics/{clean_artist}/{clean_title}.html"

            response = requests.get(url, headers=self.headers, timeout=10)
            soup = BeautifulSoup(response.text, "html.parser")

            comment = soup.find(
                string=lambda text: (
                    "Usage of azlyrics.com content" in text if text else False
                )
            )
            if comment:
                return comment.find_next("div").get_text().strip()
            return None
        except Exception:
            return None

    def fetch_lrclib_fallback(self):
        """Replaces Google scrape with a robust, free open-source lyrics API."""
        try:
            query = f"{self.artist} {self.title}"
            url = f"https://lrclib.net/api/search?q={urllib.parse.quote(query)}"

            response = requests.get(url, headers=self.headers, timeout=10)
            if response.status_code == 200:
                data = response.json()
                if data and len(data) > 0:
                    # Grab the plain lyrics from the first result
                    lyrics = data[0].get("plainLyrics")
                    if lyrics:
                        return lyrics
            return None
        except Exception:
            return None

class IconFetchWorker(QThread):
    """Threaded worker to download country flag icons without freezing UI."""
    success = Signal(str, str) # country_code, icon_path
    
    def __init__(self, country_code, icon_path):
        super().__init__()
        self.country_code = country_code
        self.icon_path = icon_path

    def run(self):
        if not os.path.exists(self.icon_path):
            try:
                url = f"https://flagcdn.com/w20/{self.country_code}.png"
                urllib.request.urlretrieve(url, self.icon_path)
                self.success.emit(self.country_code, self.icon_path)
            except Exception:
                pass
        else:
            self.success.emit(self.country_code, self.icon_path)

class PyphenLoadWorker(QThread):
    """Threaded worker to initialize Pyphen dictionary asynchronously."""
    success = Signal(object) # pyphen instance

    def __init__(self, lang_code):
        super().__init__()
        self.lang_code = lang_code

    def run(self):
        dic = pyphen.Pyphen(lang=self.lang_code)
        self.success.emit(dic)
