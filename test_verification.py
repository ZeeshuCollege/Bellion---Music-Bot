import sys
import io
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from music.library import library
from music.track import Track
from ui.views import NowPlayingLayoutView, QueueLayoutView, SearchLayoutView, StatusLayoutView

class DummyPlayer:
    def __init__(self, current=None):
        self.current = current
        self.queue = []
        self.is_paused = False
        self.loop_mode = "off"
        self.guild = None

def run_tests():
    print("--- 1. Testing Library Scanner ---")
    library.reload()
    tracks = library.get_all()
    print(f"Discovered {len(tracks)} tracks:")
    for t in tracks:
        print(f"  • {t['title']} | Artist: {t['artist']} | Duration: {int(t['duration'])}s")
    assert len(tracks) == 5, f"Expected 5 tracks, found {len(tracks)}"

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
    search_view = SearchLayoutView(player, tracks, None, query="test")
    assert search_view.has_components_v2(), "SearchLayoutView should have components_v2 = True"
    print("✓ SearchLayoutView constructed successfully with Components V2!")

    # Status V2 View
    status_view = StatusLayoutView(
        title="### 🎵 Nothing is playing",
        description="Use `/play` to start a song."
    )
    assert status_view.has_components_v2(), "StatusLayoutView should have components_v2 = True"
    print("✓ StatusLayoutView constructed successfully with Components V2!")

    print("\nALL DISCORD COMPONENTS V2 VERIFICATIONS PASSED!")

if __name__ == "__main__":
    run_tests()
