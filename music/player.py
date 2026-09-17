import asyncio
import time
import random
from typing import Optional, List, Dict
import discord
from discord.ext import commands

from config import DEFAULT_VOLUME, DEFAULT_LOOP, DEFAULT_AUTOPLAY
from music.track import Track
from ui.views import NowPlayingLayoutView, StatusLayoutView

# Audio Filter Presets (FFmpeg audio filter strings)
AUDIO_FILTERS: Dict[str, str] = {
    "8d": "apulsator=hz=0.125",
    "bassboost": "equalizer=f=60:width_type=h:width=50:g=10,equalizer=f=125:width_type=h:width=50:g=6",
    "nightcore": "asetrate=48000*1.25,aresample=48000",
    "vaporwave": "asetrate=48000*0.8,aresample=48000",
    "pop": "equalizer=f=1000:width_type=h:width=200:g=5,equalizer=f=3000:width_type=h:width=500:g=4",
}

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
        self.filter: Optional[str] = None
        self._is_reapplying_filter: bool = False
        self._play_id: int = 0
        
        self._start_time: float = 0.0
        self._pause_time: float = 0.0
        self._accumulated_pause: float = 0.0
        self.is_paused: bool = False
        
        self.now_playing_message: Optional[discord.Message] = None
        self.bound_channel: Optional[discord.abc.Messageable] = None
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

    async def add_track(self, track: Track, play_now: bool = False) -> bool:
        """Adds a track to the queue, or plays immediately if idle. Returns True if started playing immediately, False if queued."""
        async with self._lock:
            self._cancel_idle_timer()
            was_idle = (not self.is_playing and not self.is_paused and self.current is None)
            if play_now:
                self.queue.insert(0, track)
            else:
                self.queue.append(track)

            if was_idle:
                await self._play_next()
                return True
            return False

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
                # Autoplay: resolve related track from YouTube or local library
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
                    from music.resolver import resolve_related_track
                    last_track = self.history[-1]
                    next_track = await resolve_related_track(last_track.title, last_track.artist)
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

        # Create FFmpeg audio source with volume (handles local and URLs)
        is_stream = next_track.source_type == "stream" or next_track.filepath.startswith("http")
        before_opts = '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5' if is_stream else None

        ffmpeg_options = '-vn -loglevel error -nostdin'
        if self.filter and self.filter in AUDIO_FILTERS:
            ffmpeg_options += f' -af "{AUDIO_FILTERS[self.filter]}"'

        try:
            if before_opts:
                source = discord.FFmpegPCMAudio(
                    next_track.filepath,
                    options=ffmpeg_options,
                    before_options=before_opts
                )
            else:
                source = discord.FFmpegPCMAudio(
                    next_track.filepath,
                    options=ffmpeg_options
                )
            transformed = discord.PCMVolumeTransformer(source, volume=self.volume)
        except Exception as e:
            print(f"Error creating audio source: {e}")
            await self._play_next()
            return

        self._play_id += 1
        current_play_id = self._play_id

        def after_callback(error, play_id=current_play_id):
            if self._play_id != play_id or self._is_reapplying_filter:
                return
            if error:
                print(f"Player error for guild {self.guild.id}: {error}")
            # Schedule next track without blocking the audio worker thread
            asyncio.run_coroutine_threadsafe(self._play_next(), self.bot.loop)

        self.voice_client.play(transformed, after=after_callback)
        await self._send_now_playing_card()

    async def _send_now_playing_card(self, channel: Optional[discord.TextChannel] = None):
        """Sends or updates the Now Playing card in the designated channel using Components V2."""
        if not self.current:
            return

        view = NowPlayingLayoutView(self)

        # If an active Now Playing card already exists from a previous song, delete it
        # so the new song's player card is always posted fresh at the bottom of the chat
        if self.now_playing_message:
            try:
                await self.now_playing_message.delete()
            except Exception:
                pass
            self.now_playing_message = None

        target_channel = channel or getattr(self, "bound_channel", None)
        if target_channel is None:
            # Fallback to first text channel bot can send messages to
            for ch in self.guild.text_channels:
                if ch.permissions_for(self.guild.me).send_messages:
                    target_channel = ch
                    break

        if target_channel:
            try:
                msg = await target_channel.send(view=view)
                self.now_playing_message = msg
            except Exception as e:
                print(f"Failed to send Now Playing view: {e}")

    async def update_now_playing_card(self):
        """Updates the active Now Playing card with live button states."""
        if not self.now_playing_message or not self.current:
            return
        try:
            view = NowPlayingLayoutView(self)
            await self.now_playing_message.edit(view=view)
        except Exception:
            pass

    async def pause(self, update_card: bool = True) -> bool:
        """Pause current track."""
        if not self.current:
            return False
        if self.voice_client and self.voice_client.is_playing():
            self.voice_client.pause()
        self.is_paused = True
        self._pause_time = time.time()
        if update_card:
            await self.update_now_playing_card()
        return True

    async def resume(self, update_card: bool = True) -> bool:
        """Resume playback."""
        if not self.current:
            return False
        if self.voice_client and self.voice_client.is_paused():
            self.voice_client.resume()
        self.is_paused = False
        if self._pause_time > 0:
            self._accumulated_pause += time.time() - self._pause_time
            self._pause_time = 0.0
        if update_card:
            await self.update_now_playing_card()
        return True

    async def toggle_play_pause(self, update_card: bool = True) -> bool:
        if self.is_paused:
            return await self.resume(update_card=update_card)
        else:
            return await self.pause(update_card=update_card)

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
        
        current_loop = self.loop_mode
        if self.loop_mode == "track":
            self.loop_mode = "off"
            
        if self.voice_client and (self.voice_client.is_playing() or self.voice_client.is_paused()):
            self.voice_client.stop()
        else:
            await self._play_next()
            
        self.loop_mode = current_loop
        return True

    async def set_filter(self, filter_name: Optional[str], update_card: bool = True) -> bool:
        """Applies an audio filter ('8d', 'bassboost', 'nightcore', 'vaporwave', 'pop', or 'clear'/None)."""
        if filter_name == "clear" or not filter_name:
            self.filter = None
        elif filter_name in AUDIO_FILTERS:
            self.filter = filter_name
        else:
            return False

        if not self.current or not self.voice_client or not self.voice_client.is_connected():
            if update_card:
                await self.update_now_playing_card()
            return True

        if not (self.voice_client.is_playing() or self.voice_client.is_paused()):
            if update_card:
                await self.update_now_playing_card()
            return True

        # Re-create source at current playback position
        elapsed = max(0.0, self.get_elapsed())
        is_stream = self.current.source_type == "stream" or self.current.filepath.startswith("http")
        
        # Output seeking (-ss in options) prevents premature connection abort on HTTP audio streams
        seek_str = f"-ss {int(elapsed)}" if elapsed > 1 else ""
        before_opts = '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5' if is_stream else None

        ffmpeg_options = '-vn -loglevel error -nostdin'
        if seek_str:
            ffmpeg_options = f'{seek_str} {ffmpeg_options}'
        if self.filter and self.filter in AUDIO_FILTERS:
            ffmpeg_options += f' -af "{AUDIO_FILTERS[self.filter]}"'

        try:
            if before_opts:
                source = discord.FFmpegPCMAudio(
                    self.current.filepath,
                    options=ffmpeg_options,
                    before_options=before_opts
                )
            else:
                source = discord.FFmpegPCMAudio(
                    self.current.filepath,
                    options=ffmpeg_options
                )
            transformed = discord.PCMVolumeTransformer(source, volume=self.volume)
        except Exception as e:
            print(f"Error reapplying audio filter: {e}")
            return False

        # Invalidate any callbacks from the old audio playback thread
        self._play_id += 1
        new_play_id = self._play_id
        self._is_reapplying_filter = True
        
        was_paused = self.is_paused

        try:
            if self.voice_client and (self.voice_client.is_playing() or self.voice_client.is_paused()):
                self.voice_client.stop()
        except Exception as e:
            print(f"Error stopping voice client for filter: {e}")
        finally:
            self._is_reapplying_filter = False

        self._start_time = time.time() - elapsed
        self._accumulated_pause = 0.0

        def after_callback(error, play_id=new_play_id):
            if self._play_id != play_id or self._is_reapplying_filter:
                return
            if error:
                print(f"Player error for guild {self.guild.id}: {error}")
            asyncio.run_coroutine_threadsafe(self._play_next(), self.bot.loop)

        self.voice_client.play(transformed, after=after_callback)

        if was_paused:
            self.voice_client.pause()
            self.is_paused = True
            self._pause_time = time.time()
        else:
            self.is_paused = False
            self._pause_time = 0.0

        if update_card:
            await self.update_now_playing_card()

        return True

    async def stop(self):
        """Stop music, clear queue, and reset state."""
        self._play_id += 1
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
        self._play_id += 1
        self._cancel_idle_timer()
        if self.voice_client and self.voice_client.is_connected():
            await self.voice_client.disconnect()
        self.queue.clear()
        self.history.clear()
        self.current = None


from typing import Optional, List, Dict, Any

class PlayerManager:
    """Manages guild players across servers."""
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._players: Dict[int, GuildPlayer] = {}

    def get_player(self, guild: Any) -> GuildPlayer:
        if not guild or not hasattr(guild, "id"):
            raise ValueError("Invalid guild passed to get_player")
        if guild.id not in self._players:
            self._players[guild.id] = GuildPlayer(self.bot, guild)
        return self._players[guild.id]

    async def cleanup_guild(self, guild_id: int):
        if guild_id in self._players:
            await self._players[guild_id].destroy()
            del self._players[guild_id]
