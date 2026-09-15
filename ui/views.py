from typing import List, Optional
import discord
from discord.ui import View, Button, Select, button, select
from config import SUPPORT_SERVER_URL

class NowPlayingView(View):
    """
    Persistent interactive controller for the Now Playing card.
    Contains: Prev, Play/Pause, Stop, Next, Loop, Shuffle, Volume-, Volume+
    """
    def __init__(self, player, timeout: Optional[float] = None):
        super().__init__(timeout=timeout)
        self.player = player
        self._update_play_pause_button()

    def _update_play_pause_button(self):
        # Update emoji/label based on paused state
        for item in self.children:
            if isinstance(item, Button) and item.custom_id == "np_play_pause":
                item.emoji = "▶️" if self.player.is_paused else "⏸️"
                item.style = discord.ButtonStyle.success if self.player.is_paused else discord.ButtonStyle.primary
            elif isinstance(item, Button) and item.custom_id == "np_loop":
                if self.player.loop_mode == "track":
                    item.label = "Loop: 1"
                    item.style = discord.ButtonStyle.primary
                elif self.player.loop_mode == "queue":
                    item.label = "Loop: All"
                    item.style = discord.ButtonStyle.primary
                else:
                    item.label = "Loop: Off"
                    item.style = discord.ButtonStyle.secondary

    @button(emoji="⏮️", style=discord.ButtonStyle.secondary, row=0, custom_id="np_prev")
    async def prev_button(self, interaction: discord.Interaction, btn: Button):
        if not self._check_voice(interaction):
            return await interaction.response.send_message("❌ You must be in the same voice channel!", ephemeral=True)
        
        success = await self.player.previous()
        if success:
            await interaction.response.send_message("⏮️ Replaying previous track.", ephemeral=True)
        else:
            await interaction.response.send_message("❌ No previous track in history.", ephemeral=True)

    @button(emoji="⏸️", style=discord.ButtonStyle.primary, row=0, custom_id="np_play_pause")
    async def play_pause_button(self, interaction: discord.Interaction, btn: Button):
        if not self._check_voice(interaction):
            return await interaction.response.send_message("❌ You must be in the same voice channel!", ephemeral=True)

        if self.player.is_paused:
            await self.player.resume()
        else:
            await self.player.pause()
            
        self._update_play_pause_button()
        if self.player.current:
            from ui.embeds import create_now_playing_embed
            bot_avatar = interaction.client.user.display_avatar.url if interaction.client.user else None
            embed = create_now_playing_embed(self.player.current, elapsed=self.player.get_elapsed(), bot_avatar_url=bot_avatar)
            await interaction.response.edit_message(embed=embed, view=self)
        else:
            await interaction.response.defer()

    @button(emoji="⏹️", style=discord.ButtonStyle.danger, row=0, custom_id="np_stop")
    async def stop_button(self, interaction: discord.Interaction, btn: Button):
        if not self._check_voice(interaction):
            return await interaction.response.send_message("❌ You must be in the same voice channel!", ephemeral=True)

        await self.player.stop()
        from ui.embeds import create_nothing_playing_embed
        await interaction.response.edit_message(embed=create_nothing_playing_embed(), view=None)

    @button(emoji="⏭️", style=discord.ButtonStyle.secondary, row=0, custom_id="np_skip")
    async def skip_button(self, interaction: discord.Interaction, btn: Button):
        if not self._check_voice(interaction):
            return await interaction.response.send_message("❌ You must be in the same voice channel!", ephemeral=True)

        skipped = await self.player.skip()
        if skipped:
            await interaction.response.send_message(f"⏭️ Skipped **{skipped.title}**", ephemeral=True)
        else:
            await interaction.response.send_message("❌ Nothing is playing.", ephemeral=True)

    @button(label="Loop: Off", emoji="🔁", style=discord.ButtonStyle.secondary, row=0, custom_id="np_loop")
    async def loop_button(self, interaction: discord.Interaction, btn: Button):
        if not self._check_voice(interaction):
            return await interaction.response.send_message("❌ You must be in the same voice channel!", ephemeral=True)

        self.player.cycle_loop()
        self._update_play_pause_button()
        if self.player.current:
            from ui.embeds import create_now_playing_embed
            bot_avatar = interaction.client.user.display_avatar.url if interaction.client.user else None
            embed = create_now_playing_embed(self.player.current, elapsed=self.player.get_elapsed(), bot_avatar_url=bot_avatar)
            await interaction.response.edit_message(embed=embed, view=self)
        else:
            await interaction.response.defer()

    @button(emoji="🔀", label="Shuffle", style=discord.ButtonStyle.secondary, row=1, custom_id="np_shuffle")
    async def shuffle_button(self, interaction: discord.Interaction, btn: Button):
        if not self._check_voice(interaction):
            return await interaction.response.send_message("❌ You must be in the same voice channel!", ephemeral=True)

        self.player.shuffle_queue()
        await interaction.response.send_message("🔀 Queue has been shuffled!", ephemeral=True)

    @button(emoji="🔉", label="-10%", style=discord.ButtonStyle.secondary, row=1, custom_id="np_voldown")
    async def voldown_button(self, interaction: discord.Interaction, btn: Button):
        if not self._check_voice(interaction):
            return await interaction.response.send_message("❌ You must be in the same voice channel!", ephemeral=True)

        new_vol = max(0.0, self.player.volume - 0.10)
        self.player.set_volume(new_vol)
        await interaction.response.send_message(f"🔉 Volume set to **{int(new_vol * 100)}%**", ephemeral=True)

    @button(emoji="🔊", label="+10%", style=discord.ButtonStyle.secondary, row=1, custom_id="np_volup")
    async def volup_button(self, interaction: discord.Interaction, btn: Button):
        if not self._check_voice(interaction):
            return await interaction.response.send_message("❌ You must be in the same voice channel!", ephemeral=True)

        new_vol = min(1.0, self.player.volume + 0.10)
        self.player.set_volume(new_vol)
        await interaction.response.send_message(f"🔊 Volume set to **{int(new_vol * 100)}%**", ephemeral=True)

    @button(emoji="📑", label="Queue", style=discord.ButtonStyle.secondary, row=1, custom_id="np_queue")
    async def queue_button(self, interaction: discord.Interaction, btn: Button):
        from ui.embeds import create_queue_embed
        embed = create_queue_embed(self.player.queue, self.player.current, page=1)
        view = QueueView(self.player, current_page=1)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    def _check_voice(self, interaction: discord.Interaction) -> bool:
        if not interaction.user or not isinstance(interaction.user, discord.Member):
            return False
        if not interaction.user.voice or not interaction.user.voice.channel:
            return False
        vc = self.player.guild.voice_client
        if vc and interaction.user.voice.channel != vc.channel:
            return False
        return True


