"""
utils/permissions.py
---------------------
Admin level permission system.

Level 0        = regular user
Level 1-100    = staff hierarchy (higher = more powerful)
Level 999999   = Owner (infinite / bypasses everything)

Only the Discord user ID in BOT_OWNER_ID gets automatic Owner level.
Everyone else - including members with Administrator permission or the
guild owner - is governed strictly by what's stored in MongoDB, which
defaults to 0 unless explicitly set with /setadmin.

Use `require_level(n)` as an app_commands.check for slash commands,
or `has_level(interaction, n)` for manual checks inside a command body.
"""

import os
import discord
from discord import app_commands
from database.mongodb import db
from config import settings

BOT_OWNER_ID = os.getenv("BOT_OWNER_ID")


async def has_level(user_id: int, guild: discord.Guild, required: int) -> bool:
    """Returns True if the user meets the required admin level.

    Only the hardcoded BOT_OWNER_ID automatically bypasses this check.
    Everyone else - including the guild owner and members with
    Administrator permission - is checked strictly against MongoDB.
    """
    if BOT_OWNER_ID and str(user_id) == str(BOT_OWNER_ID):
        return True

    level = await db.get_admin_level(user_id)
    return level >= required


def require_level(required: int):
    """App command check decorator - use as @require_level(10)."""

    async def predicate(interaction: discord.Interaction) -> bool:
        ok = await has_level(interaction.user.id, interaction.guild, required)
        if not ok:
            await interaction.response.send_message(
                embed=discord.Embed(
                    title="Insufficient Permissions",
                    description=f"You need admin level **{required}+** to use this command.",
                    color=settings.ERROR_COLOR,
                ),
                ephemeral=True,
            )
        return ok

    return app_commands.check(predicate)


def require_owner():
    """Restricts a command to the bot owner only."""
    return require_level(settings.OWNER_LEVEL)