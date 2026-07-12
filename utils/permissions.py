"""
utils/permissions.py
---------------------
Admin level permission system.

Level 0        = regular user
Level 1-100    = staff hierarchy (higher = more powerful)
Level 999999   = Owner (infinite / bypasses everything)

Use `require_level(n)` as an app_commands.check for slash commands,
or `has_level(interaction, n)` for manual checks inside a command body.
"""

import functools
import discord
from discord import app_commands
from database.mongodb import db
from config import settings


async def has_level(user_id: int, guild: discord.Guild, required: int) -> bool:
    """Returns True if the user meets the required admin level.

    Server owner and members with Administrator permission are always
    treated as Owner level (999999) as a safety net, in addition to
    whatever is stored in MongoDB.
    """
    if guild is not None:
        member = guild.get_member(user_id)
        if member is not None:
            if member.id == guild.owner_id:
                return True
            if member.guild_permissions.administrator:
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
                    title="❌ Insufficient Permissions",
                    description=f"You need admin level **{required}+** to use this command.",
                    color=settings.ERROR_COLOR,
                ),
                ephemeral=True,
            )
        return ok

    return app_commands.check(predicate)


def require_owner():
    """Restricts a command to the Owner admin level only."""
    return require_level(settings.OWNER_LEVEL)