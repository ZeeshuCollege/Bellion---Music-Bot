from typing import List, Optional
import discord
from music.track import Track
from ui.theme import (
    COLOR_PRIMARY,
    COLOR_QUEUE,
    COLOR_SETTINGS,
    COLOR_SUCCESS,
    COLOR_WARNING,
    COLOR_INFO,
    COLOR_ERROR,
    WAVEFORM,
    make_progress_bar,
    make_volume_bar,
    format_time
)
from config import BOT_NAME, SUPPORT_SERVER_URL

def create_now_playing_embed(track: Track, elapsed: float = 0.0, bot_avatar_url: Optional[str] = None) -> discord.Embed:
    """
    Constructs the Now Playing card matching the top-left panel of the reference UI.
    """
    embed = discord.Embed(
        title="🎶 Now Playing",
        color=COLOR_PRIMARY
    )
    
    progress_bar = make_progress_bar(elapsed, track.duration, length=14)
    requester_text = track.get_requester_display()

    description = (
        f"### {track.title}\n"
        f"*{track.artist}*\n\n"
        f"{progress_bar}\n\n"
        f"👤 **Requested by**: `{requester_text}`"
    )
    embed.description = description
    
    footer_kwargs = {"text": f"{BOT_NAME} Music Engine • Use buttons below to control"}
    if bot_avatar_url:
        footer_kwargs["icon_url"] = bot_avatar_url
    embed.set_footer(**footer_kwargs)
    
    if track.thumbnail_url:
        embed.set_thumbnail(url=track.thumbnail_url)
        
    return embed


