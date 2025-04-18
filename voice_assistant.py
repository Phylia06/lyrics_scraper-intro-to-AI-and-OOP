import re

class VoiceAssistant:
    def __init__(self, transcript):
        self.transcript = transcript
        self.artist = ""
        self.song = ""

    def parse(self):
        # Regex pattern: capture phrases like "Shape of You by Ed Sheeran"
        pattern = re.search(r"(.+?)\s+by\s+(.+)", self.transcript, re.IGNORECASE)
        if pattern:
            self.song = pattern.group(1).strip()
            self.artist = pattern.group(2).strip()
        return self.artist, self.song