class QueueView(View):
    """
    Paginated interactive view for inspecting and navigating the queue.
    """
    def __init__(self, player, current_page: int = 1, timeout: float = 120.0):
        super().__init__(timeout=timeout)
        self.player = player
        self.current_page = current_page
        self._update_buttons()

    def _update_buttons(self):
        total_pages = max(1, (len(self.player.queue) + 4) // 5)
        for item in self.children:
            if isinstance(item, Button):
                if item.custom_id == "q_prev":
                    item.disabled = (self.current_page <= 1)
                elif item.custom_id == "q_next":
                    item.disabled = (self.current_page >= total_pages)
                elif item.custom_id == "q_page":
                    item.label = f"Page {self.current_page}/{total_pages}"

    @button(label="◀ Previous", style=discord.ButtonStyle.secondary, custom_id="q_prev")
    async def prev_page(self, interaction: discord.Interaction, btn: Button):
        from ui.embeds import create_queue_embed
        self.current_page = max(1, self.current_page - 1)
        self._update_buttons()
        embed = create_queue_embed(self.player.queue, self.player.current, page=self.current_page)
        await interaction.response.edit_message(embed=embed, view=self)

    @button(label="Page 1/1", style=discord.ButtonStyle.secondary, disabled=True, custom_id="q_page")
    async def page_indicator(self, interaction: discord.Interaction, btn: Button):
        pass

    @button(label="Next ▶", style=discord.ButtonStyle.secondary, custom_id="q_next")
    async def next_page(self, interaction: discord.Interaction, btn: Button):
        from ui.embeds import create_queue_embed
        total_pages = max(1, (len(self.player.queue) + 4) // 5)
        self.current_page = min(total_pages, self.current_page + 1)
        self._update_buttons()
        embed = create_queue_embed(self.player.queue, self.player.current, page=self.current_page)
        await interaction.response.edit_message(embed=embed, view=self)

    @button(label="Clear Queue", emoji="🗑️", style=discord.ButtonStyle.danger, custom_id="q_clear")
    async def clear_queue(self, interaction: discord.Interaction, btn: Button):
        self.player.queue.clear()
        from ui.embeds import create_queue_embed
        self.current_page = 1
        self._update_buttons()
        embed = create_queue_embed(self.player.queue, self.player.current, page=1)
        await interaction.response.edit_message(embed=embed, view=self)


class SearchView(View):
    """
    Interactive view for /search results offering numbered 1-5 buttons and a select menu.
    """
    def __init__(self, player, tracks: List[dict], user: discord.Member, timeout: float = 60.0):
        super().__init__(timeout=timeout)
        self.player = player
        self.tracks = tracks
        self.user = user

        # Add select dropdown for direct selection
        options = []
        for idx, t in enumerate(tracks[:5], start=1):
            options.append(
                discord.SelectOption(
                    label=f"{idx}. {t['title'][:95]}",
                    description=f"{t['artist']} ({int(t.get('duration', 0))}s)",
                    value=str(idx - 1)
                )
            )

        if options:
            select_menu = Select(
                placeholder="Choose a track to play...",
                options=options,
                custom_id="search_select",
                row=0
            )
            select_menu.callback = self.select_callback
            self.add_item(select_menu)

        # Add quick-access 1..N buttons
        for idx in range(min(5, len(tracks))):
            btn = Button(
                label=str(idx + 1),
                style=discord.ButtonStyle.primary,
                custom_id=f"search_btn_{idx}",
                row=1
            )
            btn.callback = self.make_button_callback(idx)
            self.add_item(btn)

    async def _queue_chosen_track(self, index: int, interaction: discord.Interaction):
        from music.track import Track
        from ui.embeds import create_track_queued_embed

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

        embed = create_track_queued_embed(track, position=position)
        # Disable all view elements after selection
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(embed=embed, view=self)

    def make_button_callback(self, index: int):
        async def callback(interaction: discord.Interaction):
            if interaction.user.id != self.user.id:
                return await interaction.response.send_message("❌ This search is for someone else!", ephemeral=True)
            if not getattr(interaction.user, "voice", None) or not interaction.user.voice.channel:
                return await interaction.response.send_message("❌ You must be in a voice channel to pick a track!", ephemeral=True)
            await self._queue_chosen_track(index, interaction)
        return callback

    async def select_callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user.id:
            return await interaction.response.send_message("❌ This search is for someone else!", ephemeral=True)
        if not getattr(interaction.user, "voice", None) or not interaction.user.voice.channel:
            return await interaction.response.send_message("❌ You must be in a voice channel to pick a track!", ephemeral=True)
        chosen_idx = int(interaction.data["values"][0])
        await self._queue_chosen_track(chosen_idx, interaction)


class SettingsView(View):
    """
    Interactive View for adjusting Volume, Loop Mode, and Autoplay directly.
    """
    def __init__(self, player, timeout: float = 120.0):
        super().__init__(timeout=timeout)
        self.player = player

    @button(label="Vol -10%", emoji="🔉", style=discord.ButtonStyle.secondary, row=0)
    async def vol_down(self, interaction: discord.Interaction, btn: Button):
        self.player.set_volume(max(0.0, self.player.volume - 0.10))
        from ui.embeds import create_settings_embed
        embed = create_settings_embed(self.player.volume, self.player.loop_mode, self.player.autoplay)
        await interaction.response.edit_message(embed=embed, view=self)

    @button(label="Vol +10%", emoji="🔊", style=discord.ButtonStyle.secondary, row=0)
    async def vol_up(self, interaction: discord.Interaction, btn: Button):
        self.player.set_volume(min(1.0, self.player.volume + 0.10))
        from ui.embeds import create_settings_embed
        embed = create_settings_embed(self.player.volume, self.player.loop_mode, self.player.autoplay)
        await interaction.response.edit_message(embed=embed, view=self)

    @button(label="Loop Mode", emoji="🔁", style=discord.ButtonStyle.primary, row=1)
    async def loop_toggle(self, interaction: discord.Interaction, btn: Button):
        self.player.cycle_loop()
        from ui.embeds import create_settings_embed
        embed = create_settings_embed(self.player.volume, self.player.loop_mode, self.player.autoplay)
        await interaction.response.edit_message(embed=embed, view=self)

    @button(label="Toggle Autoplay", emoji="✨", style=discord.ButtonStyle.primary, row=1)
    async def autoplay_toggle(self, interaction: discord.Interaction, btn: Button):
        self.player.autoplay = not self.player.autoplay
        from ui.embeds import create_settings_embed
        embed = create_settings_embed(self.player.volume, self.player.loop_mode, self.player.autoplay)
        await interaction.response.edit_message(embed=embed, view=self)


class HelpSupportView(View):
    """
    Interactive Help & Support View featuring direct Discord Invite Button.
    """
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(
            Button(
                label="Join Support Server",
                url=SUPPORT_SERVER_URL,
                style=discord.ButtonStyle.link,
                emoji="🌐"
            )
        )

    @button(label="Command List", emoji="📜", style=discord.ButtonStyle.primary)
    async def show_commands(self, interaction: discord.Interaction, btn: Button):
        from ui.embeds import create_help_embed
        await interaction.response.edit_message(embed=create_help_embed(), view=self)

    @button(label="Support Info", emoji="❓", style=discord.ButtonStyle.secondary)
    async def show_support(self, interaction: discord.Interaction, btn: Button):
        from ui.embeds import create_support_embed
        await interaction.response.edit_message(embed=create_support_embed(), view=self)
