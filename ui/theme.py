"""
Design tokens, color schemes, progress bar generators, and styling utilities for Bellion Music Bot.
Faithfully designed to mirror the reference UI aesthetics.
"""

# Color Palette
COLOR_PRIMARY = 0x2F72F6   # Electric Bellion Blue (Now Playing, Main Actions)
COLOR_QUEUE = 0x5A4FCF     # Deep Indigo / Violet (Queue card)
COLOR_SETTINGS = 0x2B2D31  # Sleek Dark Slate (Settings card)
COLOR_SUCCESS = 0x2ECC71   # Vibrant Emerald (Track Queued)
COLOR_WARNING = 0xE67E22   # Warm Amber (Invalid search, notices)
COLOR_INFO = 0x3498DB      # Sky Blue (Nothing is playing, informational)
COLOR_ERROR = 0xE74C3C     # Ruby Red (Errors)

# Symbols & Waveforms
WAVEFORM = "• ılıılılılılılı •"
WAVEFORM_SHORT = "ılı.lıllılı"

# Custom Animated & Static Emojis
EMOJI_MUSIC_DISC = "<a:A_BlackMusicDisc1:1549669055059726466>"
EMOJI_WHITE_ARROW = "<a:A_WhiteArrow1:1549464015628148886>"
EMOJI_HEADSET = "<a:A_Headset1:1549710667353817178>"
EMOJI_PAUSE = "<a:A_Pause1:1549711772519505973>"
EMOJI_SKIP = "<:S_Skip1:1549712968420163664>"
EMOJI_QUEUE = "<a:A_Queue1:1549713445568512000>"
EMOJI_SETTINGS = "<a:A_Settings1:1549714680824733716>"
EMOJI_PREVIOUS = "<a:A_Previous1:1549755145854652456>"
EMOJI_STOP = "<a:A_Stop1:1549755152234184724>"
EMOJI_SHUFFLE = "<a:A_Shuffle1:1549755160027340865>"
EMOJI_LOOP = "<a:A_Loop1:1549755166734032926>"
EMOJI_TRASH = "<a:A_Trash1:1549755173180670052>"
EMOJI_VOLUME = "<a:A_Volume1:1549755179686043719>"
EMOJI_MUSICNOTE = "<a:A_MusicNote1:1549755186484875367>"
EMOJI_WARNING = "<a:A_Warning1:1549755194764693514>"
EMOJI_FILTER = "<a:A_Filter1:1549755204558397557>"
EMOJI_SPARKLES = "<a:A_Sparkles1:1549755210740539535>"
EMOJI_SEARCH = "<a:A_Search1:1549755217908736030>"
EMOJI_CROSS = "<a:A_Cross1:1549755224422621224>"

def format_time(seconds: float) -> str:
    """Format seconds into M:SS or H:MM:SS."""
    if not seconds or seconds < 0:
        return "0:00"
    total_seconds = int(seconds)
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    secs = total_seconds % 60
    if hours > 0:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"

def make_progress_bar(current: float, total: float, length: int = 14) -> str:
    """
    Generate a modern sleek progress bar matching reference screenshot:
    e.g. 1:42 ━━━━━━●──────── 3:37
    """
    if total <= 0:
        total = 1.0
    progress = max(0.0, min(1.0, current / total))
    dot_pos = int(progress * (length - 1))
    
    bar_chars = []
    for i in range(length):
        if i == dot_pos:
            bar_chars.append("●")
        else:
            bar_chars.append("━")
            
    bar_str = "".join(bar_chars)
    return f"`{format_time(current)}` {bar_str} `{format_time(total)}`"

def make_volume_bar(volume: float, length: int = 10) -> str:
    """
    Generate a volume slider display matching reference screenshot:
    e.g. [ ━━━━━━━●─── ] 70%
    """
    volume = max(0.0, min(1.0, volume))
    dot_pos = int(volume * (length - 1))
    
    bar_chars = []
    for i in range(length):
        if i == dot_pos:
            bar_chars.append("●")
        else:
            bar_chars.append("━")
            
    pct = int(volume * 100)
    return f"[ {''.join(bar_chars)} ] {pct}%"
