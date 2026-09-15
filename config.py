import os
from pathlib import Path
from dotenv import load_dotenv

# Base Directory of the Project
BASE_DIR = Path(__file__).resolve().parent

# Load environment variables
load_dotenv(dotenv_path=BASE_DIR / ".env")

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN", "").strip()
MASTER_ID = int(os.getenv("MASTER_ID", "0")) if os.getenv("MASTER_ID", "").strip().isdigit() else 0

# Media Assets
LOGO_PATH = BASE_DIR / "Logo.png"
BANNER_PATH = BASE_DIR / "Banner.png"

# Default Bot Settings
DEFAULT_VOLUME = 0.70  # 70%
DEFAULT_LOOP = "off"   # off, track, queue
DEFAULT_AUTOPLAY = False
SUPPORT_SERVER_URL = "https://discord.gg/bellion"
BOT_NAME = "Bellion"
BOT_PREFIX = ","

# Components V2 Branding
POWERED_BY_TEXT = "Powered by [NexCloud Host | Fast & Reliable](https://nexcloud.host)"

# Thematic dark artworks matching reference screenshot
DEFAULT_THUMBNAILS = {
    "dark": "https://images.unsplash.com/photo-1518709268805-4e9042af9f23?w=500&auto=format&fit=crop&q=80",
    "blues": "https://images.unsplash.com/photo-1511671782779-c97d3d27a1d4?w=500&auto=format&fit=crop&q=80",
    "carnaval": "https://images.unsplash.com/photo-1514525253161-7a46d19cd819?w=500&auto=format&fit=crop&q=80",
    "foot ball": "https://images.unsplash.com/photo-1508098682722-e99c43a406b2?w=500&auto=format&fit=crop&q=80",
    "wonders": "https://images.unsplash.com/photo-1451187580459-43490279c0fa?w=500&auto=format&fit=crop&q=80",
    "default": "https://images.unsplash.com/photo-1518709268805-4e9042af9f23?w=500&auto=format&fit=crop&q=80"
}

def get_track_thumbnail(title: str, artist: str = "") -> str:
    combined = f"{title} {artist}".lower()
    for key, url in DEFAULT_THUMBNAILS.items():
        if key in combined:
            return url
    return DEFAULT_THUMBNAILS["default"]
