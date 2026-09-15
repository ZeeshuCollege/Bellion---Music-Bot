import discord
from discord import app_commands
from discord.ext import commands

from config import SUPPORT_SERVER_URL
from music.player import PlayerManager
from ui.image_generator import generate_ping_card
from ui.views import SettingsLayoutView, HelpDashboardLayoutView, StatusLayoutView

class UtilityCog(commands.Cog, name="Utility"):
    """Settings, Help, Invite, Support, and diagnostic utilities for Bellion using Components V2."""

    def __init__(self, bot: commands.Bot, player_manager: PlayerManager):
        self.bot = bot
        self.players = player_manager

    def _get_invite_url(self) -> str:
        bot_id = self.bot.user.id if self.bot.user else "0"
        return f"https://discord.com/oauth2/authorize?client_id={bot_id}&permissions=36700160&scope=bot%20applications.commands"

    # ================== Slash Commands ==================

    @app_commands.command(name="help", description="Opens interactive help dashboard with command modules")
    async def help_slash(self, interaction: discord.Interaction):
        view = HelpDashboardLayoutView(bot=self.bot)
        await interaction.response.send_message(view=view)

    @app_commands.command(name="ping", description="Check Gateway latency in dynamic image format")
    async def ping_slash(self, interaction: discord.Interaction):
        latency_ms = round(self.bot.latency * 1000)
        buf = generate_ping_card(latency_ms, len(self.bot.guilds))
        file = discord.File(fp=buf, filename="ping.png")
        await interaction.response.send_message(file=file)

    @app_commands.command(name="invite", description="DM you the bot invite link")
    async def invite_slash(self, interaction: discord.Interaction):
        invite_url = self._get_invite_url()
        try:
            await interaction.user.send(f"📬 **Here is the invite link for Bellion:**\n{invite_url}")
            await interaction.response.send_message("✅ I have sent the invite link to your DMs!", ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message(
                f"❌ Could not DM you. Please enable DMs from server members!\n**Invite Link:** {invite_url}",
                ephemeral=True
            )

    @app_commands.command(name="support", description="DM you the official support server invite")
    async def support_slash(self, interaction: discord.Interaction):
        try:
            await interaction.user.send(f"🛡️ **Join the official Bellion Support Server:**\n{SUPPORT_SERVER_URL}")
            await interaction.response.send_message("✅ I have sent the support server link to your DMs!", ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message(
                f"❌ Could not DM you. Please enable DMs from server members!\n**Support Server:** {SUPPORT_SERVER_URL}",
                ephemeral=True
            )

    @app_commands.command(name="settings", description="Configure playback volume, loop mode, and autoplay")
    async def settings_slash(self, interaction: discord.Interaction):
        player = self.players.get_player(interaction.guild)
        view = SettingsLayoutView(player)
        await interaction.response.send_message(view=view)

    # ================== Prefix Commands (,) ==================

    @commands.command(name="help", aliases=["h"])
    async def help_prefix(self, ctx: commands.Context):
        """Opens help dashboard with bot information and modules for every command"""
        view = HelpDashboardLayoutView(bot=self.bot)
        await ctx.send(view=view)

    @commands.command(name="ping")
    async def ping_prefix(self, ctx: commands.Context):
        """Shows the bot latency in image format"""
        latency_ms = round(self.bot.latency * 1000)
        buf = generate_ping_card(latency_ms, len(self.bot.guilds))
        file = discord.File(fp=buf, filename="ping.png")
        await ctx.send(file=file)

    @commands.command(name="invite")
    async def invite_prefix(self, ctx: commands.Context):
        """DM the command executer the invite link of the bot"""
        invite_url = self._get_invite_url()
        try:
            await ctx.author.send(f"📬 **Here is the invite link for Bellion:**\n{invite_url}")
            await ctx.send(f"✅ I have sent the invite link to your DMs, {ctx.author.mention}!")
        except discord.Forbidden:
            await ctx.send(f"❌ Could not DM you, {ctx.author.mention}. Please enable DMs from server members!\n{invite_url}")

    @commands.command(name="support")
    async def support_prefix(self, ctx: commands.Context):
        """DM the command user the link of the support server"""
        try:
            await ctx.author.send(f"🛡️ **Join the official Bellion Support Server:**\n{SUPPORT_SERVER_URL}")
            await ctx.send(f"✅ I have sent the support server link to your DMs, {ctx.author.mention}!")
        except discord.Forbidden:
            await ctx.send(f"❌ Could not DM you, {ctx.author.mention}. Please enable DMs from server members!\n{SUPPORT_SERVER_URL}")

    @commands.command(name="settings")
    async def settings_prefix(self, ctx: commands.Context):
        """Configure playback volume, loop mode, and autoplay"""
        player = self.players.get_player(ctx.guild)
        view = SettingsLayoutView(player)
        await ctx.send(view=view)


async def setup(bot: commands.Bot):
    if not hasattr(bot, "player_manager"):
        bot.player_manager = PlayerManager(bot)
    await bot.add_cog(UtilityCog(bot, bot.player_manager))

