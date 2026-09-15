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
