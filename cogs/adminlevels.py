"""
cogs/adminlevels.py
--------------------
Slash commands to manage the staff hierarchy admin level system.
"""

import discord
from discord import app_commands
from discord.ext import commands

from database.mongodb import db
from utils import embeds
from utils.permissions import require_level, has_level
from config import settings


class AdminLevels(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="setadmin", description="Set a user's admin level.")
    @app_commands.describe(user="The user to set", level="Admin level (0-100, or 999999 for Owner)")
    @require_level(90)
    async def setadmin(self, interaction: discord.Interaction, user: discord.Member, level: int):
        if level != settings.OWNER_LEVEL and (level < 0 or level > 100):
            return await interaction.response.send_message(
                embed=embeds.error_embed("Invalid Level", "Level must be between 0-100, or 999999 for Owner."),
                ephemeral=True,
            )

        # Prevent staff from setting a level higher than or equal to their own (except Owner)
        caller_level = await db.get_admin_level(interaction.user.id)
        if caller_level != settings.OWNER_LEVEL and level >= caller_level:
            return await interaction.response.send_message(
                embed=embeds.error_embed("Not Allowed", "You cannot assign a level equal to or higher than your own."),
                ephemeral=True,
            )

        await db.set_admin_level(user.id, level)
        await interaction.response.send_message(
            embed=embeds.success_embed("Admin Level Updated", f"{user.mention} is now admin level **{level}**.")
        )

    @app_commands.command(name="removeadmin", description="Remove a user's admin level (resets to 0).")
    @app_commands.describe(user="The user to reset")
    @require_level(90)
    async def removeadmin(self, interaction: discord.Interaction, user: discord.Member):
        await db.remove_admin_level(user.id)
        await interaction.response.send_message(
            embed=embeds.success_embed("Admin Level Removed", f"{user.mention} has been reset to level **0**.")
        )

    @app_commands.command(name="adminlevel", description="Check a user's admin level.")
    @app_commands.describe(user="The user to check (defaults to yourself)")
    async def adminlevel(self, interaction: discord.Interaction, user: discord.Member = None):
        target = user or interaction.user
        level = await db.get_admin_level(target.id)
        is_owner = target.id == interaction.guild.owner_id or target.guild_permissions.administrator

        display_level = settings.OWNER_LEVEL if (is_owner and level < settings.OWNER_LEVEL) else level
        label = "Owner (Infinite)" if display_level == settings.OWNER_LEVEL else str(display_level)

        await interaction.response.send_message(
            embed=embeds.info_embed("Admin Level", f"{target.mention}'s admin level: **{label}**")
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(AdminLevels(bot))