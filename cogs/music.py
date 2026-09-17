from typing import List, Optional, Any
import discord
from discord import app_commands
from discord.ext import commands

from music.library import library
from music.track import Track
from music.player import PlayerManager
from music.resolver import resolve_url_track
from config import SUPPORT_SERVER_URL, get_track_thumbnail
from ui.theme import (
    EMOJI_HEADSET, EMOJI_PAUSE, EMOJI_SKIP, EMOJI_QUEUE, EMOJI_SETTINGS,
    EMOJI_PREVIOUS, EMOJI_STOP, EMOJI_SHUFFLE, EMOJI_LOOP, EMOJI_TRASH,
    EMOJI_VOLUME, EMOJI_MUSICNOTE, EMOJI_WARNING, EMOJI_FILTER, EMOJI_SPARKLES,
    EMOJI_SEARCH, EMOJI_CROSS
)
from ui.views import NowPlayingLayoutView, QueueLayoutView, SearchLayoutView, StatusLayoutView

class MusicCog(commands.Cog, name="Music"):
    """Core Music Playback and Queue management commands."""

    def __init__(self, bot: commands.Bot, player_manager: PlayerManager):
        self.bot = bot
        self.players = player_manager

    async def _ensure_voice(self, interaction: discord.Interaction) -> Optional[discord.VoiceClient]:
        """Ensure user and bot are in a voice channel with proper permissions."""
        if not interaction.guild:
            await interaction.response.send_message(f"{EMOJI_CROSS} This command must be used in a server!", ephemeral=True)
            return None

        if not interaction.user or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message(f"{EMOJI_CROSS} Cannot determine user status.", ephemeral=True)
            return None

        if not interaction.user.voice or not interaction.user.voice.channel:
            await interaction.response.send_message(f"{EMOJI_CROSS} You must be connected to a voice channel first!", ephemeral=True)
            return None

        user_channel = interaction.user.voice.channel
        me = interaction.guild.me
        if not me:
            return None
        
        # Check bot permissions in target channel
        permissions = user_channel.permissions_for(me)
        if not permissions.connect or not permissions.speak:
            await interaction.response.send_message(
                f"{EMOJI_CROSS} I don't have permission to **Connect** or **Speak** in your voice channel!",
                ephemeral=True
            )
            return None

        player = self.players.get_player(interaction.guild)
        voice_client: Any = interaction.guild.voice_client

        try:
            if voice_client is None or not voice_client.is_connected():
                voice_client = await user_channel.connect(reconnect=True, timeout=20.0)
            elif voice_client.channel != user_channel:
                await voice_client.move_to(user_channel)
            player.voice_client = voice_client
        except Exception as e:
            await interaction.response.send_message(f"{EMOJI_CROSS} Failed to connect to voice channel: {e}", ephemeral=True)
            return None

        return player.voice_client

    # ------------------ /join ------------------
    @app_commands.command(name="join", description="Join your current voice channel")
    async def join_slash(self, interaction: discord.Interaction):
        if not interaction.guild:
            return await interaction.response.send_message(f"{EMOJI_CROSS} This command must be used in a server!", ephemeral=True)
        if not interaction.user or not isinstance(interaction.user, discord.Member):
            return await interaction.response.send_message(f"{EMOJI_CROSS} Cannot determine user status.", ephemeral=True)
        if not interaction.user.voice or not interaction.user.voice.channel:
            return await interaction.response.send_message(f"{EMOJI_CROSS} You must be connected to a voice channel first!", ephemeral=True)

        user_channel = interaction.user.voice.channel
        vc = await self._ensure_voice(interaction)
        if not vc:
            return

        player = self.players.get_player(interaction.guild)
        player.bound_channel = interaction.channel  # type: ignore
        view = StatusLayoutView(f"### {EMOJI_VOLUME} Joined Voice Channel", f"Connected to **{user_channel.name}**.")
        await interaction.response.send_message(view=view)

    # ------------------ /play ------------------
    @app_commands.command(name="play", description="Play a song by name or link")
    @app_commands.describe(query="Song title, keyword, or web audio link")
    async def play_slash(self, interaction: discord.Interaction, query: Optional[str] = None):
        player = self.players.get_player(interaction.guild)

        if not query:
            if player.is_paused:
                await player.resume()
                return await interaction.response.send_message(f"{EMOJI_PAUSE} Resumed playback.", ephemeral=True)
            elif player.queue and not player.is_playing:
                vc = await self._ensure_voice(interaction)
                if not vc:
                    return
                await player._play_next()
                return await interaction.response.send_message(f"{EMOJI_PAUSE} Starting playback from queue.", ephemeral=True)
            else:
                view = StatusLayoutView(f"### {EMOJI_MUSICNOTE} Nothing is playing", "Use `/play` or `,play` to start a song.")
                return await interaction.response.send_message(view=view, ephemeral=True)

        vc = await self._ensure_voice(interaction)
        if not vc:
            return

        player.bound_channel = interaction.channel  # type: ignore

        # Check if URL or local song
        if query.startswith(("http://", "https://")):
            await interaction.response.defer()
            track = await resolve_url_track(query, requester=interaction.user)
            if not track:
                view = StatusLayoutView(f"### {EMOJI_WARNING} Invalid Audio Link", f"Could not extract audio from URL: `{query}`")
                return await interaction.followup.send(view=view, ephemeral=True)
            
            position = len(player.queue) + (1 if player.current else 0)
            started = await player.add_track(track)
            
            if not started:
                view = StatusLayoutView(
                    title=f"### {EMOJI_HEADSET} Track Queued",
                    description=(
                        f"> **[{track.title}]({SUPPORT_SERVER_URL})** - `{track.artist}`\n"
                        f"> Duration: `{track.formatted_duration}`\n"
                        f"> Position in queue: `#{position}`\n\n"
                        f"-# Added to queue successfully!"
                    ),
                    thumbnail_url=track.thumbnail_url or get_track_thumbnail(track.title, track.artist)
                )
                await interaction.followup.send(view=view)
            else:
                try:
                    await interaction.delete_original_response()
                except Exception:
                    pass
            return

        matches = library.search(query, limit=1)
        if matches:
            track_data = matches[0]
            track = Track(
                title=track_data["title"],
                artist=track_data["artist"],
                duration=track_data["duration"],
                filepath=track_data["filepath"],
                requester=interaction.user
            )
            position = len(player.queue) + (1 if player.current else 0)
            started = await player.add_track(track)
            if not started:
                view = StatusLayoutView(
                    title=f"### {EMOJI_HEADSET} Track Queued",
                    description=(
                        f"> **[{track.title}]({SUPPORT_SERVER_URL})** - `{track.artist}`\n"
                        f"> Duration: `{track.formatted_duration}`\n"
                        f"> Position in queue: `#{position}`\n\n"
                        f"-# Added to queue successfully!"
                    ),
                    thumbnail_url=track.thumbnail_url or get_track_thumbnail(track.title, track.artist)
                )
                await interaction.response.send_message(view=view)
            else:
                await interaction.response.defer()
                try:
                    await interaction.delete_original_response()
                except Exception:
                    pass
        else:
            await interaction.response.defer()
            track = await resolve_url_track(query, requester=interaction.user)
            if not track:
                view = StatusLayoutView(f"### {EMOJI_WARNING} No results found", f"Could not find any song matching `{query}`.")
                return await interaction.followup.send(view=view, ephemeral=True)

            position = len(player.queue) + (1 if player.current else 0)
            started = await player.add_track(track)

            if not started:
                view = StatusLayoutView(
                    title=f"### {EMOJI_HEADSET} Track Queued",
                    description=(
                        f"> **[{track.title}]({SUPPORT_SERVER_URL})** - `{track.artist}`\n"
                        f"> Duration: `{track.formatted_duration}`\n"
                        f"> Position in queue: `#{position}`\n\n"
                        f"-# Added to queue successfully!"
                    ),
                    thumbnail_url=track.thumbnail_url or get_track_thumbnail(track.title, track.artist)
                )
                await interaction.followup.send(view=view)
            else:
                try:
                    await interaction.delete_original_response()
                except Exception:
                    pass

    @play_slash.autocomplete("query")
    async def play_autocomplete(self, interaction: discord.Interaction, current: str) -> List[app_commands.Choice[str]]:
        matches = library.search(current, limit=10) if current else library.get_all()[:10]
        return [
            app_commands.Choice(
                name=f"{t['title']} - {t['artist']}"[:100],
                value=t['title']
            )
            for t in matches
        ]

    # ------------------ /pause ------------------
    @app_commands.command(name="pause", description="Pause current track")
    async def pause_slash(self, interaction: discord.Interaction):
        player = self.players.get_player(interaction.guild)
        if await player.pause():
            view = StatusLayoutView(f"### {EMOJI_PAUSE} Playback Paused", "Use `/resume` or `,resume` to continue.")
            await interaction.response.send_message(view=view)
        else:
            view = StatusLayoutView(f"### {EMOJI_MUSICNOTE} Nothing is playing", "Use `/play` or `,play` to start a song.")
            await interaction.response.send_message(view=view, ephemeral=True)

    # ------------------ /resume ------------------
    @app_commands.command(name="resume", description="Resume paused track")
    async def resume_slash(self, interaction: discord.Interaction):
        player = self.players.get_player(interaction.guild)
        if await player.resume():
            view = StatusLayoutView(f"### {EMOJI_PAUSE} Playback Resumed", "Enjoy your music!")
            await interaction.response.send_message(view=view)
        else:
            view = StatusLayoutView(f"### {EMOJI_MUSICNOTE} Nothing is playing", "Use `/play` or `,play` to start a song.")
            await interaction.response.send_message(view=view, ephemeral=True)

    # ------------------ /skip ------------------
    @app_commands.command(name="skip", description="Skip song(s) in queue")
    @app_commands.describe(count="Number of songs to skip (default: 1)")
    async def skip_slash(self, interaction: discord.Interaction, count: Optional[int] = 1):
        player = self.players.get_player(interaction.guild)
        if not player.current:
            view = StatusLayoutView(f"### {EMOJI_MUSICNOTE} Nothing is playing", "Use `/play` or `,play` to start a song.")
            return await interaction.response.send_message(view=view, ephemeral=True)

        skip_count = max(1, count or 1)
        if skip_count > 1:
            discarded = min(skip_count - 1, len(player.queue))
            for _ in range(discarded):
                player.queue.pop(0)
            await player.skip()
            await interaction.response.send_message(f"{EMOJI_SKIP} Skipped **{discarded + 1}** songs.")
        else:
            skipped = await player.skip()
            if skipped:
                await interaction.response.send_message(f"{EMOJI_SKIP} Skipped **{skipped.title}**.")
            else:
                await interaction.response.send_message(f"{EMOJI_CROSS} Nothing was playing.", ephemeral=True)

    # ------------------ /previous ------------------
    @app_commands.command(name="previous", description="Play the previous song from history")
    async def previous_slash(self, interaction: discord.Interaction):
        player = self.players.get_player(interaction.guild)
        if not player.history:
            return await interaction.response.send_message(f"{EMOJI_CROSS} No previous track found in history.", ephemeral=True)
        prev_track = player.history[-1]
        success = await player.previous()
        if success:
            view = StatusLayoutView(f"### {EMOJI_PREVIOUS} Previous Track", f"Now playing **{prev_track.title}**.")
            await interaction.response.send_message(view=view)
        else:
            await interaction.response.send_message(f"{EMOJI_CROSS} Could not play previous track.", ephemeral=True)

    # ------------------ /stop ------------------
    @app_commands.command(name="stop", description="Stop music, clear queue, and leave voice channel")
    async def stop_slash(self, interaction: discord.Interaction):
        player = self.players.get_player(interaction.guild)
        player.queue.clear()
        await player.stop()
        if player.voice_client and player.voice_client.is_connected():
            await player.voice_client.disconnect()
        player.voice_client = None
        view = StatusLayoutView(f"### {EMOJI_STOP} Playback Stopped", "Queue cleared and left the voice channel.")
        await interaction.response.send_message(view=view)

    # ------------------ /disconnect ------------------
    @app_commands.command(name="disconnect", description="Disconnect bot from voice channel and clear queue")
    async def disconnect_slash(self, interaction: discord.Interaction):
        player = self.players.get_player(interaction.guild)
        player.queue.clear()
        await player.stop()
        if player.voice_client and player.voice_client.is_connected():
            await player.voice_client.disconnect()
        player.voice_client = None
        view = StatusLayoutView(f"### {EMOJI_STOP} Playback Stopped", "Queue cleared and disconnected from the voice channel.")
        await interaction.response.send_message(view=view)

    # ------------------ /queue ------------------
    @app_commands.command(name="queue", description="View active playlist queue")
    @app_commands.describe(page="Queue page number")
    async def queue_slash(self, interaction: discord.Interaction, page: Optional[int] = 1):
        player = self.players.get_player(interaction.guild)
        if not player.current and not player.queue:
            view = StatusLayoutView(f"### {EMOJI_QUEUE} Queue is empty", "Add some tracks using `/play` or `,play`.")
            return await interaction.response.send_message(view=view, ephemeral=True)

        view = QueueLayoutView(player, current_page=page or 1)
        await interaction.response.send_message(view=view)

    # ------------------ /clear ------------------
    @app_commands.command(name="clear", description="Clear all songs from upcoming queue")
    async def clear_slash(self, interaction: discord.Interaction):
        player = self.players.get_player(interaction.guild)
        player.queue.clear()
        view = StatusLayoutView(f"### {EMOJI_TRASH} Queue Cleared", "All pending tracks have been removed.")
        await interaction.response.send_message(view=view)

    # ------------------ /shuffle ------------------
    @app_commands.command(name="shuffle", description="Shuffle songs in upcoming queue")
    async def shuffle_slash(self, interaction: discord.Interaction):
        player = self.players.get_player(interaction.guild)
        if len(player.queue) <= 1:
            return await interaction.response.send_message(f"{EMOJI_CROSS} Not enough tracks in queue to shuffle.", ephemeral=True)
        player.shuffle_queue()
        view = StatusLayoutView(f"### {EMOJI_SHUFFLE} Queue Shuffled", "The upcoming playlist has been randomized.")
        await interaction.response.send_message(view=view)

    # ------------------ /autoplay ------------------
    @app_commands.command(name="autoplay", description="Toggle autoplay for similar songs")
    async def autoplay_slash(self, interaction: discord.Interaction):
        player = self.players.get_player(interaction.guild)
        player.autoplay = not player.autoplay
        status = "ENABLED" if player.autoplay else "DISABLED"
        view = StatusLayoutView(f"### {EMOJI_SPARKLES} Autoplay", f"Autoplay mode is now **{status}**.")
        await interaction.response.send_message(view=view)

    # ------------------ /nowplaying ------------------
    @app_commands.command(name="nowplaying", description="Show active player card")
    async def nowplaying_slash(self, interaction: discord.Interaction):
        player = self.players.get_player(interaction.guild)
        if not player.current:
            view = StatusLayoutView(f"### {EMOJI_MUSICNOTE} Nothing is playing", "Use `/play` or `,play` to start a song.")
            return await interaction.response.send_message(view=view, ephemeral=True)

        view = NowPlayingLayoutView(player)
        await interaction.response.send_message(view=view)

    # ------------------ /volume ------------------
    @app_commands.command(name="volume", description="Set playback volume (1-100)")
    @app_commands.describe(level="Volume level percentage (1 - 100)")
    async def volume_slash(self, interaction: discord.Interaction, level: int):
        if level < 1 or level > 100:
            return await interaction.response.send_message(f"{EMOJI_CROSS} Volume must be between 1 and 100.", ephemeral=True)
        player = self.players.get_player(interaction.guild)
        player.set_volume(level / 100.0)
        await interaction.response.send_message(f"{EMOJI_VOLUME} Volume set to **{level}%**")

    # ------------------ /loop ------------------
    @app_commands.command(name="loop", description="Change loop mode")
    @app_commands.choices(mode=[
        app_commands.Choice(name="Off", value="off"),
        app_commands.Choice(name="Track (Repeat Single Song)", value="track"),
        app_commands.Choice(name="Queue (Repeat Entire Playlist)", value="queue")
    ])
    async def loop_slash(self, interaction: discord.Interaction, mode: Optional[str] = None):
        player = self.players.get_player(interaction.guild)
        if mode:
            player.loop_mode = mode
            new_mode = mode
        else:
            new_mode = player.cycle_loop()
        await interaction.response.send_message(f"{EMOJI_LOOP} Loop mode set to: **{new_mode.upper()}**")

    # ------------------ /filter ------------------
    @app_commands.command(name="filter", description="Apply or clear an audio filter (8D, Bass Boost, Nightcore, etc.)")
    @app_commands.choices(preset=[
        app_commands.Choice(name="8D Audio 🎧", value="8d"),
        app_commands.Choice(name="Bass Boost 🔊", value="bassboost"),
        app_commands.Choice(name="Nightcore ✨", value="nightcore"),
        app_commands.Choice(name="Vaporwave 🌴", value="vaporwave"),
        app_commands.Choice(name="Pop / Vocal Boost 🎤", value="pop"),
        app_commands.Choice(name="Clear / Normal ❌", value="clear"),
    ])
    async def filter_slash(self, interaction: discord.Interaction, preset: str):
        player = self.players.get_player(interaction.guild)
        chosen = None if preset == "clear" else preset
        success = await player.set_filter(chosen, update_card=True)
        if success:
            label = "Normal (Cleared)" if not chosen else preset.upper()
            view = StatusLayoutView(f"### {EMOJI_FILTER} Audio Filter Updated", f"Filter set to **{label}**.")
            await interaction.response.send_message(view=view)
        else:
            await interaction.response.send_message(f"{EMOJI_CROSS} Failed to apply filter.", ephemeral=True)

    # ================== Traditional Prefix Commands (,) ==================
    @commands.command(name="join", aliases=["connect", "j"])
    async def join_prefix(self, ctx: commands.Context):
        """Join your current voice channel (,join or ,j)"""
        if not ctx.guild:
            return await ctx.send(f"{EMOJI_CROSS} This command must be used in a server!")
        if not isinstance(ctx.author, discord.Member) or not ctx.author.voice or not ctx.author.voice.channel:
            return await ctx.send(f"{EMOJI_CROSS} You must be connected to a voice channel first!")

        user_channel = ctx.author.voice.channel
        me = ctx.guild.me
        if not me:
            return
        permissions = user_channel.permissions_for(me)
        if not permissions.connect or not permissions.speak:
            return await ctx.send(f"{EMOJI_CROSS} I don't have permission to **Connect** or **Speak** in your voice channel!")

        player = self.players.get_player(ctx.guild)
        voice_client: Any = ctx.guild.voice_client

        try:
            if voice_client is None or not voice_client.is_connected():
                voice_client = await user_channel.connect(reconnect=True, timeout=20.0)
            elif voice_client.channel != user_channel:
                await voice_client.move_to(user_channel)
            player.voice_client = voice_client
            player.bound_channel = ctx.channel
            view = StatusLayoutView(f"### {EMOJI_VOLUME} Joined Voice Channel", f"Connected to **{user_channel.name}**.")
            await ctx.send(view=view)
        except Exception as e:
            await ctx.send(f"{EMOJI_CROSS} Failed to connect to voice channel: {e}")

    @commands.command(name="play", aliases=["p"])
    async def play_prefix(self, ctx: commands.Context, *, query: Optional[str] = None):
        """Play a song using ,play <song name / any link> or ,p"""
        if not ctx.guild:
            return await ctx.send(f"{EMOJI_CROSS} This command must be used in a server!")
        if not isinstance(ctx.author, discord.Member) or not ctx.author.voice or not ctx.author.voice.channel:
            return await ctx.send(f"{EMOJI_CROSS} You must be in a voice channel first!")

        user_channel = ctx.author.voice.channel
        me = ctx.guild.me
        if not me:
            return
        permissions = user_channel.permissions_for(me)
        if not permissions.connect or not permissions.speak:
            return await ctx.send(f"{EMOJI_CROSS} I don't have permission to **Connect** or **Speak** in your voice channel!")

        player = self.players.get_player(ctx.guild)
        voice_client: Any = ctx.guild.voice_client

        try:
            if voice_client is None or not voice_client.is_connected():
                voice_client = await user_channel.connect(reconnect=True, timeout=20.0)
            elif voice_client.channel != user_channel:
                await voice_client.move_to(user_channel)
            player.voice_client = voice_client
        except Exception as e:
            return await ctx.send(f"{EMOJI_CROSS} Failed to connect to voice channel: {e}")

        if not query:
            if player.is_paused:
                await player.resume()
                return await ctx.send(f"{EMOJI_PAUSE} Resumed playback.")
            elif player.queue and not player.is_playing:
                await player._play_next()
                return await ctx.send(f"{EMOJI_PAUSE} Starting playback from queue.")
            else:
                view = StatusLayoutView(f"### {EMOJI_MUSICNOTE} Nothing is playing", "Use `,play <song name/link>` to start a song.")
                return await ctx.send(view=view)

        player.bound_channel = ctx.channel

        # Check if URL or local song
        if query.startswith(("http://", "https://")):
            loading_msg = await ctx.send(f"{EMOJI_SEARCH} Fetching audio stream from link...")
            track = await resolve_url_track(query, requester=ctx.author)
            if not track:
                view = StatusLayoutView(f"### {EMOJI_WARNING} Invalid Audio Link", f"Could not extract audio from URL: `{query}`")
                return await loading_msg.edit(content=None, view=view)

            pos = len(player.queue) + (1 if player.current else 0)
            started = await player.add_track(track)

            if loading_msg:
                try:
                    await loading_msg.delete()
                except Exception:
                    pass

            if not started:
                view = StatusLayoutView(
                    title=f"### {EMOJI_HEADSET} Track Queued",
                    description=(
                        f"> **[{track.title}]({SUPPORT_SERVER_URL})** - `{track.artist}`\n"
                        f"> Duration: `{track.formatted_duration}`\n"
                        f"> Position in queue: `#{pos}`\n\n"
                        f"-# Added to queue successfully!"
                    ),
                    thumbnail_url=track.thumbnail_url or get_track_thumbnail(track.title, track.artist)
                )
                await ctx.send(view=view)
            return

        matches = library.search(query, limit=1)
        loading_msg = None
        if matches:
            track_data = matches[0]
            track = Track(
                title=track_data["title"],
                artist=track_data["artist"],
                duration=track_data["duration"],
                filepath=track_data["filepath"],
                requester=ctx.author
            )
        else:
            loading_msg = await ctx.send(f"{EMOJI_SEARCH} Searching online for `{query}`...")
            track = await resolve_url_track(query, requester=ctx.author)
            if not track:
                view = StatusLayoutView(f"### {EMOJI_WARNING} No results found", f"Could not find any song matching `{query}`.")
                if loading_msg:
                    return await loading_msg.edit(content=None, view=view)
                else:
                    return await ctx.send(view=view)

        pos = len(player.queue) + (1 if player.current else 0)
        started = await player.add_track(track)

        if loading_msg:
            try:
                await loading_msg.delete()
            except Exception:
                pass

        if not started:
            view = StatusLayoutView(
                title=f"### {EMOJI_HEADSET} Track Queued",
                description=(
                    f"> **[{track.title}]({SUPPORT_SERVER_URL})** - `{track.artist}`\n"
                    f"> Duration: `{track.formatted_duration}`\n"
                    f"> Position in queue: `#{pos}`\n\n"
                    f"-# Added to queue successfully!"
                ),
                thumbnail_url=track.thumbnail_url or get_track_thumbnail(track.title, track.artist)
            )
            await ctx.send(view=view)

    @commands.command(name="pause")
    async def pause_prefix(self, ctx: commands.Context):
        """Pause playback"""
        player = self.players.get_player(ctx.guild)
        if await player.pause():
            view = StatusLayoutView(f"### {EMOJI_PAUSE} Playback Paused", "Use `,resume` to continue.")
            await ctx.send(view=view)
        else:
            view = StatusLayoutView(f"### {EMOJI_MUSICNOTE} Nothing is playing", "Use `,play` to start a song.")
            await ctx.send(view=view)

    @commands.command(name="resume")
    async def resume_prefix(self, ctx: commands.Context):
        """Resume playback"""
        player = self.players.get_player(ctx.guild)
        if await player.resume():
            view = StatusLayoutView(f"### {EMOJI_PAUSE} Playback Resumed", "Enjoy your music!")
            await ctx.send(view=view)
        else:
            view = StatusLayoutView(f"### {EMOJI_MUSICNOTE} Nothing is playing", "Use `,play` to start a song.")
            await ctx.send(view=view)

    @commands.command(name="skip", aliases=["s"])
    async def skip_prefix(self, ctx: commands.Context, count: Optional[int] = 1):
        """Skip song(s) in queue using ,skip or ,skip <number>"""
        player = self.players.get_player(ctx.guild)
        if not player.current:
            view = StatusLayoutView(f"### {EMOJI_MUSICNOTE} Nothing is playing", "Use `,play` to start a song.")
            return await ctx.send(view=view)

        skip_count = max(1, count or 1)
        if skip_count > 1:
            discarded = min(skip_count - 1, len(player.queue))
            for _ in range(discarded):
                player.queue.pop(0)
            await player.skip()
            view = StatusLayoutView(f"### {EMOJI_SKIP} Skipped Tracks", f"Skipped **{discarded + 1}** songs.")
            await ctx.send(view=view)
        else:
            skipped = await player.skip()
            if skipped:
                view = StatusLayoutView(f"### {EMOJI_SKIP} Track Skipped", f"Skipped **{skipped.title}**.")
                await ctx.send(view=view)

    @commands.command(name="previous", aliases=["prev"])
    async def previous_prefix(self, ctx: commands.Context):
        """Play previous track from history (alias: ,prev)"""
        player = self.players.get_player(ctx.guild)
        if not player.history:
            return await ctx.send(f"{EMOJI_CROSS} No previous track found in history.")
        prev_track = player.history[-1]
        success = await player.previous()
        if success:
            view = StatusLayoutView(f"### {EMOJI_PREVIOUS} Previous Track", f"Now playing **{prev_track.title}**.")
            await ctx.send(view=view)
        else:
            await ctx.send(f"{EMOJI_CROSS} Could not play previous track.")

    @commands.command(name="filter", aliases=["filters"])
    async def filter_prefix(self, ctx: commands.Context, filter_name: Optional[str] = None):
        """Set or clear an audio filter: ,filter [8d|bassboost|nightcore|vaporwave|pop|clear]"""
        player = self.players.get_player(ctx.guild)
        if not filter_name:
            active = player.filter.upper() if player.filter else "None"
            return await ctx.send(f"{EMOJI_FILTER} Active filter: **{active}**. Available: `8d`, `bassboost`, `nightcore`, `vaporwave`, `pop`, `clear`.")
        
        filter_name = filter_name.lower().strip()
        if filter_name in ("clear", "off", "none", "reset"):
            await player.set_filter(None)
            view = StatusLayoutView(f"### {EMOJI_FILTER} Audio Filter Cleared", "All audio effects reset to normal.")
            return await ctx.send(view=view)
            
        success = await player.set_filter(filter_name)
        if success:
            view = StatusLayoutView(f"### {EMOJI_FILTER} Audio Filter Applied", f"Filter set to **{filter_name.upper()}**.")
            await ctx.send(view=view)
        else:
            await ctx.send(f"{EMOJI_CROSS} Unknown filter `{filter_name}`. Available: `8d`, `bassboost`, `nightcore`, `vaporwave`, `pop`, `clear`.")

    @commands.command(name="stop", aliases=["disconnect", "dc", "leave"])
    async def stop_prefix(self, ctx: commands.Context):
        """Stop music, clear queue, and leave voice channel (aliases: ,disconnect, ,dc, ,leave)"""
        player = self.players.get_player(ctx.guild)
        player.queue.clear()
        await player.stop()
        if player.voice_client and player.voice_client.is_connected():
            await player.voice_client.disconnect()
        player.voice_client = None
        view = StatusLayoutView(f"### {EMOJI_STOP} Playback Stopped", "Queue cleared and disconnected from the voice channel.")
        await ctx.send(view=view)

    @commands.command(name="queue", aliases=["q"])
    async def queue_prefix(self, ctx: commands.Context, page: int = 1):
        """Show songs in queue"""
        player = self.players.get_player(ctx.guild)
        if not player.current and not player.queue:
            view = StatusLayoutView(f"### {EMOJI_QUEUE} Queue is empty", "Add some tracks using `,play`.")
            return await ctx.send(view=view)
        view = QueueLayoutView(player, current_page=page)
        await ctx.send(view=view)

    @commands.command(name="clear")
    async def clear_prefix(self, ctx: commands.Context):
        """Clear the queue"""
        player = self.players.get_player(ctx.guild)
        player.queue.clear()
        view = StatusLayoutView(f"### {EMOJI_TRASH} Queue Cleared", "All pending tracks have been removed.")
        await ctx.send(view=view)

    @commands.command(name="shuffle")
    async def shuffle_prefix(self, ctx: commands.Context):
        """Shuffle the queue"""
        player = self.players.get_player(ctx.guild)
        if len(player.queue) <= 1:
            return await ctx.send(f"{EMOJI_CROSS} Not enough tracks in queue to shuffle.")
        player.shuffle_queue()
        view = StatusLayoutView(f"### {EMOJI_SHUFFLE} Queue Shuffled", "The upcoming playlist has been randomized.")
        await ctx.send(view=view)

    @commands.command(name="loop")
    async def loop_prefix(self, ctx: commands.Context):
        """Loop the current song"""
        player = self.players.get_player(ctx.guild)
        if player.loop_mode == "track":
            player.loop_mode = "off"
            status = "DISABLED"
        else:
            player.loop_mode = "track"
            status = "ENABLED"
        view = StatusLayoutView(f"### {EMOJI_LOOP} Track Loop", f"Current song repeat is now **{status}**.")
        await ctx.send(view=view)

    @commands.command(name="autoplay")
    async def autoplay_prefix(self, ctx: commands.Context):
        """Plays songs similar to the last song played"""
        player = self.players.get_player(ctx.guild)
        player.autoplay = not player.autoplay
        status = "ENABLED" if player.autoplay else "DISABLED"
        view = StatusLayoutView(f"### {EMOJI_SPARKLES} Autoplay", f"Autoplay mode is now **{status}**.")
        await ctx.send(view=view)

    @commands.command(name="nowplaying", aliases=["np"])
    async def nowplaying_prefix(self, ctx: commands.Context):
        """Show active player card"""
        player = self.players.get_player(ctx.guild)
        if not player.current:
            view = StatusLayoutView(f"### {EMOJI_MUSICNOTE} Nothing is playing", "Use `,play` to start a song.")
            return await ctx.send(view=view)
        view = NowPlayingLayoutView(player)
        await ctx.send(view=view)


async def setup(bot: commands.Bot):
    # Retrieve or create PlayerManager attached to bot
    pm = getattr(bot, "player_manager", None)
    if not pm:
        pm = PlayerManager(bot)
        setattr(bot, "player_manager", pm)
    await bot.add_cog(MusicCog(bot, pm))
