"""
cogs/update.py
---------------
/update       - syncs the invoking user's roles against all bound groups/ranks
/updateall    - syncs every verified member in the server (admin level 10+)
"""

import asyncio
import discord
from discord import app_commands
from discord.ext import commands

from database.mongodb import db
from utils import embeds, roblox
from utils.permissions import require_level
from config import settings


async def sync_member_roles(guild: discord.Guild, member: discord.Member, roblox_id: int):
    """Compares the member's current roles against every rankbind and
    adds/removes roles as needed. Returns (added, removed) role name lists.
    """
    groupbinds = await db.list_groupbinds(guild.id)
    added, removed = [], []

    for gb in groupbinds:
        group_id = int(gb["group_id"])
        rank_id, _ = await roblox.get_user_rank_in_group(roblox_id, group_id)
        rankbinds = await db.list_rankbinds(guild.id, group_id)

        for rb in rankbinds:
            role = guild.get_role(int(rb["role_id"]))
            if role is None:
                continue

            should_have = int(rb["rank_id"]) == rank_id
            has_role = role in member.roles

            try:
                if should_have and not has_role:
                    await member.add_roles(role, reason="Royal Guard rank sync")
                    added.append(role.name)
                elif not should_have and has_role:
                    await member.remove_roles(role, reason="Royal Guard rank sync")
                    removed.append(role.name)
            except discord.Forbidden:
                continue

    return added, removed


class Update(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="update", description="Sync your own roles with your current Roblox group ranks.")
    async def update(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        verification = await db.get_verification(interaction.user.id)
        if not verification:
            return await interaction.followup.send(
                embed=embeds.error_embed("Not Verified", "You need to verify with `/panel verification` first.")
            )

        added, removed = await sync_member_roles(interaction.guild, interaction.user, int(verification["roblox_id"]))

        desc = "Your roles have been synced."
        if added:
            desc += f"\n**Added:** {', '.join(added)}"
        if removed:
            desc += f"\n**Removed:** {', '.join(removed)}"

        await interaction.followup.send(embed=embeds.success_embed("Roles Updated", desc))

    @app_commands.command(name="updateall", description="Sync roles for every verified member in the server.")
    @require_level(settings.UPDATEALL_MIN_LEVEL)
    async def updateall(self, interaction: discord.Interaction):
        await interaction.response.defer()

        guild = interaction.guild
        updated, failed = 0, 0

        progress_embed = embeds.info_embed("Updating All Members", "This may take a while depending on server size...")
        message = await interaction.followup.send(embed=progress_embed)

        async for member in guild.fetch_members(limit=None):
            if member.bot:
                continue
            verification = await db.get_verification(member.id)
            if not verification:
                continue
            try:
                await sync_member_roles(guild, member, int(verification["roblox_id"]))
                updated += 1
            except Exception:
                failed += 1
            await asyncio.sleep(0.5)  # Rate-limit friendly pacing

        await message.edit(embed=embeds.success_embed(
            "Update Complete", f"Synced **{updated}** members. Failed: **{failed}**."
        ))


async def setup(bot: commands.Bot):
    await bot.add_cog(Update(bot))