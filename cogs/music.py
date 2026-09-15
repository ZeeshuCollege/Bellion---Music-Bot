from typing import List, Optional
import discord
from discord import app_commands
from discord.ext import commands

from music.library import library
from music.track import Track
from music.player import PlayerManager
from music.resolver import resolve_url_track
from config import SUPPORT_SERVER_URL, get_track_thumbnail
from ui.views import NowPlayingLayoutView, QueueLayoutView, SearchLayoutView, StatusLayoutView

class MusicCog(commands.Cog, name="Music"):
    """Core Music Playback and Queue management commands."""

    def __init__(self, bot: commands.Bot, player_manager: PlayerManager):
        self.bot = bot
        self.players = player_manager

    async def _ensure_voice(self, interaction: discord.Interaction) -> Optional[discord.VoiceClient]:
        """Ensure user and bot are in a voice channel with proper permissions."""
        if not interaction.user or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message("❌ Cannot determine user status.", ephemeral=True)
            return None

        if not interaction.user.voice or not interaction.user.voice.channel:
            await interaction.response.send_message("❌ You must be connected to a voice channel first!", ephemeral=True)
            return None

        user_channel = interaction.user.voice.channel
        
        # Check bot permissions in target channel
        permissions = user_channel.permissions_for(interaction.guild.me)
        if not permissions.connect or not permissions.speak:
            await interaction.response.send_message(
                "❌ I don't have permission to **Connect** or **Speak** in your voice channel!",
                ephemeral=True
            )
            return None

        player = self.players.get_player(interaction.guild)
        voice_client = interaction.guild.voice_client

        try:
            if voice_client is None or not voice_client.is_connected():
                voice_client = await user_channel.connect(reconnect=True, timeout=20.0)
            elif voice_client.channel != user_channel:
                await voice_client.move_to(user_channel)
            player.voice_client = voice_client
        except Exception as e:
            await interaction.response.send_message(f"❌ Failed to connect to voice channel: {e}", ephemeral=True)
            return None

        return player.voice_client

    # ------------------ /play ------------------
    @app_commands.command(name="play", description="Play a song by name or link")
    @app_commands.describe(query="Song title, keyword, or web audio link")
    async def play_slash(self, interaction: discord.Interaction, query: Optional[str] = None):
        player = self.players.get_player(interaction.guild)

        if not query:
            if player.is_paused:
                await player.resume()
                return await interaction.response.send_message("▶️ Resumed playback.", ephemeral=True)
            elif player.queue and not player.is_playing:
                vc = await self._ensure_voice(interaction)
                if not vc:
                    return
                await player._play_next()
                return await interaction.response.send_message("▶️ Starting playback from queue.", ephemeral=True)
            else:
                view = StatusLayoutView("### 🎵 Nothing is playing", "Use `/play` or `,play` to start a song.")
                return await interaction.response.send_message(view=view, ephemeral=True)

        vc = await self._ensure_voice(interaction)
        if not vc:
            return

        # Check if URL or local song
        if query.startswith(("http://", "https://")):
            await interaction.response.defer()
            track = await resolve_url_track(query, requester=interaction.user)
            if not track:
                view = StatusLayoutView("### ⚠️ Invalid Audio Link", f"Could not extract audio from URL: `{query}`")
                return await interaction.followup.send(view=view, ephemeral=True)
            
            is_already_active = player.is_playing or player.current is not None
            position = len(player.queue) + (1 if player.current else 0)
            await player.add_track(track)
            
            if is_already_active:
                view = StatusLayoutView(
                    title="### :white_check_mark: Track Queued",
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
                await interaction.followup.send(f"🎵 Now loading **{track.title}**...")
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
        else:
            await interaction.response.defer()
            track = await resolve_url_track(query, requester=interaction.user)
            if not track:
                view = StatusLayoutView("### ⚠️ No results found", f"Could not find any song matching `{query}`.")
                return await interaction.followup.send(view=view, ephemeral=True)

        is_already_active = player.is_playing or player.current is not None
        position = len(player.queue) + (1 if player.current else 0)

        await player.add_track(track)

        if is_already_active:
            view = StatusLayoutView(
                title="### :white_check_mark: Track Queued",
                description=(
                    f"> **[{track.title}]({SUPPORT_SERVER_URL})** - `{track.artist}`\n"
                    f"> Duration: `{track.formatted_duration}`\n"
                    f"> Position in queue: `#{position}`\n\n"
                    f"-# Added to queue successfully!"
                ),
                thumbnail_url=track.thumbnail_url or get_track_thumbnail(track.title, track.artist)
            )
            if interaction.response.is_done():
                await interaction.followup.send(view=view)
            else:
                await interaction.response.send_message(view=view)
        else:
            if interaction.response.is_done():
                await interaction.followup.send(f"🎵 Now loading **{track.title}**...")
            else:
                await interaction.response.send_message(f"🎵 Now loading **{track.title}**...", ephemeral=True)

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
            view = StatusLayoutView("### ⏸️ Playback Paused", "Use `/resume` or `,resume` to continue.")
            await interaction.response.send_message(view=view)
        else:
            view = StatusLayoutView("### 🎵 Nothing is playing", "Use `/play` or `,play` to start a song.")
            await interaction.response.send_message(view=view, ephemeral=True)

    # ------------------ /resume ------------------
    @app_commands.command(name="resume", description="Resume paused track")
    async def resume_slash(self, interaction: discord.Interaction):
        player = self.players.get_player(interaction.guild)
        if await player.resume():
            view = StatusLayoutView("### ▶️ Playback Resumed", "Enjoy your music!")
            await interaction.response.send_message(view=view)
        else:
            view = StatusLayoutView("### 🎵 Nothing is playing", "Use `/play` or `,play` to start a song.")
            await interaction.response.send_message(view=view, ephemeral=True)

    # ------------------ /skip ------------------
    @app_commands.command(name="skip", description="Skip song(s) in queue")
    @app_commands.describe(count="Number of songs to skip (default: 1)")
    async def skip_slash(self, interaction: discord.Interaction, count: Optional[int] = 1):
        player = self.players.get_player(interaction.guild)
        if not player.current:
            view = StatusLayoutView("### 🎵 Nothing is playing", "Use `/play` or `,play` to start a song.")
            return await interaction.response.send_message(view=view, ephemeral=True)

        skip_count = max(1, count or 1)
        if skip_count > 1:
            discarded = min(skip_count - 1, len(player.queue))
            for _ in range(discarded):
                player.queue.pop(0)
            await player.skip()
            await interaction.response.send_message(f"⏭️ Skipped **{discarded + 1}** songs.")
        else:
            skipped = await player.skip()
            await interaction.response.send_message(f"⏭️ Skipped **{skipped.title}**.")

    # ------------------ /stop ------------------
    @app_commands.command(name="stop", description="Stop music, clear queue, and leave voice channel")
    async def stop_slash(self, interaction: discord.Interaction):
        player = self.players.get_player(interaction.guild)
        player.queue.clear()
        await player.stop()
        if player.voice_client and player.voice_client.is_connected():
            await player.voice_client.disconnect()
        player.voice_client = None
        view = StatusLayoutView("### ⏹️ Playback Stopped", "Queue cleared and left the voice channel.")
        await interaction.response.send_message(view=view)

    # ------------------ /queue ------------------
    @app_commands.command(name="queue", description="View active playlist queue")
    @app_commands.describe(page="Queue page number")
    async def queue_slash(self, interaction: discord.Interaction, page: Optional[int] = 1):
        player = self.players.get_player(interaction.guild)
        if not player.current and not player.queue:
            view = StatusLayoutView("### 📑 Queue is empty", "Add some tracks using `/play` or `,play`.")
            return await interaction.response.send_message(view=view, ephemeral=True)

        view = QueueLayoutView(player, current_page=page or 1)
        await interaction.response.send_message(view=view)

    # ------------------ /clear ------------------
    @app_commands.command(name="clear", description="Clear all songs from upcoming queue")
    async def clear_slash(self, interaction: discord.Interaction):
        player = self.players.get_player(interaction.guild)
        player.queue.clear()
        view = StatusLayoutView("### 🗑️ Queue Cleared", "All pending tracks have been removed.")
        await interaction.response.send_message(view=view)

    # ------------------ /shuffle ------------------
    @app_commands.command(name="shuffle", description="Shuffle songs in upcoming queue")
    async def shuffle_slash(self, interaction: discord.Interaction):
        player = self.players.get_player(interaction.guild)
        if len(player.queue) <= 1:
            return await interaction.response.send_message("❌ Not enough tracks in queue to shuffle.", ephemeral=True)
        player.shuffle_queue()
        view = StatusLayoutView("### 🔀 Queue Shuffled", "The upcoming playlist has been randomized.")
        await interaction.response.send_message(view=view)

    # ------------------ /loop ------------------
    @app_commands.command(name="loop", description="Loop the current song")
    async def loop_slash(self, interaction: discord.Interaction):
        player = self.players.get_player(interaction.guild)
        if player.loop_mode == "track":
            player.loop_mode = "off"
            status = "DISABLED"
        else:
            player.loop_mode = "track"
            status = "ENABLED"
        view = StatusLayoutView("### 🔁 Track Loop", f"Current song repeat is now **{status}**.")
        await interaction.response.send_message(view=view)

    # ------------------ /autoplay ------------------
    @app_commands.command(name="autoplay", description="Toggle autoplay for similar songs")
    async def autoplay_slash(self, interaction: discord.Interaction):
        player = self.players.get_player(interaction.guild)
        player.autoplay = not player.autoplay
        status = "ENABLED" if player.autoplay else "DISABLED"
        view = StatusLayoutView("### ✨ Autoplay", f"Autoplay mode is now **{status}**.")
        await interaction.response.send_message(view=view)

    # ------------------ /nowplaying ------------------
    @app_commands.command(name="nowplaying", description="Show active player card")
    async def nowplaying_slash(self, interaction: discord.Interaction):
        player = self.players.get_player(interaction.guild)
        if not player.current:
            view = StatusLayoutView("### 🎵 Nothing is playing", "Use `/play` or `,play` to start a song.")
            return await interaction.response.send_message(view=view, ephemeral=True)

        view = NowPlayingLayoutView(player)
        await interaction.response.send_message(view=view)

    # ------------------ /shuffle ------------------
    @app_commands.command(name="shuffle", description="Shuffle songs in the upcoming queue")
    async def shuffle_slash(self, interaction: discord.Interaction):
        player = self.players.get_player(interaction.guild)
        if len(player.queue) <= 1:
            return await interaction.response.send_message("❌ Not enough tracks in queue to shuffle.", ephemeral=True)
        player.shuffle_queue()
        await interaction.response.send_message("🔀 Queue shuffled successfully!")

    # ------------------ /clear ------------------
    @app_commands.command(name="clear", description="Clear all songs from upcoming queue")
    async def clear_slash(self, interaction: discord.Interaction):
        player = self.players.get_player(interaction.guild)
        player.queue.clear()
        await interaction.response.send_message("🗑️ Cleared upcoming queue.")

    # ------------------ /volume ------------------
    @app_commands.command(name="volume", description="Set playback volume (1-100)")
    @app_commands.describe(level="Volume level percentage (1 - 100)")
    async def volume_slash(self, interaction: discord.Interaction, level: int):
        if level < 1 or level > 100:
            return await interaction.response.send_message("❌ Volume must be between 1 and 100.", ephemeral=True)
        player = self.players.get_player(interaction.guild)
        player.set_volume(level / 100.0)
        await interaction.response.send_message(f"🔊 Volume set to **{level}%**")

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
        await interaction.response.send_message(f"🔁 Loop mode set to: **{new_mode.upper()}**")

    # ================== Traditional Prefix Commands (,) ==================
    @commands.command(name="play", aliases=["p"])
    async def play_prefix(self, ctx: commands.Context, *, query: Optional[str] = None):
        """Play a song using ,play <song name / any link> or ,p"""
        if not ctx.author.voice or not ctx.author.voice.channel:
            return await ctx.send("❌ You must be in a voice channel first!")

        user_channel = ctx.author.voice.channel
        permissions = user_channel.permissions_for(ctx.guild.me)
        if not permissions.connect or not permissions.speak:
            return await ctx.send("❌ I don't have permission to **Connect** or **Speak** in your voice channel!")

        player = self.players.get_player(ctx.guild)
        voice_client = ctx.guild.voice_client

        try:
            if voice_client is None or not voice_client.is_connected():
                voice_client = await user_channel.connect(reconnect=True, timeout=20.0)
            elif voice_client.channel != user_channel:
                await voice_client.move_to(user_channel)
            player.voice_client = voice_client
        except Exception as e:
            return await ctx.send(f"❌ Failed to connect to voice channel: {e}")

        if not query:
            if player.is_paused:
                await player.resume()
                return await ctx.send("▶️ Resumed playback.")
            elif player.queue and not player.is_playing:
                await player._play_next()
                return await ctx.send("▶️ Starting playback from queue.")
            else:
                view = StatusLayoutView("### 🎵 Nothing is playing", "Use `,play <song name/link>` to start a song.")
                return await ctx.send(view=view)

        # Check if URL or local song
        if query.startswith(("http://", "https://")):
            loading_msg = await ctx.send(f"🔍 Fetching audio stream from link...")
            track = await resolve_url_track(query, requester=ctx.author)
            if not track:
                view = StatusLayoutView("### ⚠️ Invalid Audio Link", f"Could not extract audio from URL: `{query}`")
                return await loading_msg.edit(content=None, view=view)

            is_already_active = player.is_playing or player.current is not None
            pos = len(player.queue) + (1 if player.current else 0)
            await player.add_track(track)

            if is_already_active:
                view = StatusLayoutView(
                    title="### :white_check_mark: Track Queued",
                    description=(
                        f"> **[{track.title}]({SUPPORT_SERVER_URL})** - `{track.artist}`\n"
                        f"> Duration: `{track.formatted_duration}`\n"
                        f"> Position in queue: `#{pos}`\n\n"
                        f"-# Added to queue successfully!"
                    ),
                    thumbnail_url=track.thumbnail_url or get_track_thumbnail(track.title, track.artist)
                )
                await loading_msg.edit(content=None, view=view)
            else:
                await loading_msg.edit(content=f"🎵 Now playing **{track.title}**!")
            return

        matches = library.search(query, limit=1)
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
            loading_msg = await ctx.send(f"🔍 Searching online for `{query}`...")
            track = await resolve_url_track(query, requester=ctx.author)
            if not track:
                view = StatusLayoutView("### ⚠️ No results found", f"Could not find any song matching `{query}`.")
                return await loading_msg.edit(content=None, view=view)
            try:
                await loading_msg.delete()
            except Exception:
                pass

        is_already_active = player.is_playing or player.current is not None
        pos = len(player.queue) + (1 if player.current else 0)

        await player.add_track(track)

        if is_already_active:
            view = StatusLayoutView(
                title="### :white_check_mark: Track Queued",
                description=(
                    f"> **[{track.title}]({SUPPORT_SERVER_URL})** - `{track.artist}`\n"
                    f"> Duration: `{track.formatted_duration}`\n"
                    f"> Position in queue: `#{pos}`\n\n"
                    f"-# Added to queue successfully!"
                ),
                thumbnail_url=track.thumbnail_url or get_track_thumbnail(track.title, track.artist)
            )
            await ctx.send(view=view)
        else:
            await ctx.send(f"🎵 Now loading **{track.title}**...")

    @commands.command(name="pause")
    async def pause_prefix(self, ctx: commands.Context):
        """Pause playback"""
        player = self.players.get_player(ctx.guild)
        if await player.pause():
            view = StatusLayoutView("### ⏸️ Playback Paused", "Use `,resume` to continue.")
            await ctx.send(view=view)
        else:
            view = StatusLayoutView("### 🎵 Nothing is playing", "Use `,play` to start a song.")
            await ctx.send(view=view)

    @commands.command(name="resume")
    async def resume_prefix(self, ctx: commands.Context):
        """Resume playback"""
        player = self.players.get_player(ctx.guild)
        if await player.resume():
            view = StatusLayoutView("### ▶️ Playback Resumed", "Enjoy your music!")
            await ctx.send(view=view)
        else:
            view = StatusLayoutView("### 🎵 Nothing is playing", "Use `,play` to start a song.")
            await ctx.send(view=view)

    @commands.command(name="skip", aliases=["s"])
    async def skip_prefix(self, ctx: commands.Context, count: Optional[int] = 1):
        """Skip song(s) in queue using ,skip or ,skip <number>"""
        player = self.players.get_player(ctx.guild)
        if not player.current:
            view = StatusLayoutView("### 🎵 Nothing is playing", "Use `,play` to start a song.")
            return await ctx.send(view=view)

        skip_count = max(1, count or 1)
        if skip_count > 1:
            discarded = min(skip_count - 1, len(player.queue))
            for _ in range(discarded):
                player.queue.pop(0)
            await player.skip()
            view = StatusLayoutView("### ⏭️ Skipped Tracks", f"Skipped **{discarded + 1}** songs.")
            await ctx.send(view=view)
        else:
            skipped = await player.skip()
            if skipped:
                view = StatusLayoutView("### ⏭️ Track Skipped", f"Skipped **{skipped.title}**.")
                await ctx.send(view=view)

    @commands.command(name="stop")
    async def stop_prefix(self, ctx: commands.Context):
        """Stop music, clear queue, and leave voice channel"""
        player = self.players.get_player(ctx.guild)
        player.queue.clear()
        await player.stop()
        if player.voice_client and player.voice_client.is_connected():
            await player.voice_client.disconnect()
        player.voice_client = None
        view = StatusLayoutView("### ⏹️ Playback Stopped", "Queue cleared and disconnected from the voice channel.")
        await ctx.send(view=view)

    @commands.command(name="queue", aliases=["q"])
    async def queue_prefix(self, ctx: commands.Context, page: int = 1):
        """Show songs in queue"""
        player = self.players.get_player(ctx.guild)
        if not player.current and not player.queue:
            view = StatusLayoutView("### 📑 Queue is empty", "Add some tracks using `,play`.")
            return await ctx.send(view=view)
        view = QueueLayoutView(player, current_page=page)
        await ctx.send(view=view)

    @commands.command(name="clear")
    async def clear_prefix(self, ctx: commands.Context):
        """Clear the queue"""
        player = self.players.get_player(ctx.guild)
        player.queue.clear()
        view = StatusLayoutView("### 🗑️ Queue Cleared", "All pending tracks have been removed.")
        await ctx.send(view=view)

    @commands.command(name="shuffle")
    async def shuffle_prefix(self, ctx: commands.Context):
        """Shuffle the queue"""
        player = self.players.get_player(ctx.guild)
        if len(player.queue) <= 1:
            return await ctx.send("❌ Not enough tracks in queue to shuffle.")
        player.shuffle_queue()
        view = StatusLayoutView("### 🔀 Queue Shuffled", "The upcoming playlist has been randomized.")
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
        view = StatusLayoutView("### 🔁 Track Loop", f"Current song repeat is now **{status}**.")
        await ctx.send(view=view)

    @commands.command(name="autoplay")
    async def autoplay_prefix(self, ctx: commands.Context):
        """Plays songs similar to the last song played"""
        player = self.players.get_player(ctx.guild)
        player.autoplay = not player.autoplay
        status = "ENABLED" if player.autoplay else "DISABLED"
        view = StatusLayoutView("### ✨ Autoplay", f"Autoplay mode is now **{status}**.")
        await ctx.send(view=view)

    @commands.command(name="nowplaying", aliases=["np"])
    async def nowplaying_prefix(self, ctx: commands.Context):
        """Show active player card"""
        player = self.players.get_player(ctx.guild)
        if not player.current:
            view = StatusLayoutView("### 🎵 Nothing is playing", "Use `,play` to start a song.")
            return await ctx.send(view=view)
        view = NowPlayingLayoutView(player)
        await ctx.send(view=view)


async def setup(bot: commands.Bot):
    # Retrieve or create PlayerManager attached to bot
    if not hasattr(bot, "player_manager"):
        bot.player_manager = PlayerManager(bot)
    await bot.add_cog(MusicCog(bot, bot.player_manager))
