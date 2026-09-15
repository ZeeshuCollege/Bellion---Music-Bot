import asyncio
from typing import Optional
import discord
import yt_dlp
from config import BASE_DIR
from music.track import Track

async def resolve_url_track(query_or_url: str, requester: Optional[discord.Member | discord.User] = None) -> Optional[Track]:
    """
    Extracts stream audio information from a URL or search query using yt-dlp asynchronously.
    Supports YouTube, SoundCloud, direct audio links, and keyword search fallback.
    """
    target = query_or_url.strip()
    if not target.startswith(("http://", "https://")):
        target = f"ytsearch1:{target}"

    ydl_opts = {
        'format': 'bestaudio/best',
        'quiet': True,
        'no_warnings': True,
        'default_search': 'auto',
        'extract_flat': False,
        'noplaylist': True,
        'extractor_args': {
            'youtube': {
                'player_client': ['android', 'ios', 'web']
            }
        }
    }
    
    cookies_file = BASE_DIR / "cookies.txt"
    if cookies_file.exists():
        ydl_opts['cookiefile'] = str(cookies_file)
    
    loop = asyncio.get_running_loop()
    def _extract():
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            return ydl.extract_info(target, download=False)

    try:
        data = await loop.run_in_executor(None, _extract)
        if not data:
            return None

        # In case of search/playlist, pick the first entry
        if 'entries' in data and data['entries']:
            entries = [e for e in data['entries'] if e]
            if not entries:
                return None
            data = entries[0]

        title = data.get('title') or 'Web Audio Track'
        artist = data.get('uploader') or data.get('channel') or 'Online Stream'
        duration = float(data.get('duration') or 0.0)
        stream_url = data.get('url') or query_or_url
        thumbnail = data.get('thumbnail')

        return Track(
            title=title,
            artist=artist,
            duration=duration,
            filepath=stream_url,
            requester=requester,
            thumbnail_url=thumbnail,
            source_type='stream'
        )
    except Exception as e:
        print(f"Error extracting audio for '{query_or_url}': {e}")
        return None

async def resolve_related_track(title: str, artist: str = "") -> Optional[Track]:
    """
    Finds a related track on YouTube for seamless autoplay when queue ends.
    """
    query = f"ytsearch5:{title} {artist} mix"
    ydl_opts = {
        'format': 'bestaudio/best',
        'quiet': True,
        'no_warnings': True,
        'default_search': 'auto',
        'extract_flat': False,
        'noplaylist': True,
        'extractor_args': {
            'youtube': {
                'player_client': ['android', 'ios', 'web']
            }
        }
    }

    cookies_file = BASE_DIR / "cookies.txt"
    if cookies_file.exists():
        ydl_opts['cookiefile'] = str(cookies_file)

    loop = asyncio.get_running_loop()
    def _extract():
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            return ydl.extract_info(query, download=False)

    try:
        data = await loop.run_in_executor(None, _extract)
        if not data or 'entries' not in data or not data['entries']:
            return None

        # Filter out exact same title
        clean_target = title.lower()
        candidates = [e for e in data['entries'] if e and e.get('title') and clean_target not in e.get('title', '').lower()]
        pick = candidates[0] if candidates else data['entries'][0]

        return Track(
            title=pick.get('title') or 'Related Track',
            artist=pick.get('uploader') or pick.get('channel') or 'YouTube Music',
            duration=float(pick.get('duration') or 0.0),
            filepath=pick.get('url') or "",
            requester=None,
            thumbnail_url=pick.get('thumbnail'),
            source_type='stream'
        )
    except Exception as e:
        print(f"Autoplay resolution error: {e}")
        return None

