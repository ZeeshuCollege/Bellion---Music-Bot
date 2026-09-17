from typing import List, Optional
import discord
from discord import ui

from config import SUPPORT_SERVER_URL, get_track_thumbnail
from music.track import Track
from ui.theme import (
    EMOJI_MUSIC_DISC, EMOJI_HEADSET, EMOJI_PAUSE, EMOJI_QUEUE, EMOJI_SETTINGS,
    EMOJI_PREVIOUS, EMOJI_STOP, EMOJI_SHUFFLE, EMOJI_LOOP, EMOJI_TRASH,
    EMOJI_VOLUME, EMOJI_MUSICNOTE, EMOJI_WARNING, EMOJI_FILTER, EMOJI_SPARKLES,
    EMOJI_SEARCH, EMOJI_CROSS, EMOJI_WHITE_ARROW, EMOJI_SKIP
)

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
        
        # 1. Header: 💽 Now Playing (or ⏸️ Paused)
        if self.player.is_paused:
            header = ui.TextDisplay(f"### {EMOJI_PAUSE} Paused")
        else:
            header = ui.TextDisplay(f"### {EMOJI_MUSIC_DISC} Now Playing")
        container.add_item(header)
        
        track = self.player.current
        if track:
            # Upper side: Media gallery image
            thumb_url = track.thumbnail_url or get_track_thumbnail(track.title, track.artist)
            if thumb_url:
                media_item = discord.MediaGalleryItem(thumb_url)
                container.add_item(ui.MediaGallery(media_item))
            
            # Down side: Track info stacked vertically (long not wide)
            requester_name = track.get_requester_display()
            content = (
                f"> **[{track.title}]({SUPPORT_SERVER_URL})**\n"
                f"> **Artist:** `{track.artist}`\n"
                f"> **Duration:** `{track.formatted_duration}`\n"
                f"> **Requested by:** {requester_name}"
            )
            container.add_item(ui.TextDisplay(content))
        else:
            container.add_item(ui.TextDisplay("> *Nothing is currently playing.*"))
            
        # 2. Action Row 1: Prev, Pause (In red color), Next, Loop, Shuffle
        btn_prev = ui.Button(label="Prev", emoji=discord.PartialEmoji.from_str(EMOJI_PREVIOUS), style=discord.ButtonStyle.secondary, custom_id="v2_prev")
        
        pause_label = "Resume" if self.player.is_paused else "Pause"
        pause_style = discord.ButtonStyle.success if self.player.is_paused else discord.ButtonStyle.danger
        btn_pause = ui.Button(label=pause_label, emoji=discord.PartialEmoji.from_str(EMOJI_PAUSE), style=pause_style, custom_id="v2_pause")
        
        btn_next = ui.Button(label="Next", emoji=discord.PartialEmoji.from_str(EMOJI_SKIP), style=discord.ButtonStyle.secondary, custom_id="v2_next")
        
        loop_labels = {
            "off": "Loop",
            "track": "Loop: 1",
            "queue": "Loop: All"
        }
        loop_label = loop_labels.get(self.player.loop_mode, "Loop")
        loop_style = discord.ButtonStyle.primary if self.player.loop_mode != "off" else discord.ButtonStyle.secondary
        btn_loop = ui.Button(label=loop_label, emoji=discord.PartialEmoji.from_str(EMOJI_LOOP), style=loop_style, custom_id="v2_loop")
        
        btn_shuffle = ui.Button(label="Shuffle", emoji=discord.PartialEmoji.from_str(EMOJI_SHUFFLE), style=discord.ButtonStyle.secondary, custom_id="v2_shuffle")
        
        btn_prev.callback = self.on_prev
        btn_pause.callback = self.on_pause
        btn_next.callback = self.on_next
        btn_loop.callback = self.on_loop
        btn_shuffle.callback = self.on_shuffle
        
        row_buttons = ui.ActionRow(btn_prev, btn_pause, btn_next, btn_loop, btn_shuffle)
        container.add_item(row_buttons)

        # 3. Action Row 2: Audio Filters Dropdown
        current_filter = getattr(self.player, "filter", None)
        filter_options = [
            discord.SelectOption(
                label="8D Audio",
                value="8d",
                description="Rotating 8D surround sound effect",
                emoji=discord.PartialEmoji.from_str(EMOJI_HEADSET),
                default=(current_filter == "8d")
            ),
            discord.SelectOption(
                label="Bass Boost",
                value="bassboost",
                description="Deep low-frequency punch & bass enhancement",
                emoji=discord.PartialEmoji.from_str(EMOJI_VOLUME),
                default=(current_filter == "bassboost")
            ),
            discord.SelectOption(
                label="Nightcore",
                value="nightcore",
                description="High pitch and 25% faster tempo",
                emoji=discord.PartialEmoji.from_str(EMOJI_SPARKLES),
                default=(current_filter == "nightcore")
            ),
            discord.SelectOption(
                label="Vaporwave",
                value="vaporwave",
                description="Slowed down with relaxing lo-fi aesthetics",
                emoji="🌴",
                default=(current_filter == "vaporwave")
            ),
            discord.SelectOption(
                label="Pop / Vocal Boost",
                value="pop",
                description="Crisp vocals and bright treble clarity",
                emoji="🎤",
                default=(current_filter == "pop")
            ),
            discord.SelectOption(
                label="Clear Filters",
                value="clear",
                description="Remove all active audio filters",
                emoji=discord.PartialEmoji.from_str(EMOJI_CROSS),
                default=False
            ),
        ]
        
        filter_display_names = {
            "8d": "8D Audio",
            "bassboost": "Bass Boost",
            "nightcore": "Nightcore",
            "vaporwave": "Vaporwave",
            "pop": "Pop / Vocal Boost",
        }
        active_display = filter_display_names.get(current_filter) if current_filter else None
        placeholder = f"Active Filter: {active_display}" if active_display else "Choose Audio Filter (Active: None)"
        select_filter = ui.Select(
            placeholder=placeholder,
            options=filter_options,
            custom_id="v2_filter"
        )
        select_filter.callback = self.on_filter_select
        row_filter = ui.ActionRow(select_filter)
        container.add_item(row_filter)
        
        self.add_item(container)

    def _check_voice(self, interaction: discord.Interaction) -> bool:
        if not interaction.user or not isinstance(interaction.user, discord.Member):
            return False
        if not interaction.user.voice or not interaction.user.voice.channel:
            return False
        vc = self.player.guild.voice_client if self.player.guild else None
        if vc and interaction.user.voice.channel != vc.channel:
            return False
        return True

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if not self._check_voice(interaction):
            await interaction.response.send_message("❌ You must be in the same voice channel!", ephemeral=True)
            return False
        # Catch any legacy button clicks for "v2_stop" and redirect to pause without deleting card
        if interaction.data and interaction.data.get("custom_id") == "v2_stop":
            await self.on_pause(interaction)
            return False
        return True

    async def on_prev(self, interaction: discord.Interaction):
        if not self._check_voice(interaction):
            return await interaction.response.send_message("❌ You must be in the same voice channel!", ephemeral=True)
        if not self.player.history:
            return await interaction.response.send_message("❌ No previous track in history.", ephemeral=True)
        await interaction.response.defer()
        await self.player.previous()

    async def on_pause(self, interaction: discord.Interaction):
        if not self._check_voice(interaction):
            return await interaction.response.send_message("❌ You must be in the same voice channel!", ephemeral=True)
        
        if not self.player.current:
            return await interaction.response.send_message("❌ Nothing is currently playing!", ephemeral=True)
            
        if self.player.is_paused:
            await self.player.resume(update_card=False)
        else:
            await self.player.pause(update_card=False)
            
        self.rebuild()
        await interaction.response.edit_message(view=self)

    async def on_next(self, interaction: discord.Interaction):
        if not self._check_voice(interaction):
            return await interaction.response.send_message("❌ You must be in the same voice channel!", ephemeral=True)
            
        await interaction.response.defer()
        await self.player.skip()

    # Alias on_skip for backward compatibility
    on_skip = on_next

    async def on_stop(self, interaction: discord.Interaction):
        """Legacy handler: if an old stop button is clicked, pause instead of destroying the player card."""
        await self.on_pause(interaction)

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
        await interaction.response.defer()

    async def on_filter_select(self, interaction: discord.Interaction):
        if not self._check_voice(interaction):
            return await interaction.response.send_message("❌ You must be in the same voice channel!", ephemeral=True)
        
        if not self.player.current:
            return await interaction.response.send_message("❌ Nothing is currently playing!", ephemeral=True)

        values = interaction.data.get("values", []) if interaction.data else []
        chosen = values[0] if values else "clear"
        
        await self.player.set_filter(chosen, update_card=False)
        
        if interaction.message:
            self.player.now_playing_message = interaction.message

        self.rebuild()
        if not interaction.response.is_done():
            await interaction.response.edit_message(view=self)
        elif self.player.now_playing_message:
            await self.player.now_playing_message.edit(view=self)


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
        container.add_item(ui.TextDisplay(f"### {EMOJI_QUEUE} Current Queue"))
        
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
                lines.append(f"> {EMOJI_WHITE_ARROW} **[{self.player.current.title}]({SUPPORT_SERVER_URL})** - `{self.player.current.artist}` (`{self.player.current.formatted_duration}`)\n")
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
        btn_prev = ui.Button(label="Previous", emoji=discord.PartialEmoji.from_str(EMOJI_PREVIOUS), style=discord.ButtonStyle.secondary, disabled=(self.current_page <= 1))
        total_pages = max(1, (len(self.player.queue) + 4) // 5) if self.player.queue else 1
        btn_next = ui.Button(label="Next", emoji=discord.PartialEmoji.from_str(EMOJI_SKIP), style=discord.ButtonStyle.secondary, disabled=(self.current_page >= total_pages))
        btn_clear = ui.Button(label="Clear Queue", emoji=discord.PartialEmoji.from_str(EMOJI_TRASH), style=discord.ButtonStyle.danger)
        
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
    def __init__(self, player, tracks: List[dict], user: Optional[discord.Member | discord.User] = None, query: str = "", timeout: float = 60.0):
        super().__init__(timeout=timeout)
        self.player = player
        self.tracks = tracks
        self.user = user
        self.query = query
        self.rebuild()

    def rebuild(self):
        self.clear_items()
        container = ui.Container()
        
        container.add_item(ui.TextDisplay(f"### {EMOJI_SEARCH} Search Results for `{self.query}`"))
        
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
            if self.user and interaction.user.id != self.user.id:
                return await interaction.response.send_message(f"{EMOJI_CROSS} This search is for someone else!", ephemeral=True)
            if not getattr(interaction.user, "voice", None) or not interaction.user.voice.channel:
                return await interaction.response.send_message(f"{EMOJI_CROSS} You must be in a voice channel!", ephemeral=True)
                
            track_data = self.tracks[index]
            track = Track(
                title=track_data["title"],
                artist=track_data["artist"],
                duration=track_data["duration"],
                filepath=track_data["filepath"],
                requester=interaction.user
            )
            
            position = len(self.player.queue) + (1 if self.player.current else 0)
            started = await self.player.add_track(track)
            
            try:
                if interaction.message:
                    await interaction.message.delete()
            except Exception:
                pass

            if not started:
                view = StatusLayoutView(
                    title=f"### {EMOJI_HEADSET} Track Queued",
                    description=(
                        f"> **[{track.title}]({SUPPORT_SERVER_URL})** - `{track.artist}`\n"
                        f"> Duration: `{track.formatted_duration}`\n"
                        f"> Position in queue: `#{position}`\n\n"
                        f"-# Added to queue successfully!"
                    ),
                    thumbnail_url=get_track_thumbnail(track.title, track.artist)
                )
                if not interaction.response.is_done():
                    await interaction.response.send_message(view=view)
                elif interaction.channel:
                    await interaction.channel.send(view=view)
            else:
                if not interaction.response.is_done():
                    await interaction.response.defer()
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
        container.add_item(ui.TextDisplay(f"### {EMOJI_SETTINGS} Audio Settings"))

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
        btn_volup = ui.Button(label="Vol +10%", emoji=discord.PartialEmoji.from_str(EMOJI_VOLUME), style=discord.ButtonStyle.secondary)
        btn_loop = ui.Button(label="Loop Mode", emoji=discord.PartialEmoji.from_str(EMOJI_LOOP), style=discord.ButtonStyle.secondary)
        btn_autoplay = ui.Button(label="Autoplay", emoji=discord.PartialEmoji.from_str(EMOJI_SPARKLES), style=discord.ButtonStyle.secondary)

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


class HelpDashboardLayoutView(ui.LayoutView):
    """
    Interactive Help Dashboard using Discord Components V2.
    Displays bot information and modular command listings with tab navigation.
    """
    def __init__(self, bot=None, current_module: str = "overview", timeout: Optional[float] = 180.0):
        super().__init__(timeout=timeout)
        self.bot = bot
        self.current_module = current_module
        self.rebuild()

    def rebuild(self):
        self.clear_items()
        container = ui.Container()

        latency_str = f"{round(self.bot.latency * 1000)} ms" if self.bot and hasattr(self.bot, "latency") else "Optimal"
        guild_count = len(self.bot.guilds) if self.bot and hasattr(self.bot, "guilds") else 1

        if self.current_module == "overview":
            container.add_item(ui.TextDisplay(f"### {EMOJI_MUSIC_DISC} Bellion Music — Help Dashboard"))
            overview_lines = [
                f"> **Bot Name:** `Bellion`\n"
                f"> **Command Prefix:** `,` (comma)\n"
                f"> **Gateway Latency:** `{latency_str}`\n"
                f"> **Active Guilds:** `{guild_count}`\n"
                f"> **Engine:** Discord Components V2 (Rich Interactive Layouts)",
                
                "**Command Modules:**\n"
                f"• {EMOJI_MUSIC_DISC} **Music Module** — Playback, pause, resume, skip, prev, stop, filter\n\n"
                f"• {EMOJI_QUEUE} **Queue Module** — Upcoming queue, clear, shuffle, loop, autoplay\n\n"
                f"• {EMOJI_SETTINGS} **Utility Module** — Join voice, latency ping, settings, invite, support",
                
                "-# *Click the navigation buttons below to view module commands.*"
            ]
            container.add_item(ui.TextDisplay("\n\n".join(overview_lines)))

        elif self.current_module == "music":
            container.add_item(ui.TextDisplay(f"### {EMOJI_MUSIC_DISC} Music Commands Module"))
            music_lines = [
                "> **`,play <song name / link>`** `(alias: ,p)`\n"
                "> Streams high quality audio from YouTube, Spotify, or local files.",
                
                "> **`,pause`**\n"
                "> Pauses the currently playing track.",
                
                "> **`,resume`**\n"
                "> Resumes playback of the paused track.",
                
                "> **`,skip [amount]`** `(alias: ,s)`\n"
                "> Skips the current track (or given number of songs).",
                
                "> **`,previous`** `(alias: ,prev)`\n"
                "> Plays the previously played track from history.",
                
                "> **`,stop`** `(aliases: ,disconnect, ,dc, ,leave)`\n"
                "> Stops playback, clears the queue, and leaves voice channel.",
                
                "> **`,nowplaying`** `(alias: ,np)`\n"
                "> Displays the active player card with buttons & filter controls.",
                
                "> **`,filter [preset]`** `(alias: ,filters)`\n"
                "> Apply audio effects: `8d`, `bassboost`, `nightcore`, `vaporwave`, `pop`, `clear`."
            ]
            container.add_item(ui.TextDisplay("\n\n".join(music_lines)))

        elif self.current_module == "queue":
            container.add_item(ui.TextDisplay(f"### {EMOJI_QUEUE} Queue & Playback Module"))
            queue_lines = [
                "> **`,queue [page]`** `(alias: ,q)`\n"
                "> Displays upcoming songs with interactive page navigation buttons.",
                
                "> **`,clear`**\n"
                "> Clears all upcoming tracks from the queue immediately.",
                
                "> **`,shuffle`**\n"
                "> Shuffles the remaining tracks in the queue into a random order.",
                
                "> **`,loop`**\n"
                "> Cycles repeat mode: `off` ➔ `track (repeat single)` ➔ `queue (repeat all)`.",
                
                "> **`,autoplay`**\n"
                "> Automatically discovers and queues similar songs when the playlist ends."
            ]
            container.add_item(ui.TextDisplay("\n\n".join(queue_lines)))

        elif self.current_module == "utility":
            container.add_item(ui.TextDisplay(f"### {EMOJI_SETTINGS} Utility & Info Module"))
            util_lines = [
                "> **`,help`** `(alias: ,h)`\n"
                "> Opens this interactive help dashboard with command modules.",
                
                "> **`,join`** `(aliases: ,connect, ,j)`\n"
                "> Connects the bot directly to your current voice channel.",
                
                "> **`,ping`**\n"
                "> Renders dynamic image card displaying Discord gateway latency.",
                
                "> **`,settings`**\n"
                "> Configure volume, repeat loop mode, and autoplay preferences.",
                
                "> **`,invite`**\n"
                "> DMs you a direct invite link to add Bellion to your server.",
                
                "> **`,support`**\n"
                "> DMs you an invite link to the official Bellion support community."
            ]
            container.add_item(ui.TextDisplay("\n\n".join(util_lines)))

        # Module navigation buttons
        btn_overview = ui.Button(
            label="Overview",
            emoji=discord.PartialEmoji.from_str(EMOJI_WHITE_ARROW),
            style=discord.ButtonStyle.primary if self.current_module == "overview" else discord.ButtonStyle.secondary
        )
        btn_music = ui.Button(
            label="Music",
            emoji=discord.PartialEmoji.from_str(EMOJI_MUSICNOTE),
            style=discord.ButtonStyle.primary if self.current_module == "music" else discord.ButtonStyle.secondary
        )
        btn_queue = ui.Button(
            label="Queue",
            emoji=discord.PartialEmoji.from_str(EMOJI_QUEUE),
            style=discord.ButtonStyle.primary if self.current_module == "queue" else discord.ButtonStyle.secondary
        )
        btn_util = ui.Button(
            label="Utility",
            emoji=discord.PartialEmoji.from_str(EMOJI_SETTINGS),
            style=discord.ButtonStyle.primary if self.current_module == "utility" else discord.ButtonStyle.secondary
        )

        btn_overview.callback = self.make_module_callback("overview")
        btn_music.callback = self.make_module_callback("music")
        btn_queue.callback = self.make_module_callback("queue")
        btn_util.callback = self.make_module_callback("utility")

        row1 = ui.ActionRow(btn_overview, btn_music, btn_queue, btn_util)
        container.add_item(row1)

        # External Link buttons
        invite_url = (
            f"https://discord.com/oauth2/authorize?client_id={self.bot.user.id}&permissions=36700160&scope=bot%20applications.commands"
            if self.bot and getattr(self.bot, "user", None)
            else "https://discord.com"
        )
        btn_invite = ui.Button(label="Invite Bot", url=invite_url, style=discord.ButtonStyle.link)
        btn_support = ui.Button(label="Support Server", url=SUPPORT_SERVER_URL, style=discord.ButtonStyle.link)
        row2 = ui.ActionRow(btn_invite, btn_support)
        container.add_item(row2)

        self.add_item(container)

    def make_module_callback(self, module_name: str):
        async def callback(interaction: discord.Interaction):
            self.current_module = module_name
            self.rebuild()
            await interaction.response.edit_message(view=self)
        return callback


# Backward-compatibility aliases
HelpSupportLayoutView = HelpDashboardLayoutView
HelpSupportView = HelpDashboardLayoutView
HelpDashboardView = HelpDashboardLayoutView
SettingsView = SettingsLayoutView
NowPlayingView = NowPlayingLayoutView
QueueView = QueueLayoutView
SearchView = SearchLayoutView

