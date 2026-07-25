"""
cogs/automod.py
-----------------
Lightweight automod: spam detection (message rate), mass mentions,
invite link filtering, and a basic bad-word filter. Configurable per
guild via /automod config. Staff (admin level 10+) are exempt.
"""

import time
import re
import discord
from discord import app_commands
from discord.ext import commands

from database.mongodb import db
from utils import embeds
from utils.permissions import require_level, has_level

INVITE_REGEX = re.compile(r"(discord\.gg|discord(?:app)?\.com/invite)/\S+", re.IGNORECASE)

# Simple in-memory spam tracker: {(guild_id, user_id): [timestamps]}
_message_windows = {}


class AutoModGroup(app_commands.Group):
    def __init__(self):
        super().__init__(name="automod", description="Configure automod.")


class AutoMod(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.group = AutoModGroup()

        self.group.add_command(
            app_commands.Command(name="config", description="Configure automod settings.",
                                  callback=self.automod_config)
        )
        self.group.add_command(
            app_commands.Command(name="enable", description="Enable automod.",
                                  callback=self.automod_enable)
        )
        self.group.add_command(
            app_commands.Command(name="disable", description="Disable automod.",
                                  callback=self.automod_disable)
        )
        self.group.add_command(
            app_commands.Command(name="addword", description="Add a word to the filtered word list.",
                                  callback=self.automod_addword)
        )
        self.group.add_command(
            app_commands.Command(name="removeword", description="Remove a word from the filtered word list.",
                                  callback=self.automod_removeword)
        )
        bot.tree.add_command(self.group)

    async def _log(self, guild: discord.Guild, embed: discord.Embed):
        config = await db.get_automod_config(guild.id)
        log_channel_id = config.get("log_channel_id")
        if log_channel_id:
            channel = guild.get_channel(int(log_channel_id))
            if channel:
                await channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return

        # Staff (level 10+) bypass automod entirely
        if await has_level(message.author.id, message.guild, 10):
            return

        config = await db.get_automod_config(message.guild.id)
        if not config.get("enabled", False):
            return

        # ---- Mass mention filter ----
        max_mentions = config.get("max_mentions", 5)
        if len(message.mentions) + len(message.role_mentions) > max_mentions:
            await self._delete_and_warn(message, "Mass mentions")
            return

        # ---- Invite link filter ----
        if config.get("block_invites", True) and INVITE_REGEX.search(message.content):
            await self._delete_and_warn(message, "Posting an invite link")
            return

        # ---- Bad word filter ----
        banned_words = config.get("banned_words", [])
        if banned_words:
            content_lower = message.content.lower()
            for word in banned_words:
                if word.lower() in content_lower:
                    await self._delete_and_warn(message, "Filtered word")
                    return

        # ---- Spam / message rate filter ----
        max_messages = config.get("spam_max_messages", 5)
        spam_window = config.get("spam_window_seconds", 5)

        key = (message.guild.id, message.author.id)
        now = time.time()
        timestamps = _message_windows.get(key, [])
        timestamps = [t for t in timestamps if now - t < spam_window]
        timestamps.append(now)
        _message_windows[key] = timestamps

        if len(timestamps) > max_messages:
            _message_windows[key] = []  # reset so we don't spam-punish repeatedly
            try:
                await message.author.timeout(discord.utils.utcnow() + __import__("datetime").timedelta(minutes=5),
                                              reason="Automod: message spam")
            except discord.Forbidden:
                pass

            embed = embeds.warning_embed(
                "Automod Action",
                f"{message.author.mention} was muted for 5 minutes for spamming."
            )
            await self._log(message.guild, embed)

    async def _delete_and_warn(self, message: discord.Message, reason: str):
        try:
            await message.delete()
        except discord.Forbidden:
            pass

        embed = embeds.warning_embed(
            "Automod Action",
            f"A message from {message.author.mention} was removed.\n**Reason:** {reason}"
        )
        await self._log(message.guild, embed)

    # ============================================================
    # COMMANDS
    # ============================================================
    @require_level(50)
    @app_commands.describe(
        log_channel="Channel to post automod actions to",
        max_mentions="Max mentions per message before deletion",
        block_invites="Whether to auto-delete Discord invite links",
        spam_max_messages="Messages allowed within the spam window",
        spam_window_seconds="Spam window length in seconds",
    )
    async def automod_config(
        self,
        interaction: discord.Interaction,
        log_channel: discord.TextChannel = None,
        max_mentions: int = None,
        block_invites: bool = None,
        spam_max_messages: int = None,
        spam_window_seconds: int = None,
    ):
        update = {}
        if log_channel:
            update["log_channel_id"] = str(log_channel.id)
        if max_mentions is not None:
            update["max_mentions"] = max_mentions
        if block_invites is not None:
            update["block_invites"] = block_invites
        if spam_max_messages is not None:
            update["spam_max_messages"] = spam_max_messages
        if spam_window_seconds is not None:
            update["spam_window_seconds"] = spam_window_seconds

        if update:
            await db.set_automod_config(interaction.guild.id, **update)

        await interaction.response.send_message(
            embed=embeds.success_embed("Automod Configured", "Settings updated."), ephemeral=True
        )

    @require_level(50)
    async def automod_enable(self, interaction: discord.Interaction):
        await db.set_automod_config(interaction.guild.id, enabled=True)
        await interaction.response.send_message(
            embed=embeds.success_embed("Automod Enabled", "Automod is now active."), ephemeral=True
        )

    @require_level(50)
    async def automod_disable(self, interaction: discord.Interaction):
        await db.set_automod_config(interaction.guild.id, enabled=False)
        await interaction.response.send_message(
            embed=embeds.warning_embed("Automod Disabled", "Automod is now off."), ephemeral=True
        )

    @require_level(50)
    @app_commands.describe(word="The word or phrase to filter")
    async def automod_addword(self, interaction: discord.Interaction, word: str):
        config = await db.get_automod_config(interaction.guild.id)
        words = config.get("banned_words", [])
        if word.lower() not in [w.lower() for w in words]:
            words.append(word)
            await db.set_automod_config(interaction.guild.id, banned_words=words)
        await interaction.response.send_message(
            embed=embeds.success_embed("Word Added", f"`{word}` added to the filter list."), ephemeral=True
        )

    @require_level(50)
    @app_commands.describe(word="The word or phrase to remove from the filter")
    async def automod_removeword(self, interaction: discord.Interaction, word: str):
        config = await db.get_automod_config(interaction.guild.id)
        words = [w for w in config.get("banned_words", []) if w.lower() != word.lower()]
        await db.set_automod_config(interaction.guild.id, banned_words=words)
        await interaction.response.send_message(
            embed=embeds.success_embed("Word Removed", f"`{word}` removed from the filter list."), ephemeral=True
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(AutoMod(bot))