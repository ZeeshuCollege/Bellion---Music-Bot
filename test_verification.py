import sys
import io
import asyncio
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))

import discord
from discord.ext import commands
from music.library import library
from music.track import Track
from ui.views import (
    NowPlayingLayoutView, QueueLayoutView, SearchLayoutView, 
    StatusLayoutView, HelpDashboardLayoutView, SettingsLayoutView
)
from ui.image_generator import generate_ping_card

class DummyPlayer:
    def __init__(self, current=None):
        self.current = current
        self.queue = []
        self.is_paused = False
        self.loop_mode = "off"
        self.volume = 0.70
        self.autoplay = False
        self.guild = None

def run_tests():
    print("--- 1. Testing Library Scanner ---")
    library.reload()
    tracks = library.get_all()
    print(f"Discovered {len(tracks)} tracks:")
    print(f"Local tracks discovered: {len(tracks)} (Online YouTube streaming is now the primary audio source).")

    print("\n--- 2. Testing Discord Components V2 LayoutViews ---")
    dummy_track = Track(
        title="snowfall (Slowed + Reverb)",
        artist="Øneheart",
        duration=151.0,
        filepath="dummy.mp3",
        requester=None
    )
    player = DummyPlayer(current=dummy_track)

    # Now Playing V2 View
    np_view = NowPlayingLayoutView(player)
    assert np_view.has_components_v2(), "NowPlayingLayoutView should have components_v2 = True"
    print("✓ NowPlayingLayoutView constructed successfully with Components V2!")
    components_json = np_view.to_components()
    assert len(components_json) > 0
    print(f"✓ NowPlayingLayoutView root component type: {components_json[0]['type']} (Container)")

    # Queue V2 View
    queue_view = QueueLayoutView(player, current_page=1)
    assert queue_view.has_components_v2(), "QueueLayoutView should have components_v2 = True"
    print("✓ QueueLayoutView constructed successfully with Components V2!")

    # Search V2 View
    search_view = SearchLayoutView(player, tracks, user=None, query="test")
    assert search_view.has_components_v2(), "SearchLayoutView should have components_v2 = True"
    print("✓ SearchLayoutView constructed successfully with Components V2!")

    # Status V2 View
    status_view = StatusLayoutView(
        title="### 🎵 Nothing is playing",
        description="Use `,play` to start a song."
    )
    assert status_view.has_components_v2(), "StatusLayoutView should have components_v2 = True"
    print("✓ StatusLayoutView constructed successfully with Components V2!")

    # Help Dashboard V2 View with all modules
    for mod in ["overview", "music", "queue", "utility"]:
        help_view = HelpDashboardLayoutView(current_module=mod)
        assert help_view.has_components_v2(), f"HelpDashboardLayoutView ({mod}) should have components_v2 = True"
    print("✓ HelpDashboardLayoutView modules (overview, music, queue, utility) constructed successfully!")

    # Settings V2 View
    settings_view = SettingsLayoutView(player)
    assert settings_view.has_components_v2(), "SettingsLayoutView should have components_v2 = True"
    print("✓ SettingsLayoutView constructed successfully!")

    print("\n--- 3. Testing Image Ping Generator ---")
    img_buf = generate_ping_card(42, guild_count=5)
    assert img_buf is not None and img_buf.getbuffer().nbytes > 1000
    print(f"✓ Ping card generated successfully! Size: {img_buf.getbuffer().nbytes} bytes")

    print("\n--- 4. Testing Bot Cogs and Prefix Commands ---")
    async def test_bot_setup():
        intents = discord.Intents.default()
        intents.message_content = True
        bot = commands.Bot(command_prefix=",", intents=intents, help_command=None)
        
        await bot.load_extension("cogs.music")
        await bot.load_extension("cogs.utility")

        expected_commands = [
            "play", "pause", "resume", "skip", "stop",
            "queue", "clear", "shuffle", "loop", "autoplay",
            "help", "ping", "invite", "support"
        ]

        registered = [c.name for c in bot.commands]
        print(f"Registered Prefix Commands ({len(registered)}): {', '.join(registered)}")

        for cmd in expected_commands:
            assert cmd in registered, f"Missing required prefix command: ,{cmd}"
            print(f"  ✓ ,{cmd} registered")

        print("✓ All 14 requested prefix commands verified!")

        # Verify Aliases
        expected_aliases = {
            "p": "play",
            "s": "skip",
            "dc": "stop",
            "disconnect": "stop",
            "leave": "stop"
        }
        for alias, target_cmd in expected_aliases.items():
            cmd = bot.get_command(alias)
            assert cmd is not None, f"Alias ,{alias} not found!"
            assert cmd.name == target_cmd, f"Alias ,{alias} resolves to {cmd.name}, expected {target_cmd}"
            print(f"  ✓ Alias ,{alias} -> ,{target_cmd} verified!")

    asyncio.run(test_bot_setup())

    print("\nALL VERIFICATION TESTS COMPLETED SUCCESSFULLY!")

if __name__ == "__main__":
    run_tests()

