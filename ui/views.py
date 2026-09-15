from typing import List, Optional
import discord
from discord import ui

from config import SUPPORT_SERVER_URL, POWERED_BY_TEXT, get_track_thumbnail
from music.track import Track

class NowPlayingLayoutView(ui.LayoutView):
    """
    Discord Components V2 LayoutView matching the reference screenshot.
    Uses Container (type 17), Section (type 9) with Thumbnail accessory (type 11),
    and Action Rows with styled buttons.
    """
    def __init__(self, player, timeout: Optional[float] = None):
        super().__init__(timeout=timeout)
        self.player = player
        self.rebuild()

    def rebuild(self):
        """Reconstruct the components tree based on current player state."""
        self.clear_items()
        
        container = ui.Container()
        
        # 1. Header: 💽 Now Playing
        header = ui.TextDisplay("### :minidisc: Now Playing")
        container.add_item(header)
        
        track = self.player.current
        if track:
            # Thumbnail accessory
            thumb_url = track.thumbnail_url or get_track_thumbnail(track.title, track.artist)
            thumb = ui.Thumbnail(thumb_url)
            
            # Content with blockquote formatting matching screenshot
            requester_name = track.get_requester_display()
            content = (
                f"> **[{track.title}]({SUPPORT_SERVER_URL})** - `{track.artist}`\n"
                f"> Duration: `{track.formatted_duration}`\n"
                f"> Requested by {requester_name}"
            )
            section = ui.Section(ui.TextDisplay(content), accessory=thumb)
            container.add_item(section)
        else:
            container.add_item(ui.TextDisplay("> *Nothing is currently playing.*"))
            
        # 2. Powered by footer
        footer = ui.TextDisplay(POWERED_BY_TEXT)
        container.add_item(footer)
        
        # 3. Action Row 1: Pause/Resume, Skip, Stop (Danger), Loop
        pause_label = "Resume" if self.player.is_paused else "Pause"
        btn_pause = ui.Button(label=pause_label, style=discord.ButtonStyle.secondary, custom_id="v2_pause")
        btn_skip = ui.Button(label="Skip", style=discord.ButtonStyle.secondary, custom_id="v2_skip")
        btn_stop = ui.Button(label="Stop", style=discord.ButtonStyle.danger, custom_id="v2_stop")
        
        loop_labels = {
            "off": "Loop",
            "track": "Loop: 1",
            "queue": "Loop: All"
        }
        loop_label = loop_labels.get(self.player.loop_mode, "Loop")
        btn_loop = ui.Button(label=loop_label, style=discord.ButtonStyle.secondary, custom_id="v2_loop")
        
        btn_pause.callback = self.on_pause
        btn_skip.callback = self.on_skip
        btn_stop.callback = self.on_stop
        btn_loop.callback = self.on_loop
        
        row1 = ui.ActionRow(btn_pause, btn_skip, btn_stop, btn_loop)
        container.add_item(row1)
        
        # 4. Action Row 2: Shuffle
        btn_shuffle = ui.Button(label="Shuffle", style=discord.ButtonStyle.secondary, custom_id="v2_shuffle")
        btn_shuffle.callback = self.on_shuffle
        row2 = ui.ActionRow(btn_shuffle)
        container.add_item(row2)
        
        self.add_item(container)

    def _check_voice(self, interaction: discord.Interaction) -> bool:
        if not interaction.user or not isinstance(interaction.user, discord.Member):
            return False
        if not interaction.user.voice or not interaction.user.voice.channel:
            return False
        vc = self.player.guild.voice_client
        if vc and interaction.user.voice.channel != vc.channel:
            return False
        return True

    async def on_pause(self, interaction: discord.Interaction):
        if not self._check_voice(interaction):
            return await interaction.response.send_message("❌ You must be in the same voice channel!", ephemeral=True)
        
        if self.player.is_paused:
            await self.player.resume()
        else:
            await self.player.pause()
            
        self.rebuild()
        await interaction.response.edit_message(view=self)

    async def on_skip(self, interaction: discord.Interaction):
        if not self._check_voice(interaction):
            return await interaction.response.send_message("❌ You must be in the same voice channel!", ephemeral=True)
            
        skipped = await self.player.skip()
        if skipped:
            await interaction.response.send_message(f"⏭️ Skipped **{skipped.title}**", ephemeral=True)
        else:
            await interaction.response.send_message("❌ Nothing is playing.", ephemeral=True)

    async def on_stop(self, interaction: discord.Interaction):
        if not self._check_voice(interaction):
            return await interaction.response.send_message("❌ You must be in the same voice channel!", ephemeral=True)
            
        await self.player.stop()
        view = StatusLayoutView(
            title="### 🎵 Nothing is playing",
            description="Playback stopped and queue cleared.\nUse `/play` to start a song."
        )
        await interaction.response.edit_message(view=view)

    async def on_loop(self, interaction: discord.Interaction):
        if not self._check_voice(interaction):
            return await interaction.response.send_message("❌ You must be in the same voice channel!", ephemeral=True)
            
        self.player.cycle_loop()
        self.rebuild()
        await interaction.response.edit_message(view=self)

    async def on_shuffle(self, interaction: discord.Interaction):
        if not self._check_voice(interaction):
            return await interaction.response.send_message("❌ You must be in the same voice channel!", ephemeral=True)
            
        self.player.shuffle_queue()
        await interaction.response.send_message("🔀 Queue has been shuffled!", ephemeral=True)


