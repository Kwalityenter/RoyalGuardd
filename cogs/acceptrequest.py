"""
cogs/acceptrequest.py
----------------------
/acceptrequest user:@Member  - accept level 20+ only

Shows a dropdown of every regiment group configured via /setup -> Background
Check -> Regiment Groups (guild_config["regiment_groups"], comma-separated
Roblox group IDs). Whichever regiment the admin picks, the target user is
ranked to that group's entry rank - the lowest rank above 0 (Guest), i.e.
the standard "just joined" rank - then their Discord roles are re-synced.
"""

import discord
from discord import app_commands
from discord.ext import commands

from database.mongodb import db
from utils import embeds, roblox
from utils.permissions import require_level
from cogs.update import sync_member_roles


class RegimentSelect(discord.ui.Select):
    def __init__(self, member: discord.Member, roblox_id: int, groups_info: list[dict], guild_id: int):
        self.member = member
        self.roblox_id = roblox_id
        self.guild_id = guild_id
        self.groups_info = {str(g["id"]): g for g in groups_info}

        options = [
            discord.SelectOption(label=g["name"][:100], value=str(g["id"]), description=f"Group ID: {g['id']}")
            for g in groups_info
        ][:25]  # Discord hard cap on select options

        super().__init__(placeholder="Select a regiment to accept this user into...", options=options)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        group_id = int(self.values[0])
        group_name = self.groups_info[self.values[0]]["name"]

        roles = await roblox.get_group_roles(group_id)
        entry_roles = sorted((r for r in roles if r["rank"] > 0), key=lambda r: r["rank"])
        if not entry_roles:
            return await interaction.followup.send(
                embed=embeds.error_embed("No Entry Rank Found", f"Could not find a valid entry rank in **{group_name}**."),
                ephemeral=True,
            )
        entry_role = entry_roles[0]

        try:
            success = await roblox.set_group_rank(group_id, self.roblox_id, entry_role["id"], guild_id=self.guild_id)
        except RuntimeError as e:
            return await interaction.followup.send(
                embed=embeds.error_embed("Rank Change Failed", str(e)),
                ephemeral=True,
            )

        if not success:
            return await interaction.followup.send(
                embed=embeds.error_embed("Rank Change Failed", "Could not accept the user into this regiment."),
                ephemeral=True,
            )

        await sync_member_roles(interaction.guild, self.member, self.roblox_id)

        await interaction.followup.send(
            embed=embeds.success_embed(
                "Request Accepted",
                f"{self.member.mention} has been accepted into **{group_name}** as **{entry_role['name']}**."
            ),
            ephemeral=True,
        )

        channel_id = await db.get_log_channel(interaction.guild.id, "rank")
        if channel_id:
            channel = interaction.guild.get_channel(int(channel_id))
            if channel:
                await channel.send(embed=embeds.info_embed(
                    "Regiment Acceptance",
                    f"**{interaction.user}** accepted {self.member.mention} into **{group_name}** as **{entry_role['name']}**."
                ))


class RegimentSelectView(discord.ui.View):
    def __init__(self, member: discord.Member, roblox_id: int, groups_info: list[dict], guild_id: int):
        super().__init__(timeout=120)
        self.add_item(RegimentSelect(member, roblox_id, groups_info, guild_id))


class AcceptRequest(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="acceptrequest", description="Accept a user into a regiment group.")
    @app_commands.describe(user="The Discord user to accept into a regiment")
    @require_level(20)
    async def acceptrequest(self, interaction: discord.Interaction, user: discord.Member):
        await interaction.response.defer(ephemeral=True)

        verification = await db.get_verification(user.id)
        if not verification:
            return await interaction.followup.send(
                embed=embeds.error_embed("Warning - Not Verified", f"{user.mention} has not verified their Roblox account.")
            )

        guild_config = await db.get_guild_config(interaction.guild.id)
        raw = guild_config.get("regiment_groups", "")
        regiment_ids = [v.strip() for v in raw.split(",") if v.strip()]

        if not regiment_ids:
            return await interaction.followup.send(
                embed=embeds.error_embed(
                    "No Regiments Configured",
                    "No regiment groups are set up. Configure them via /setup -> Background Check -> Regiment Groups."
                )
            )

        groups_info = []
        for gid in regiment_ids:
            info = await roblox.get_group_info(int(gid))
            if info:
                groups_info.append({"id": int(gid), "name": info.get("name", f"Group {gid}")})
            else:
                groups_info.append({"id": int(gid), "name": f"Unknown Group ({gid})"})

        embed = embeds.info_embed(
            "Accept Into Regiment",
            f"Select which regiment to accept {user.mention} into."
        )
        view = RegimentSelectView(user, int(verification["roblox_id"]), groups_info, interaction.guild.id)
        await interaction.followup.send(embed=embed, view=view)


async def setup(bot: commands.Bot):
    await bot.add_cog(AcceptRequest(bot))
