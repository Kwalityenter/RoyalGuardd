"""
cogs/groupbinds.py
-------------------
Manage which Roblox groups are bound to this Discord server.
Multiple groups may be bound at once.
"""

import discord
from discord import app_commands
from discord.ext import commands

from database.mongodb import db
from utils import embeds, roblox
from utils.permissions import require_level


class GroupBindGroup(app_commands.Group):
    def __init__(self):
        super().__init__(name="groupbind", description="Manage Roblox group bindings for this server.")


class GroupBinds(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.group = GroupBindGroup()

        self.group.add_command(
            app_commands.Command(name="add", description="Bind a Roblox group to this server.",
                                  callback=self.groupbind_add)
        )
        self.group.add_command(
            app_commands.Command(name="remove", description="Unbind a Roblox group from this server.",
                                  callback=self.groupbind_remove)
        )
        self.group.add_command(
            app_commands.Command(name="list", description="List all Roblox groups bound to this server.",
                                  callback=self.groupbind_list)
        )
        bot.tree.add_command(self.group)

    @require_level(10)
    @app_commands.describe(group_id="The Roblox group ID to bind")
    async def groupbind_add(self, interaction: discord.Interaction, group_id: int):
        await interaction.response.defer(ephemeral=True)
        info = await roblox.get_group_info(group_id)
        if not info:
            return await interaction.followup.send(
                embed=embeds.error_embed("Group Not Found", f"Could not find a Roblox group with ID `{group_id}`.")
            )

        await db.add_groupbind(interaction.guild.id, group_id, info.get("name", "Unknown"))
        await interaction.followup.send(
            embed=embeds.success_embed("Group Bound", f"**{info.get('name')}** (`{group_id}`) is now bound to this server.")
        )

    @require_level(10)
    @app_commands.describe(group_id="The Roblox group ID to unbind")
    async def groupbind_remove(self, interaction: discord.Interaction, group_id: int):
        await db.remove_groupbind(interaction.guild.id, group_id)
        await interaction.response.send_message(
            embed=embeds.success_embed("Group Unbound", f"Group `{group_id}` and its rankbinds have been removed.")
        )

    async def groupbind_list(self, interaction: discord.Interaction):
        binds = await db.list_groupbinds(interaction.guild.id)
        if not binds:
            return await interaction.response.send_message(
                embed=embeds.info_embed("No Groupbinds", "This server has no Roblox groups bound yet.")
            )

        description = "\n".join(f"• **{b['group_name']}** — `{b['group_id']}`" for b in binds)
        await interaction.response.send_message(embed=embeds.info_embed("Bound Groups", description))


async def setup(bot: commands.Bot):
    await bot.add_cog(GroupBinds(bot))