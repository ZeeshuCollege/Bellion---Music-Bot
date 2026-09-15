import os
from pathlib import Path
from typing import List, Optional
import mutagen
from config import BASE_DIR

class AudioLibrary:
    """
    Scans and manages local audio tracks.
    Provides fast fuzzy searching and autocomplete choices for slash commands.
    """
    def __init__(self, directory: Path = BASE_DIR):
        self.directory = directory
        self._tracks: List[dict] = []
        self.reload()

    def reload(self):
        """Scans the directory for all audio files and extracts metadata."""
        self._tracks.clear()
        extensions = {".mp3", ".wav", ".ogg", ".flac", ".m4a"}
        
        # Scan root directory for audio files
        for entry in os.scandir(self.directory):
            if entry.is_file():
                ext = Path(entry.name).suffix.lower()
                if ext in extensions:
                    self._load_file(Path(entry.path))

    def _load_file(self, path: Path):
        filename_stem = path.stem
        title = filename_stem
        artist = "Bellion Originals"
        duration = 0.0

        try:
            audio = mutagen.File(str(path))
            if audio is not None:
                if audio.info and hasattr(audio.info, "length"):
                    duration = float(audio.info.length)
                
                # Check tags if available
                if audio.tags:
                    if "TIT2" in audio.tags:
                        title = str(audio.tags["TIT2"])
                    elif "title" in audio.tags:
                        title = str(audio.tags["title"][0])

                    if "TPE1" in audio.tags:
                        artist = str(audio.tags["TPE1"])
                    elif "artist" in audio.tags:
                        artist = str(audio.tags["artist"][0])
        except Exception:
            pass

        # Beautiful default artists if untagged
        if artist == "Bellion Originals":
            if "Carnaval" in title:
                artist = "Rio Beats"
            elif "Blues" in title:
                artist = "Jazz & Blues Lounge"
            elif "Dark" in title:
                artist = "Cinematic Ambient"
            elif "Foot Ball" in title:
                artist = "Stadium Anthems"
            elif "Wonders" in title:
                artist = "Nature Symphony"

        self._tracks.append({
            "title": title,
            "artist": artist,
            "duration": duration,
            "filepath": str(path.resolve()),
            "filename": path.name
        })

    def get_all(self) -> List[dict]:
        return list(self._tracks)

    def search(self, query: str, limit: int = 5) -> List[dict]:
        """
        Fuzzy search for audio tracks matching a query.
        Returns top matching tracks.
        """
        if not self._tracks:
            self.reload()

        cleaned_query = query.strip().lower()
        if not cleaned_query:
            return self._tracks[:limit]

        # Score matching: exact match, prefix match, substring match
        scored = []
        for track in self._tracks:
            t_title = track["title"].lower()
            t_artist = track["artist"].lower()
            t_file = track["filename"].lower()

            score = 0
            if cleaned_query == t_title or cleaned_query == t_file:
                score += 100
            elif t_title.startswith(cleaned_query):
                score += 50
            elif cleaned_query in t_title:
                score += 30
            elif cleaned_query in t_artist:
                score += 20
            elif any(word in t_title for word in cleaned_query.split()):
                score += 10

            if score > 0:
                scored.append((score, track))

        scored.sort(key=lambda x: x[0], reverse=True)
        results = [item[1] for item in scored]
        
        # If no strict match, fallback to returning partial or all if query is broad
        if not results:
            for track in self._tracks:
                if any(part in track["title"].lower() for part in cleaned_query.split()):
                    results.append(track)

        return results[:limit]

# Singleton instance
library = AudioLibrary()
