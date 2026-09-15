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
from ui.theme import format_time, make_progress_bar, make_volume_bar
from ui.embeds import (
    create_now_playing_embed,
    create_queue_embed,
    create_search_results_embed,
    create_settings_embed,
    create_help_embed,
    create_support_embed,
    create_nothing_playing_embed,
    create_queue_empty_embed,
    create_invalid_search_embed,
    create_track_queued_embed
)

def run_tests():
    print("--- 1. Testing Library Scanner ---")
    library.reload()
    tracks = library.get_all()
    print(f"Discovered {len(tracks)} tracks:")
    for t in tracks:
        print(f"  • {t['title']} | Artist: {t['artist']} | Duration: {format_time(t['duration'])} ({t['duration']:.1f}s)")
    assert len(tracks) == 5, f"Expected 5 tracks, found {len(tracks)}"

    print("\n--- 2. Testing Search Function ---")
    results = library.search("blues")
    assert len(results) >= 1, "Expected search for 'blues' to return results"
    print(f"Search for 'blues': {[r['title'] for r in results]}")

    results_carnaval = library.search("carnaval")
    assert len(results_carnaval) >= 1, "Expected search for 'carnaval' to return results"
    print(f"Search for 'carnaval': {[r['title'] for r in results_carnaval]}")

    print("\n--- 3. Testing Visual Sliders & Progress Bars ---")
    prog = make_progress_bar(102, 217)  # ~1:42 of 3:37
    print(f"Progress bar (1:42 / 3:37): {prog}")
    vol = make_volume_bar(0.70)
    print(f"Volume bar (70%): {vol}")

    print("\n--- 4. Testing Embed Generation ---")
    first_track = Track(
        title=tracks[0]["title"],
        artist=tracks[0]["artist"],
        duration=tracks[0]["duration"],
        filepath=tracks[0]["filepath"],
        requester=None
    )

    np_embed = create_now_playing_embed(first_track, elapsed=45.0)
    print("✓ Now Playing embed created")
    queue_embed = create_queue_embed([first_track], current=first_track, page=1)
    print("✓ Queue embed created")
    search_embed = create_search_results_embed("vibes", tracks)
    print("✓ Search embed created")
    settings_embed = create_settings_embed(0.70, "off", False)
    print("✓ Settings embed created")
    help_embed = create_help_embed()
    print("✓ Help embed created")
    support_embed = create_support_embed()
    print("✓ Support embed created")
    alert1 = create_nothing_playing_embed()
    alert2 = create_queue_empty_embed()
    alert3 = create_invalid_search_embed("xyz123")
    alert4 = create_track_queued_embed(first_track, position=1)
    print("✓ All 4 alert embeds created successfully!")

    print("\nALL OFFLINE TESTS PASSED PERFECTLY!")

if __name__ == "__main__":
    run_tests()
