import asyncio
import io
import logging
import sys

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
import discord
from discord.ext import commands

from config import DISCORD_TOKEN, MASTER_ID, BOT_NAME
from music.player import PlayerManager
from music.library import library

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("BellionBot")

class BellionBot(commands.Bot):
    def __init__(self, message_content: bool = True):
        intents = discord.Intents.default()
        intents.guilds = True
        intents.voice_states = True
        intents.message_content = message_content

        super().__init__(
            command_prefix="!",
            intents=intents,
            help_command=None
        )
        self.player_manager = PlayerManager(self)

    async def setup_hook(self):
        # Load Cogs
        await self.load_extension("cogs.music")
        await self.load_extension("cogs.utility")
        logger.info("Loaded cogs: cogs.music, cogs.utility")

        # Scan local music library on startup
        library.reload()
        tracks = library.get_all()
        logger.info(f"Loaded {len(tracks)} local test tracks into library:")
        for t in tracks:
            logger.info(f"  • {t['title']} ({int(t['duration'])}s) - {t['filepath']}")

        # Synchronize slash commands globally
        try:
            synced = await self.tree.sync()
            logger.info(f"Synced {len(synced)} slash commands globally.")
        except Exception as e:
            logger.error(f"Failed to sync slash commands: {e}")

    async def on_ready(self):
        activity = discord.Activity(
            type=discord.ActivityType.listening,
            name="🎶 /play | Bellion Music"
        )
        await self.change_presence(status=discord.Status.online, activity=activity)

        logger.info("=" * 50)
        logger.info(f"🎵 {BOT_NAME.upper()} MUSIC BOT IS ONLINE 🎵")
        logger.info(f"Logged in as: {self.user} (ID: {self.user.id})")
        logger.info(f"Master ID:    {MASTER_ID}")
        logger.info(f"Connected to {len(self.guilds)} server(s)")
        logger.info("=" * 50)

    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        """Handle auto-pause or auto-disconnect if bot is left alone in voice channel."""
        if not self.user:
            return

        # If bot itself is disconnected by a moderator
        if member.id == self.user.id and after.channel is None and before.channel:
            player = self.player_manager.get_player(before.channel.guild)
            if player:
                await player.stop()
                player.voice_client = None
            return

        # Check if the bot was in the channel the member left
        if before.channel and self.user in before.channel.members:
            non_bots = [m for m in before.channel.members if not m.bot]
            if len(non_bots) == 0:
                player = self.player_manager.get_player(before.channel.guild)
                if player and player.is_playing:
                    logger.info(f"All users left voice channel {before.channel.name}. Pausing playback.")
                    await player.pause()


async def start_bot(message_content: bool):
    bot = BellionBot(message_content=message_content)

    # Sync command for bot master/admin
    @bot.command(name="sync")
    async def sync_cmd(ctx: commands.Context):
        if ctx.author.id == MASTER_ID or (ctx.guild and ctx.author.guild_permissions.administrator):
            msg = await ctx.send("🔄 Syncing slash commands globally...")
            synced = await bot.tree.sync()
            await msg.edit(content=f"✅ Successfully synced {len(synced)} slash commands!")
        else:
            await ctx.send("❌ Only the Bot Master or an Administrator can use `!sync`.")

    # Global tree error handler
    @bot.tree.error
    async def on_app_command_error(interaction: discord.Interaction, error: discord.app_commands.AppCommandError):
        logger.error(f"Slash command error: {error}")
        msg = "❌ An unexpected error occurred while processing this command."
        if isinstance(error, discord.app_commands.CommandOnCooldown):
            msg = f"⏳ Command is on cooldown. Try again in {error.retry_after:.1f}s."
        elif isinstance(error, discord.app_commands.MissingPermissions):
            msg = "❌ You lack the necessary permissions to use this command."
        
        try:
            if interaction.response.is_done():
                await interaction.followup.send(msg, ephemeral=True)
            else:
                await interaction.response.send_message(msg, ephemeral=True)
        except Exception:
            pass

    async with bot:
        await bot.start(DISCORD_TOKEN)


async def main():
    if not DISCORD_TOKEN:
        logger.error("No DISCORD_TOKEN found in .env! Please set DISCORD_TOKEN.")
        sys.exit(1)

    try:
        await start_bot(message_content=True)
    except discord.errors.PrivilegedIntentsRequired:
        logger.warning("Message Content Intent not enabled in Discord Developer Portal.")
        logger.warning("Falling back to Slash-Commands only mode (standard intents).")
        await start_bot(message_content=False)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot shutting down gracefully.")