class QueueLayoutView(ui.LayoutView):
    """
    Paginated queue browser using Discord Components V2.
    """
    def __init__(self, player, current_page: int = 1, timeout: float = 120.0):
        super().__init__(timeout=timeout)
        self.player = player
        self.current_page = current_page
        self.rebuild()

    def rebuild(self):
        self.clear_items()
        container = ui.Container()
        
        # Header
        container.add_item(ui.TextDisplay("### :hash: Current Queue"))
        
        all_tracks = []
        if self.player.current:
            all_tracks.append(self.player.current)
        all_tracks.extend(self.player.queue)
        
        if not all_tracks:
            container.add_item(ui.TextDisplay("> *The queue is empty. Add songs using `/play`!*"))
        else:
            lines = []
            if self.player.current and self.current_page == 1:
                lines.append(f"> **Now Playing:**")
                lines.append(f"> ▶ **[{self.player.current.title}]({SUPPORT_SERVER_URL})** - `{self.player.current.artist}` (`{self.player.current.formatted_duration}`)\n")
                if self.player.queue:
                    lines.append(f"> **Up Next:**")
            
            start_idx = (self.current_page - 1) * 5
            end_idx = start_idx + 5
            page_tracks = self.player.queue[start_idx:end_idx]
            
            for i, track in enumerate(page_tracks, start=start_idx + 1):
                lines.append(f"> `{i}.` **[{track.title}]({SUPPORT_SERVER_URL})** - `{track.artist}` (`{track.formatted_duration}`)")
                
            total_pages = max(1, (len(self.player.queue) + 4) // 5) if self.player.queue else 1
            lines.append(f"\n-# Page {self.current_page}/{total_pages} • Total: {len(self.player.queue)} tracks in queue")
            container.add_item(ui.TextDisplay("\n".join(lines)))
            
        # Navigation buttons
        btn_prev = ui.Button(label="◀ Previous", style=discord.ButtonStyle.secondary, disabled=(self.current_page <= 1))
        total_pages = max(1, (len(self.player.queue) + 4) // 5) if self.player.queue else 1
        btn_next = ui.Button(label="Next ▶", style=discord.ButtonStyle.secondary, disabled=(self.current_page >= total_pages))
        btn_clear = ui.Button(label="Clear Queue", style=discord.ButtonStyle.danger)
        
        btn_prev.callback = self.on_prev
        btn_next.callback = self.on_next
        btn_clear.callback = self.on_clear
        
        row = ui.ActionRow(btn_prev, btn_next, btn_clear)
        container.add_item(row)
        
        self.add_item(container)

    async def on_prev(self, interaction: discord.Interaction):
        self.current_page = max(1, self.current_page - 1)
        self.rebuild()
        await interaction.response.edit_message(view=self)

    async def on_next(self, interaction: discord.Interaction):
        total_pages = max(1, (len(self.player.queue) + 4) // 5) if self.player.queue else 1
        self.current_page = min(total_pages, self.current_page + 1)
        self.rebuild()
        await interaction.response.edit_message(view=self)

    async def on_clear(self, interaction: discord.Interaction):
        self.player.queue.clear()
        self.current_page = 1
        self.rebuild()
        await interaction.response.edit_message(view=self)


class SearchLayoutView(ui.LayoutView):
    """
    Search results layout using Discord Components V2.
    """
    def __init__(self, player, tracks: List[dict], user: discord.Member, query: str, timeout: float = 60.0):
        super().__init__(timeout=timeout)
        self.player = player
        self.tracks = tracks
        self.user = user
        self.query = query
        self.rebuild()

    def rebuild(self):
        self.clear_items()
        container = ui.Container()
        
        container.add_item(ui.TextDisplay(f"### :mag: Search Results for `{self.query}`"))
        
        lines = []
        for idx, t in enumerate(self.tracks[:5], start=1):
            dur = int(t.get("duration", 0))
            mins = dur // 60
            secs = dur % 60
            lines.append(f"> `{idx}.` **[{t['title']}]({SUPPORT_SERVER_URL})** - `{t['artist']}` (`{mins}:{secs:02d}`)")
            
        lines.append("\n-# Click a number below to play that track immediately:")
        container.add_item(ui.TextDisplay("\n".join(lines)))
        
        buttons = []
        for idx in range(min(5, len(self.tracks))):
            btn = ui.Button(label=str(idx + 1), style=discord.ButtonStyle.primary, custom_id=f"v2_search_{idx}")
            btn.callback = self.make_callback(idx)
            buttons.append(btn)
            
        if buttons:
            row = ui.ActionRow(*buttons)
            container.add_item(row)
            
        self.add_item(container)

    def make_callback(self, index: int):
        async def callback(interaction: discord.Interaction):
            if interaction.user.id != self.user.id:
                return await interaction.response.send_message("❌ This search is for someone else!", ephemeral=True)
            if not getattr(interaction.user, "voice", None) or not interaction.user.voice.channel:
                return await interaction.response.send_message("❌ You must be in a voice channel!", ephemeral=True)
                
            track_data = self.tracks[index]
            track = Track(
                title=track_data["title"],
                artist=track_data["artist"],
                duration=track_data["duration"],
                filepath=track_data["filepath"],
                requester=interaction.user
            )
            
            position = len(self.player.queue) + (1 if self.player.current else 0)
            await self.player.add_track(track)
            
            view = StatusLayoutView(
                title="### :white_check_mark: Track Queued",
                description=(
                    f"> **[{track.title}]({SUPPORT_SERVER_URL})** - `{track.artist}`\n"
                    f"> Duration: `{track.formatted_duration}`\n"
                    f"> Position in queue: `#{position}`\n\n"
                    f"-# Added to queue successfully!"
                ),
                thumbnail_url=get_track_thumbnail(track.title, track.artist)
            )
            await interaction.response.edit_message(view=view)
        return callback


class StatusLayoutView(ui.LayoutView):
    """
    Standard Components V2 status card for notifications, alerts, and confirmations.
    """
    def __init__(self, title: str, description: str, thumbnail_url: Optional[str] = None, timeout: Optional[float] = None):
        super().__init__(timeout=timeout)
        container = ui.Container()
        container.add_item(ui.TextDisplay(title))
        
        if thumbnail_url:
            section = ui.Section(ui.TextDisplay(description), accessory=ui.Thumbnail(thumbnail_url))
            container.add_item(section)
        else:
            container.add_item(ui.TextDisplay(description))
            
        self.add_item(container)


class SettingsLayoutView(ui.LayoutView):
    """
    Settings card using Discord Components V2.
    """
    def __init__(self, player, timeout: float = 120.0):
        super().__init__(timeout=timeout)
        self.player = player
        self.rebuild()

    def rebuild(self):
        self.clear_items()
        container = ui.Container()
        container.add_item(ui.TextDisplay("### :gear: Audio Settings"))

        vol_pct = int(self.player.volume * 100)
        loop_display = {
            "off": "Off",
            "track": "Single Track",
            "queue": "Entire Queue"
        }.get(self.player.loop_mode, self.player.loop_mode.capitalize())
        autoplay_display = "Enabled" if self.player.autoplay else "Disabled"

        content = (
            f"> **Volume:** `{vol_pct}%`\n"
            f"> **Loop Mode:** `{loop_display}`\n"
            f"> **Autoplay:** `{autoplay_display}`"
        )
        container.add_item(ui.TextDisplay(content))

        btn_voldown = ui.Button(label="Vol -10%", style=discord.ButtonStyle.secondary)
        btn_volup = ui.Button(label="Vol +10%", style=discord.ButtonStyle.secondary)
        btn_loop = ui.Button(label="Loop Mode", style=discord.ButtonStyle.secondary)
        btn_autoplay = ui.Button(label="Autoplay", style=discord.ButtonStyle.secondary)

        btn_voldown.callback = self.on_voldown
        btn_volup.callback = self.on_volup
        btn_loop.callback = self.on_loop
        btn_autoplay.callback = self.on_autoplay

        row = ui.ActionRow(btn_voldown, btn_volup, btn_loop, btn_autoplay)
        container.add_item(row)
        self.add_item(container)

    async def on_voldown(self, interaction: discord.Interaction):
        self.player.set_volume(max(0.0, self.player.volume - 0.10))
        self.rebuild()
        await interaction.response.edit_message(view=self)

    async def on_volup(self, interaction: discord.Interaction):
        self.player.set_volume(min(1.0, self.player.volume + 0.10))
        self.rebuild()
        await interaction.response.edit_message(view=self)

    async def on_loop(self, interaction: discord.Interaction):
        self.player.cycle_loop()
        self.rebuild()
        await interaction.response.edit_message(view=self)

    async def on_autoplay(self, interaction: discord.Interaction):
        self.player.autoplay = not self.player.autoplay
        self.rebuild()
        await interaction.response.edit_message(view=self)


class HelpSupportLayoutView(ui.LayoutView):
    """
    Help and support layout using Discord Components V2.
    """
    def __init__(self, timeout: Optional[float] = None):
        super().__init__(timeout=timeout)
        container = ui.Container()
        container.add_item(ui.TextDisplay("### :scroll: Bellion Music - Command Guide"))
        
        content = (
            "> **🎵 Music Commands:**\n"
            "> `/play <query>` • `/search <query>` • `/pause` • `/resume` • `/skip` • `/stop`\n\n"
            "> **📑 Queue & Playback:**\n"
            "> `/nowplaying` • `/queue` • `/shuffle` • `/volume` • `/loop` • `/clear`\n\n"
            "> **⚙️ Utility & Settings:**\n"
            "> `/settings` • `/help` • `/ping`"
        )
        container.add_item(ui.TextDisplay(content))
        container.add_item(ui.TextDisplay(POWERED_BY_TEXT))

        btn_support = ui.Button(label="Support Server", url=SUPPORT_SERVER_URL, style=discord.ButtonStyle.link)
        row = ui.ActionRow(btn_support)
        container.add_item(row)
        self.add_item(container)


# Backward-compatibility aliases
SettingsView = SettingsLayoutView
HelpSupportView = HelpSupportLayoutView
NowPlayingView = NowPlayingLayoutView
QueueView = QueueLayoutView
SearchView = SearchLayoutView
