import discord
from discord import app_commands
from discord.ext import commands

from music.player import PlayerManager
from ui.views import SettingsLayoutView, HelpSupportLayoutView, StatusLayoutView

class UtilityCog(commands.Cog, name="Utility"):
    """Settings, Help, and diagnostic utilities for Bellion using Components V2."""

    def __init__(self, bot: commands.Bot, player_manager: PlayerManager):
        self.bot = bot
        self.players = player_manager

    # ------------------ /settings ------------------
    @app_commands.command(name="settings", description="Configure playback volume, loop mode, and autoplay")
    async def settings_slash(self, interaction: discord.Interaction):
        player = self.players.get_player(interaction.guild)
        view = SettingsLayoutView(player)
        await interaction.response.send_message(view=view)

    # ------------------ /help ------------------
    @app_commands.command(name="help", description="View commands list and support information")
    async def help_slash(self, interaction: discord.Interaction):
        view = HelpSupportLayoutView()
        await interaction.response.send_message(view=view)

    # ------------------ /ping ------------------
    @app_commands.command(name="ping", description="Check Discord API latency")
    async def ping_slash(self, interaction: discord.Interaction):
        latency_ms = round(self.bot.latency * 1000)
        view = StatusLayoutView(
            title="### 📶 Pong!",
            description=f"> Gateway Latency: `{latency_ms} ms`"
        )
        await interaction.response.send_message(view=view, ephemeral=True)


async def setup(bot: commands.Bot):
    if not hasattr(bot, "player_manager"):
        bot.player_manager = PlayerManager(bot)
    await bot.add_cog(UtilityCog(bot, bot.player_manager))
