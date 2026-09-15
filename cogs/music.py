from typing import List, Optional
import discord
from discord import app_commands
from discord.ext import commands

from music.library import library
from music.track import Track
from music.player import PlayerManager
from ui.embeds import (
    create_now_playing_embed,
    create_queue_embed,
    create_search_results_embed,
    create_nothing_playing_embed,
    create_queue_empty_embed,
    create_invalid_search_embed,
    create_track_queued_embed
)
from ui.views import NowPlayingView, QueueView, SearchView

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
    @app_commands.command(name="play", description="Play a track from library or resume playback")
    @app_commands.describe(query="Song title, keyword, or select from autocomplete")
    async def play_slash(self, interaction: discord.Interaction, query: Optional[str] = None):
        player = self.players.get_player(interaction.guild)

        # If no query provided, check if we should resume playback
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
                return await interaction.response.send_message(embed=create_nothing_playing_embed(), ephemeral=True)

        matches = library.search(query, limit=1)
        if not matches:
            return await interaction.response.send_message(embed=create_invalid_search_embed(query), ephemeral=True)

        vc = await self._ensure_voice(interaction)
        if not vc:
            return

        track_data = matches[0]
        track = Track(
            title=track_data["title"],
            artist=track_data["artist"],
            duration=track_data["duration"],
            filepath=track_data["filepath"],
            requester=interaction.user
        )

        is_already_active = player.is_playing or player.current is not None
        position = len(player.queue) + (1 if player.current else 0)

        await player.add_track(track)

        if is_already_active:
            await interaction.response.send_message(embed=create_track_queued_embed(track, position=position))
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

    # ------------------ /search ------------------
    @app_commands.command(name="search", description="Search for songs and choose using buttons or dropdown")
    @app_commands.describe(query="Song title or artist to search for")
    async def search_slash(self, interaction: discord.Interaction, query: str):
        vc = await self._ensure_voice(interaction)
        if not vc:
            return

        matches = library.search(query, limit=5)
        if not matches:
            return await interaction.response.send_message(embed=create_invalid_search_embed(query), ephemeral=True)

        player = self.players.get_player(interaction.guild)
        embed = create_search_results_embed(query, matches)
        view = SearchView(player, matches, interaction.user)
        await interaction.response.send_message(embed=embed, view=view)

    # ------------------ /pause ------------------
    @app_commands.command(name="pause", description="Pause current track")
    async def pause_slash(self, interaction: discord.Interaction):
        player = self.players.get_player(interaction.guild)
        if await player.pause():
            await interaction.response.send_message("⏸️ Playback paused.", ephemeral=True)
        else:
            await interaction.response.send_message(embed=create_nothing_playing_embed(), ephemeral=True)

    # ------------------ /resume ------------------
    @app_commands.command(name="resume", description="Resume paused track")
    async def resume_slash(self, interaction: discord.Interaction):
        player = self.players.get_player(interaction.guild)
        if await player.resume():
            await interaction.response.send_message("▶️ Playback resumed.", ephemeral=True)
        else:
            await interaction.response.send_message(embed=create_nothing_playing_embed(), ephemeral=True)

    # ------------------ /skip ------------------
    @app_commands.command(name="skip", description="Skip to next track in queue")
    async def skip_slash(self, interaction: discord.Interaction):
        player = self.players.get_player(interaction.guild)
        skipped = await player.skip()
        if skipped:
            await interaction.response.send_message(f"⏭️ Skipped **{skipped.title}**.", ephemeral=True)
        else:
            await interaction.response.send_message(embed=create_nothing_playing_embed(), ephemeral=True)

    # ------------------ /previous ------------------
    @app_commands.command(name="previous", description="Replay the previous track")
    async def previous_slash(self, interaction: discord.Interaction):
        player = self.players.get_player(interaction.guild)
        if await player.previous():
            await interaction.response.send_message("⏮️ Replaying previous track.", ephemeral=True)
        else:
            await interaction.response.send_message("❌ No previous track in history.", ephemeral=True)

    # ------------------ /stop ------------------
    @app_commands.command(name="stop", description="Stop music and clear queue")
    async def stop_slash(self, interaction: discord.Interaction):
        player = self.players.get_player(interaction.guild)
        await player.stop()
        await interaction.response.send_message("⏹️ Playback stopped and queue cleared.")

    # ------------------ /nowplaying ------------------
    @app_commands.command(name="nowplaying", description="Show active player card with real-time controls")
    async def nowplaying_slash(self, interaction: discord.Interaction):
        player = self.players.get_player(interaction.guild)
        if not player.current:
            return await interaction.response.send_message(embed=create_nothing_playing_embed(), ephemeral=True)

        embed = create_now_playing_embed(player.current, elapsed=player.get_elapsed())
        view = NowPlayingView(player)
        await interaction.response.send_message(embed=embed, view=view)

    # ------------------ /queue ------------------
    @app_commands.command(name="queue", description="View active playlist queue with pagination")
    @app_commands.describe(page="Queue page number")
    async def queue_slash(self, interaction: discord.Interaction, page: Optional[int] = 1):
        player = self.players.get_player(interaction.guild)
        if not player.current and not player.queue:
            return await interaction.response.send_message(embed=create_queue_empty_embed(), ephemeral=True)

        embed = create_queue_embed(player.queue, player.current, page=page or 1)
        view = QueueView(player, current_page=page or 1)
        await interaction.response.send_message(embed=embed, view=view)

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

    # ================== Traditional Prefix Commands (!) ==================
    @commands.command(name="play", aliases=["p"])
    async def play_prefix(self, ctx: commands.Context, *, query: Optional[str] = None):
        """Play a song using !play <query> or !p"""
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
                return await ctx.send(embed=create_nothing_playing_embed())

        matches = library.search(query, limit=1)
        if not matches:
            return await ctx.send(embed=create_invalid_search_embed(query))

        track_data = matches[0]
        track = Track(
            title=track_data["title"],
            artist=track_data["artist"],
            duration=track_data["duration"],
            filepath=track_data["filepath"],
            requester=ctx.author
        )

        is_already_active = player.is_playing or player.current is not None
        pos = len(player.queue) + (1 if player.current else 0)

        await player.add_track(track)

        if is_already_active:
            await ctx.send(embed=create_track_queued_embed(track, position=pos))
        else:
            await ctx.send(f"🎵 Now loading **{track.title}**...")

    @commands.command(name="skip", aliases=["s"])
    async def skip_prefix(self, ctx: commands.Context):
        player = self.players.get_player(ctx.guild)
        skipped = await player.skip()
        if skipped:
            await ctx.send(f"⏭️ Skipped **{skipped.title}**.")
        else:
            await ctx.send(embed=create_nothing_playing_embed())

    @commands.command(name="pause")
    async def pause_prefix(self, ctx: commands.Context):
        player = self.players.get_player(ctx.guild)
        if await player.pause():
            await ctx.send("⏸️ Paused playback.")
        else:
            await ctx.send(embed=create_nothing_playing_embed())

    @commands.command(name="resume")
    async def resume_prefix(self, ctx: commands.Context):
        player = self.players.get_player(ctx.guild)
        if await player.resume():
            await ctx.send("▶️ Resumed playback.")
        else:
            await ctx.send(embed=create_nothing_playing_embed())

    @commands.command(name="stop")
    async def stop_prefix(self, ctx: commands.Context):
        player = self.players.get_player(ctx.guild)
        await player.stop()
        await ctx.send("⏹️ Playback stopped and queue cleared.")

    @commands.command(name="queue", aliases=["q"])
    async def queue_prefix(self, ctx: commands.Context, page: int = 1):
        player = self.players.get_player(ctx.guild)
        if not player.current and not player.queue:
            return await ctx.send(embed=create_queue_empty_embed())
        embed = create_queue_embed(player.queue, player.current, page=page)
        view = QueueView(player, current_page=page)
        await ctx.send(embed=embed, view=view)

    @commands.command(name="nowplaying", aliases=["np"])
    async def nowplaying_prefix(self, ctx: commands.Context):
        player = self.players.get_player(ctx.guild)
        if not player.current:
            return await ctx.send(embed=create_nothing_playing_embed())
        embed = create_now_playing_embed(player.current, elapsed=player.get_elapsed())
        view = NowPlayingView(player)
        await ctx.send(embed=embed, view=view)


async def setup(bot: commands.Bot):
    # Retrieve or create PlayerManager attached to bot
    if not hasattr(bot, "player_manager"):
        bot.player_manager = PlayerManager(bot)
    await bot.add_cog(MusicCog(bot, bot.player_manager))
