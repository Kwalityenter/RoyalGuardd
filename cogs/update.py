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
    """Compares the member's current roles against every rankbind, adds/removes
    roles as needed, applies the highest-priority nickname prefix, and logs
    the result. Returns (added, removed, nickname_changed).
    """
    groupbinds = await db.list_groupbinds(guild.id)
    added, removed = [], []
    best_prefix = None
    best_rank_id = -1

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

            if should_have and rb.get("nickname_prefix") and int(rb["rank_id"]) > best_rank_id:
                best_rank_id = int(rb["rank_id"])
                best_prefix = rb["nickname_prefix"]

    nickname_changed = False
    if best_prefix and guild.me.guild_permissions.manage_nicknames and member.id != guild.owner_id:
        base_name = member.name
        new_nick = f"{best_prefix} {base_name}"
        if member.nick != new_nick:
            try:
                await member.edit(nick=new_nick[:32], reason="Royal Guard rank sync")
                nickname_changed = True
            except discord.Forbidden:
                pass

    if added or removed or nickname_changed:
        log_embed = embeds.info_embed("Roles Update", "Succesfully updated user roles")
        log_embed.add_field(name="Nickname", value=member.nick or member.name, inline=False)
        log_embed.add_field(name="Roles Added", value=", ".join(added) if added else "None", inline=False)
        log_embed.add_field(name="Roles Removed", value=", ".join(removed) if removed else "None", inline=False)

        channel_id = await db.get_log_channel(guild.id, "update")
        if channel_id:
            channel = guild.get_channel(int(channel_id))
            if channel:
                await channel.send(embed=log_embed)

    return added, removed, nickname_changed


class Update(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="update", description="Sync your own roles with your current Roblox group ranks.")
    async def update(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        verification = await db.get_verification(interaction.user.id)
        if not verification:
            return await interaction.followup.send(
                embed=embeds.error_embed("Warning - Not Verified", "You must be verified to update your roles.")
            )

        added, removed, nickname_changed = await sync_member_roles(
            interaction.guild, interaction.user, int(verification["roblox_id"])
        )

        embed = embeds.success_embed("Roles Update", "Succesfully updated user roles")
        embed.add_field(name="Nickname", value=interaction.user.nick or interaction.user.name, inline=False)
        embed.add_field(name="Roles Added", value=", ".join(added) if added else "None", inline=False)
        embed.add_field(name="Roles Removed", value=", ".join(removed) if removed else "None", inline=False)

        await interaction.followup.send(embed=embed)

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
            await asyncio.sleep(0.5)

        await message.edit(embed=embeds.success_embed(
            "Update Complete", f"Synced **{updated}** members. Failed: **{failed}**."
        ))


async def setup(bot: commands.Bot):
    await bot.add_cog(Update(bot))