def create_queue_embed(queue: List[Track], current: Optional[Track] = None, page: int = 1, per_page: int = 5) -> discord.Embed:
    """
    Constructs the Queue card matching the bottom-left of the first panel in reference UI.
    """
    embed = discord.Embed(
        title=f"🔢 Queue",
        color=COLOR_QUEUE
    )

    all_tracks = []
    if current:
        all_tracks.append(current)
    all_tracks.extend(queue)

    if not all_tracks:
        embed.description = "*The queue is currently empty. Add tracks using `/play`!*"
        return embed

    total_count = len(all_tracks)
    total_seconds = sum(t.duration for t in all_tracks)
    total_duration_str = format_time(total_seconds)
    
    # Calculate pages
    total_pages = max(1, (len(queue) + per_page - 1) // per_page) if queue else 1
    page = max(1, min(page, total_pages))

    embed.set_author(name=f"{total_count} Tracks | {total_duration_str} Total Duration")

    lines = []
    if current and page == 1:
        lines.append(f"**Now Playing:**")
        lines.append(f"▶ **{current.title}** • `{current.artist}` (`{current.formatted_duration}`) | 👤 `{current.get_requester_display()}`\n")
        if queue:
            lines.append(f"**Up Next:**")

    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page
    page_queue = queue[start_idx:end_idx]

    for i, track in enumerate(page_queue, start=start_idx + 1):
        lines.append(
            f"`{i}.` 🎵 **{track.title}**\n"
            f"   *{track.artist}* • `{track.formatted_duration}` | 👤 `{track.get_requester_display()}`"
        )

    embed.description = "\n".join(lines)
    embed.set_footer(text=f"Page {page}/{total_pages} • {len(queue)} in upcoming queue")
    return embed


def create_search_results_embed(query: str, tracks: List[dict]) -> discord.Embed:
    """
    Constructs the Search Results card matching top-right of reference UI.
    """
    embed = discord.Embed(
        title="🔍 Search Results",
        description=f"Showing top {len(tracks)} matches for: **`{query}`**\n",
        color=COLOR_PRIMARY
    )

    lines = []
    for idx, track in enumerate(tracks, start=1):
        duration_str = format_time(track.get("duration", 0.0))
        lines.append(
            f"**`[{idx}]`** 🎵 **{track['title']}**\n"
            f"   *{track['artist']}* • `{duration_str}`\n"
        )

    lines.append("ℹ *Select a track using the numbered buttons or dropdown below.*")
    embed.description += "\n".join(lines)
    embed.set_footer(text=f"{BOT_NAME} Search Service")
    return embed


def create_settings_embed(volume: float, loop_mode: str, autoplay: bool) -> discord.Embed:
    """
    Constructs the Settings card matching reference UI.
    """
    embed = discord.Embed(
        title="⚙ Settings",
        description="*Customize your listening experience*",
        color=COLOR_SETTINGS
    )

    vol_bar = make_volume_bar(volume, length=12)
    loop_display = {
        "off": "Off ⏹️",
        "track": "Single Track 🔂",
        "queue": "Entire Queue 🔁"
    }.get(loop_mode, loop_mode.capitalize())

    autoplay_display = "Enabled ✅" if autoplay else "Disabled ❌"

    embed.add_field(
        name="🔊 Volume",
        value=f"`{vol_bar}`",
        inline=False
    )
    embed.add_field(
        name="🔁 Loop Mode",
        value=f"`{loop_display}`",
        inline=True
    )
    embed.add_field(
        name="✨ Autoplay",
        value=f"`{autoplay_display}`",
        inline=True
    )

    embed.set_footer(text=f"{BOT_NAME} Settings • Interactive toggles below")
    return embed


def create_help_embed() -> discord.Embed:
    """
    Constructs the Command List card matching reference UI.
    """
    embed = discord.Embed(
        title="📜 Command List",
        description="*All commands support slash `/` and prefix `!`*",
        color=COLOR_PRIMARY
    )

    embed.add_field(
        name="🎵 Music",
        value=(
            "`/play <query>` - Play song with instant autocomplete\n"
            "`/search <query>` - Search & pick from top 5 matches\n"
            "`/pause` / `/resume` - Pause or resume playback\n"
            "`/skip` - Skip to next song in queue\n"
            "`/previous` - Replay the last played song\n"
            "`/stop` - Stop playback and clear the queue"
        ),
        inline=False
    )

    embed.add_field(
        name="📑 Queue",
        value=(
            "`/queue [page]` - View active playlist & track numbers\n"
            "`/nowplaying` - View interactive player card\n"
            "`/shuffle` - Shuffle upcoming songs\n"
            "`/clear` - Clear all pending songs in queue"
        ),
        inline=False
    )

    embed.add_field(
        name="🎛 Playback & Utility",
        value=(
            "`/volume <1-100>` - Set audio playback volume\n"
            "`/loop [off/track/queue]` - Cycle or set repeat mode\n"
            "`/settings` - Open interactive control dashboard\n"
            "`/help` - View this help documentation\n"
            "`/ping` - Check Discord Gateway latency"
        ),
        inline=False
    )

    embed.set_footer(text=f"{BOT_NAME} • Your Ultimate Audio Experience")
    return embed


def create_support_embed() -> discord.Embed:
    """
    Constructs the Help / Support card matching bottom reference UI.
    """
    embed = discord.Embed(
        title="❓ Help / Support",
        description="*Need help? We're here for you.*",
        color=COLOR_PRIMARY
    )

    embed.add_field(
        name="📖 Command Guide",
        value="View documentation and slash command tips.",
        inline=False
    )
    embed.add_field(
        name="⭐ Features",
        value="High-definition local & stream playback, real-time buttons, and queue persistence.",
        inline=False
    )
    embed.add_field(
        name="🌐 Support Server",
        value=f"Join our official community at [discord.gg/bellion]({SUPPORT_SERVER_URL})",
        inline=False
    )

    embed.set_footer(text="Bellion Support Center")
    return embed


# Alert Cards matching the reference UI
def create_nothing_playing_embed() -> discord.Embed:
    """Blue card: Nothing is playing."""
    embed = discord.Embed(
        title="🎵 Nothing is playing",
        description="Use `/play` to start a song.",
        color=COLOR_INFO
    )
    return embed


def create_queue_empty_embed() -> discord.Embed:
    """Deep indigo card: Queue is empty."""
    embed = discord.Embed(
        title="📑 Queue is empty",
        description="Add some tracks using `/play`.",
        color=COLOR_QUEUE
    )
    return embed


def create_invalid_search_embed(query: str) -> discord.Embed:
    """Amber/Red card: Invalid search."""
    embed = discord.Embed(
        title="⚠️ Invalid search",
        description=f"No results for **`{query}`**. Try a different keyword.",
        color=COLOR_WARNING
    )
    return embed


def create_track_queued_embed(track: Track, position: int) -> discord.Embed:
    """Vibrant emerald green card: Track Queued."""
    embed = discord.Embed(
        title="✅ Track Queued",
        color=COLOR_SUCCESS
    )
    embed.description = (
        f"🎵 **{track.title}**\n"
        f"*{track.artist}* • `{track.formatted_duration}`\n\n"
        f"📌 Position in queue: `#{position}`\n"
        f"*Added to queue successfully!*"
    )
    if track.thumbnail_url:
        embed.set_thumbnail(url=track.thumbnail_url)
    return embed
