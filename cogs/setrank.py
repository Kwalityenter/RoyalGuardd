"""
cogs/setrank.py
----------------
Manually sets a member's Roblox group rank (writes back to Roblox via the
service account cookie configured in ROBLOX_SECURITY_COOKIE), then syncs
their Discord roles/nickname to match, and posts a promotion log matching
the "Archive Promotion Logs" style.
"""

import discord
from discord import app_commands
from discord.ext import commands

from database.mongodb import db
from utils import embeds, roblox
from utils.permissions import require_level
from cogs.update import sync_member_roles


class SetRank(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="setrank", description="Set a user's Roblox group rank.")
    @app_commands.describe(
        user="Discord user to rank",
        group_id="Roblox group ID",
        rank_id="The rank number to set them to",
    )
    @require_level(30)
    async def setrank(self, interaction: discord.Interaction, user: discord.Member, group_id: int, rank_id: int):
        await interaction.response.defer()

        verification = await db.get_verification(user.id)
        if not verification:
            return await interaction.followup.send(
                embed=embeds.error_embed("Not Verified", f"{user.mention} has not verified their Roblox account.")
            )

        roblox_id = int(verification["roblox_id"])
        group_info = await roblox.get_group_info(group_id)
        group_name = group_info.get("name", "Unknown Group") if group_info else "Unknown Group"

        roles = await roblox.get_group_roles(group_id)
        rank_name = next((r["name"] for r in roles if r["rank"] == rank_id), f"Rank {rank_id}")
        rank_role_data = next((r for r in roles if r["rank"] == rank_id), None)

        success = False
        if rank_role_data:
            try:
                success = await roblox.set_group_rank(group_id, roblox_id, rank_role_data["id"])
            except RuntimeError:
                success = False

        if not success:
            return await interaction.followup.send(
                embed=embeds.error_embed(
                    "Rank Change Failed",
                    "Could not update the rank in Roblox. Make sure ROBLOX_SECURITY_COOKIE is configured and the service account outranks the target rank."
                )
            )

        await sync_member_roles(interaction.guild, user, roblox_id)

        embed = embeds.success_embed(
            "Rank Updated",
            f"Successfully set the rank of **{verification['roblox_username']}** to **{rank_name}** in **{group_name}**."
        )
        embed.set_footer(text=f"Set by {interaction.user}")
        await interaction.followup.send(embed=embed)

        log_embed = embeds.info_embed(
            "Archive Promotion Logs",
            f"**{interaction.user}** successfully set the rank of **{verification['roblox_username']}** "
            f"to **{rank_name}** in **{group_name}**."
        )
        channel_id = await db.get_log_channel(interaction.guild.id, "rank")
        if channel_id:
            channel = interaction.guild.get_channel(int(channel_id))
            if channel:
                await channel.send(embed=log_embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(SetRank(bot))