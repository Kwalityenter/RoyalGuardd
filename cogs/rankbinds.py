"""
cogs/rankbinds.py
------------------
Manage rank -> Discord role bindings per Roblox group, plus an optional
nickname prefix (e.g. "[OF-8]") applied automatically during role sync.

/rankbind add accepts up to 5 roles in a single call, so binding multiple
Discord roles to the same Roblox rank doesn't require running the command
repeatedly. Any additional roles beyond 5 can still be added with a
follow-up /rankbind add call - they simply add to what's already bound.
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
            app_commands.Command(name="add", description="Bind a Roblox rank to one or more Discord roles.",
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
        role2="Optional: a second role to bind to the same rank",
        role3="Optional: a third role to bind to the same rank",
        role4="Optional: a fourth role to bind to the same rank",
        role5="Optional: a fifth role to bind to the same rank",
        nickname_prefix="Optional nickname prefix, e.g. '[OF-8]' (leave blank for none)",
    )
    async def rankbind_add(
        self,
        interaction: discord.Interaction,
        group_id: int,
        rank_id: int,
        role: discord.Role,
        role2: discord.Role = None,
        role3: discord.Role = None,
        role4: discord.Role = None,
        role5: discord.Role = None,
        nickname_prefix: str = "",
    ):
        await interaction.response.defer(ephemeral=True)

        roles_to_bind = [r for r in [role, role2, role3, role4, role5] if r is not None]

        role_info = await roblox.get_group_roles(group_id)
        rank_name = next((r["name"] for r in role_info if r["rank"] == rank_id), f"Rank {rank_id}")

        for r in roles_to_bind:
            await db.add_rankbind(interaction.guild.id, group_id, rank_id, r.id, rank_name, nickname_prefix)

        role_mentions = ", ".join(r.mention for r in roles_to_bind)
        extra = f" Nickname prefix: `{nickname_prefix}`." if nickname_prefix else ""
        await interaction.followup.send(
            embed=embeds.success_embed(
                "Rankbind Added",
                f"Rank **{rank_name}** (`{rank_id}`) in group `{group_id}` now maps to {role_mentions}.{extra}"
            )
        )

    @require_level(10)
    @app_commands.describe(
        group_id="The Roblox group ID",
        rank_id="The Roblox rank number to unbind",
        role="Optional: remove only this specific role from the rank (leave blank to remove all roles bound to this rank)",
    )
    async def rankbind_remove(self, interaction: discord.Interaction, group_id: int, rank_id: int, role: discord.Role = None):
        await db.remove_rankbind(interaction.guild.id, group_id, rank_id, role.id if role else None)
        if role:
            await interaction.response.send_message(
                embed=embeds.success_embed("Rankbind Removed", f"{role.mention} removed from rank `{rank_id}` in group `{group_id}`.")
            )
        else:
            await interaction.response.send_message(
                embed=embeds.success_embed("Rankbind Removed", f"All roles removed from rank `{rank_id}` in group `{group_id}`.")
            )

    @app_commands.describe(group_id="The Roblox group ID to list rankbinds for")
    async def rankbind_list(self, interaction: discord.Interaction, group_id: int):
        binds = await db.list_rankbinds(interaction.guild.id, group_id)
        if not binds:
            return await interaction.response.send_message(
                embed=embeds.info_embed("No Rankbinds", f"No rankbinds found for group `{group_id}`.")
            )

        by_rank = {}
        for b in binds:
            by_rank.setdefault(b["rank_id"], {"rank_name": b.get("rank_name", "Rank"), "roles": []})
            by_rank[b["rank_id"]]["roles"].append(b)

        lines = []
        for rank_id, data in sorted(by_rank.items()):
            role_mentions = []
            for b in data["roles"]:
                prefix = f" (`{b['nickname_prefix']}`)" if b.get("nickname_prefix") else ""
                role_mentions.append(f"<@&{b['role_id']}>{prefix}")
            lines.append(f"**{data['rank_name']}** (`{rank_id}`) → {', '.join(role_mentions)}")

        await interaction.response.send_message(embed=embeds.info_embed(f"Rankbinds for {group_id}", "\n".join(lines)))


async def setup(bot: commands.Bot):
    await bot.add_cog(RankBinds(bot))git add cogs/rankbinds.py