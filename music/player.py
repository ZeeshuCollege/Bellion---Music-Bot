import asyncio
import time
import random
from typing import Optional, List, Dict
import discord
from discord.ext import commands

from config import DEFAULT_VOLUME, DEFAULT_LOOP, DEFAULT_AUTOPLAY
from music.track import Track
from ui.embeds import (
    create_now_playing_embed,
    create_nothing_playing_embed,
    create_queue_empty_embed
)
from ui.views import NowPlayingView

class GuildPlayer:
    """
    Manages audio playback, queue, loop mode, volume, and voice connection for a single guild.
    """
    def __init__(self, bot: commands.Bot, guild: discord.Guild):
        self.bot = bot
        self.guild = guild
        self.voice_client: Optional[discord.VoiceClient] = None
        
        self.queue: List[Track] = []
        self.history: List[Track] = []
        self.current: Optional[Track] = None
        
        self.volume: float = DEFAULT_VOLUME
        self.loop_mode: str = DEFAULT_LOOP  # "off", "track", "queue"
        self.autoplay: bool = DEFAULT_AUTOPLAY
        
        self._start_time: float = 0.0
        self._pause_time: float = 0.0
        self._accumulated_pause: float = 0.0
        self.is_paused: bool = False
        
        self.now_playing_message: Optional[discord.Message] = None
        self._idle_task: Optional[asyncio.Task] = None
        self._lock = asyncio.Lock()

    @property
    def is_playing(self) -> bool:
        return self.voice_client is not None and self.voice_client.is_playing()

    def get_elapsed(self) -> float:
        """Returns elapsed playback time in seconds for the current track."""
        if not self.current or self._start_time == 0:
            return 0.0
        if self.is_paused and self._pause_time > 0:
            return self._pause_time - self._start_time - self._accumulated_pause
        return time.time() - self._start_time - self._accumulated_pause

    async def add_track(self, track: Track, play_now: bool = False):
        """Adds a track to the queue, or plays immediately if idle."""
        async with self._lock:
            self._cancel_idle_timer()
            if play_now:
                self.queue.insert(0, track)
            else:
                self.queue.append(track)

            if not self.is_playing and not self.is_paused and self.current is None:
                await self._play_next()

    async def _play_next(self):
        """Internal method to trigger the next song."""
        if self.voice_client is None or not self.voice_client.is_connected():
            return

        # Determine next track based on loop mode
        if self.current and self.loop_mode == "track":
            next_track = self.current
        elif self.current and self.loop_mode == "queue":
            self.queue.append(self.current)
            if self.queue:
                next_track = self.queue.pop(0)
            else:
                next_track = None
        else:
            if self.current:
                self.history.append(self.current)
                if len(self.history) > 20:
                    self.history.pop(0)

            if self.queue:
                next_track = self.queue.pop(0)
            elif self.autoplay and self.history:
                # Autoplay random track from library
                from music.library import library
                all_tracks = library.get_all()
                if all_tracks:
                    random_data = random.choice(all_tracks)
                    next_track = Track(
                        title=random_data["title"],
                        artist=random_data["artist"],
                        duration=random_data["duration"],
                        filepath=random_data["filepath"],
                        requester=self.bot.user
                    )
                else:
                    next_track = None
            else:
                next_track = None

        if next_track is None:
            self.current = None
            self._start_idle_timer()
            return

        self.current = next_track
        self._start_time = time.time()
        self._accumulated_pause = 0.0
        self.is_paused = False

        # Create FFmpeg audio source with volume
        ffmpeg_opts = {
            'options': '-vn -loglevel error'
        }
        try:
            source = discord.FFmpegPCMAudio(next_track.filepath, **ffmpeg_opts)
            transformed = discord.PCMVolumeTransformer(source, volume=self.volume)
        except Exception as e:
            print(f"Error creating audio source: {e}")
            await self._play_next()
            return

        def after_callback(error):
            if error:
                print(f"Player error for guild {self.guild.id}: {error}")
            # Schedule next track without blocking the audio worker thread
            asyncio.run_coroutine_threadsafe(self._play_next(), self.bot.loop)

        self.voice_client.play(transformed, after=after_callback)
        await self._send_now_playing_card()

    async def _send_now_playing_card(self, channel: Optional[discord.TextChannel] = None):
        """Sends or updates the Now Playing card in the designated channel."""
        if not self.current:
            return

        bot_avatar = self.bot.user.display_avatar.url if self.bot.user else None
        embed = create_now_playing_embed(self.current, elapsed=0.0, bot_avatar_url=bot_avatar)
        view = NowPlayingView(self)

        target_channel = channel or (self.now_playing_message.channel if self.now_playing_message else None)
        if target_channel is None:
            # Fallback to first text channel bot can send messages to
            for ch in self.guild.text_channels:
                if ch.permissions_for(self.guild.me).send_messages:
                    target_channel = ch
                    break

        if target_channel:
            try:
                msg = await target_channel.send(embed=embed, view=view)
                self.now_playing_message = msg
            except Exception as e:
                print(f"Failed to send Now Playing embed: {e}")

    async def update_now_playing_card(self):
        """Updates the active Now Playing card with live progress and button states."""
        if not self.now_playing_message or not self.current:
            return
        try:
            bot_avatar = self.bot.user.display_avatar.url if self.bot.user else None
            embed = create_now_playing_embed(self.current, elapsed=self.get_elapsed(), bot_avatar_url=bot_avatar)
            view = NowPlayingView(self)
            await self.now_playing_message.edit(embed=embed, view=view)
        except Exception:
            pass

    async def pause(self) -> bool:
        """Pause current track."""
        if self.voice_client and self.voice_client.is_playing():
            self.voice_client.pause()
            self.is_paused = True
            self._pause_time = time.time()
            await self.update_now_playing_card()
            return True
        return False

    async def resume(self) -> bool:
        """Resume playback."""
        if self.voice_client and self.voice_client.is_paused():
            self.voice_client.resume()
            self.is_paused = False
            if self._pause_time > 0:
                self._accumulated_pause += time.time() - self._pause_time
                self._pause_time = 0.0
            await self.update_now_playing_card()
            return True
        return False

    async def toggle_play_pause(self) -> bool:
        if self.is_paused:
            return await self.resume()
        else:
            return await self.pause()

    async def skip(self) -> Optional[Track]:
        """Skip current track."""
        skipped = self.current
        if self.voice_client and (self.voice_client.is_playing() or self.voice_client.is_paused()):
            # Changing loop mode temporarily if single-track loop is on so skip actually moves ahead
            current_loop = self.loop_mode
            if self.loop_mode == "track":
                self.loop_mode = "off"
            self.voice_client.stop()
            self.loop_mode = current_loop
        return skipped

    async def previous(self) -> bool:
        """Plays the previous track from history."""
        if not self.history:
            return False
        prev_track = self.history.pop()
        if self.current:
            self.queue.insert(0, self.current)
        self.queue.insert(0, prev_track)
        if self.voice_client and (self.voice_client.is_playing() or self.voice_client.is_paused()):
            self.voice_client.stop()
        else:
            await self._play_next()
        return True

    async def stop(self):
        """Stop music, clear queue, and reset state."""
        self.queue.clear()
        self.current = None
        self.is_paused = False
        if self.voice_client and (self.voice_client.is_playing() or self.voice_client.is_paused()):
            self.voice_client.stop()
        self._start_idle_timer()

    def set_volume(self, volume: float):
        """Set player volume between 0.0 and 1.0 (0% - 100%)."""
        self.volume = max(0.0, min(1.0, volume))
        if self.voice_client and self.voice_client.source:
            if isinstance(self.voice_client.source, discord.PCMVolumeTransformer):
                self.voice_client.source.volume = self.volume

    def cycle_loop(self) -> str:
        """Cycle loop mode: off -> track -> queue -> off."""
        modes = ["off", "track", "queue"]
        idx = modes.index(self.loop_mode) if self.loop_mode in modes else 0
        self.loop_mode = modes[(idx + 1) % len(modes)]
        return self.loop_mode

    def shuffle_queue(self):
        """Shuffle remaining queue."""
        if len(self.queue) > 1:
            random.shuffle(self.queue)

    def _start_idle_timer(self):
        """Starts 5 minute inactivity countdown before disconnecting."""
        self._cancel_idle_timer()
        self._idle_task = asyncio.create_task(self._idle_disconnect())

    def _cancel_idle_timer(self):
        if self._idle_task and not self._idle_task.done():
            self._idle_task.cancel()
            self._idle_task = None

    async def _idle_disconnect(self):
        try:
            await asyncio.sleep(300)  # 5 minutes
            if self.voice_client and self.voice_client.is_connected() and not self.is_playing:
                await self.voice_client.disconnect()
                self.voice_client = None
        except asyncio.CancelledError:
            pass

    async def destroy(self):
        """Cleanup player resources."""
        self._cancel_idle_timer()
        if self.voice_client and self.voice_client.is_connected():
            await self.voice_client.disconnect()
        self.queue.clear()
        self.history.clear()
        self.current = None


class PlayerManager:
    """Manages guild players across servers."""
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._players: Dict[int, GuildPlayer] = {}

    def get_player(self, guild: discord.Guild) -> GuildPlayer:
        if guild.id not in self._players:
            self._players[guild.id] = GuildPlayer(self.bot, guild)
        return self._players[guild.id]

    async def cleanup_guild(self, guild_id: int):
        if guild_id in self._players:
            await self._players[guild_id].destroy()
            del self._players[guild_id]
