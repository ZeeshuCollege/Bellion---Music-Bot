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
DEFAULT_VOLUME = 0.70  # 70% as in reference UI
DEFAULT_LOOP = "off"   # off, track, queue
DEFAULT_AUTOPLAY = False
SUPPORT_SERVER_URL = "https://discord.gg/bellion"
BOT_NAME = "Bellion"
