"""
cogs/rankbinds.py
------------------
Manage rank -> Discord role bindings per Roblox group, plus an optional
nickname prefix (e.g. "[OF-8]") applied automatically during role sync.
"""

import discord
from discord import app_commands
from discord.ext import commands

from database.mongodb import db
from utils import embeds, roblox
from utils.permissions import require_level


class RankBindGroup(app_commands.Group):
    def __init__(self):
        super().__init__(name="rankbind", description="Manage rank-to-role bindings.")


class RankBinds(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.group = RankBindGroup()

        self.group.add_command(
            app_commands.Command(name="add", description="Bind a Roblox rank to a Discord role.",
                                  callback=self.rankbind_add)
        )
        self.group.add_command(
            app_commands.Command(name="remove", description="Remove a rankbind.",
                                  callback=self.rankbind_remove)
        )
        self.group.add_command(
            app_commands.Command(name="list", description="List rankbinds for a group.",
                                  callback=self.rankbind_list)
        )
        bot.tree.add_command(self.group)

    @require_level(10)
    @app_commands.describe(
        group_id="The Roblox group ID",
        rank_id="The Roblox rank number (1-255) to bind",
        role="The Discord role to assign for this rank",
        nickname_prefix="Optional nickname prefix, e.g. '[OF-8]' (leave blank for none)",
    )
    async def rankbind_add(
        self,
        interaction: discord.Interaction,
        group_id: int,
        rank_id: int,
        role: discord.Role,
        nickname_prefix: str = "",
    ):
        await interaction.response.defer(ephemeral=True)

        roles = await roblox.get_group_roles(group_id)
        rank_name = next((r["name"] for r in roles if r["rank"] == rank_id), f"Rank {rank_id}")

        await db.add_rankbind(interaction.guild.id, group_id, rank_id, role.id, rank_name, nickname_prefix)
        extra = f" Nickname prefix: `{nickname_prefix}`." if nickname_prefix else ""
        await interaction.followup.send(
            embed=embeds.success_embed(
                "Rankbind Added",
                f"Rank **{rank_name}** (`{rank_id}`) in group `{group_id}` now maps to {role.mention}.{extra}"
            )
        )

    @require_level(10)
    @app_commands.describe(group_id="The Roblox group ID", rank_id="The Roblox rank number to unbind")
    async def rankbind_remove(self, interaction: discord.Interaction, group_id: int, rank_id: int):
        await db.remove_rankbind(interaction.guild.id, group_id, rank_id)
        await interaction.response.send_message(
            embed=embeds.success_embed("Rankbind Removed", f"Rankbind for rank `{rank_id}` in group `{group_id}` removed.")
        )

    @app_commands.describe(group_id="The Roblox group ID to list rankbinds for")
    async def rankbind_list(self, interaction: discord.Interaction, group_id: int):
        binds = await db.list_rankbinds(interaction.guild.id, group_id)
        if not binds:
            return await interaction.response.send_message(
                embed=embeds.info_embed("No Rankbinds", f"No rankbinds found for group `{group_id}`.")
            )

        lines = []
        for b in binds:
            prefix = f" | Nickname: `{b['nickname_prefix']}`" if b.get("nickname_prefix") else ""
            lines.append(f"• **{b.get('rank_name', 'Rank')}** (`{b['rank_id']}`) → <@&{b['role_id']}>{prefix}")

        await interaction.response.send_message(embed=embeds.info_embed(f"Rankbinds for {group_id}", "\n".join(lines)))


async def setup(bot: commands.Bot):
    await bot.add_cog(RankBinds(bot))