"""
cogs/rankbinds.py
------------------
Manage rank -> Discord role bindings per Roblox group, plus an optional
nickname prefix (e.g. "[OF-8]") applied automatically during role sync.

/rankbind add        - bind up to 5 roles to a single rank
/rankbind autobind   - bulk-create one sticky Discord role per rank in a group
/rankbind addall     - attach one or more extra roles to every rank already
                       bound in a group (e.g. a shared "Verified Member" role)
/rankbind setprefix  - set/fix the nickname prefix on an existing rankbind
                       (useful after /rankbind autobind, which doesn't set
                       a prefix by default)
/rankbind remove     - unbind a role (or all roles) from a rank
/rankbind list        - list current bindings for a group
"""

import discord
from discord import app_commands
from discord.ext import commands
import asyncio

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
        self.group.add_command(
            app_commands.Command(name="autobind", description="Auto-create and bind a sticky Discord role for every rank in a group.",
                                  callback=self.rankbind_autobind)
        )
        self.group.add_command(
            app_commands.Command(name="addall", description="Add extra role(s) to every rank already bound in a group.",
                                  callback=self.rankbind_addall)
        )
        self.group.add_command(
            app_commands.Command(name="setprefix", description="Set or fix the nickname prefix for an existing rankbind.",
                                  callback=self.rankbind_setprefix)
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

    @require_level(30)
    @app_commands.describe(
        group_id="The Roblox group ID whose existing rankbinds should get extra role(s)",
        role="Role to add to every rank already bound in this group",
        role2="Optional: a second role to add to every rank",
        role3="Optional: a third role to add to every rank",
        role4="Optional: a fourth role to add to every rank",
        role5="Optional: a fifth role to add to every rank",
    )
    async def rankbind_addall(
        self,
        interaction: discord.Interaction,
        group_id: int,
        role: discord.Role,
        role2: discord.Role = None,
        role3: discord.Role = None,
        role4: discord.Role = None,
        role5: discord.Role = None,
    ):
        await interaction.response.defer(ephemeral=True)

        roles_to_add = [r for r in [role, role2, role3, role4, role5] if r is not None]

        existing_binds = await db.list_rankbinds(interaction.guild.id, group_id)
        if not existing_binds:
            return await interaction.followup.send(
                embed=embeds.error_embed("No Rankbinds Found", f"Group `{group_id}` has no existing rankbinds. Use `/rankbind autobind` or `/rankbind add` first.")
            )

        unique_ranks = {}
        for b in existing_binds:
            unique_ranks[b["rank_id"]] = b.get("rank_name", f"Rank {b['rank_id']}")

        added_count = 0
        for rank_id, rank_name in unique_ranks.items():
            for r in roles_to_add:
                already_bound = any(
                    b["rank_id"] == rank_id and b["role_id"] == str(r.id) for b in existing_binds
                )
                if already_bound:
                    continue
                await db.add_rankbind(interaction.guild.id, group_id, rank_id, r.id, rank_name, "")
                added_count += 1

        role_mentions = ", ".join(r.mention for r in roles_to_add)
        await interaction.followup.send(
            embed=embeds.success_embed(
                "Roles Added to All Ranks",
                f"{role_mentions} added across **{len(unique_ranks)}** rank(s) in group `{group_id}`.\n"
                f"({added_count} new binding(s) created; already-bound combinations were skipped.)"
            )
        )

    @require_level(10)
    @app_commands.describe(
        group_id="The Roblox group ID",
        rank_id="The Roblox rank number to set a prefix for",
        nickname_prefix="The nickname prefix to apply, e.g. '[OF-8]' (leave blank to clear it)",
    )
    async def rankbind_setprefix(self, interaction: discord.Interaction, group_id: int, rank_id: int, nickname_prefix: str = ""):
        modified = await db.set_rankbind_prefix(interaction.guild.id, group_id, rank_id, nickname_prefix)

        if modified == 0:
            return await interaction.response.send_message(
                embed=embeds.error_embed("No Rankbind Found", f"No existing rankbind for rank `{rank_id}` in group `{group_id}`."),
                ephemeral=True,
            )

        label = f"`{nickname_prefix}`" if nickname_prefix else "no prefix (cleared)"
        await interaction.response.send_message(
            embed=embeds.success_embed(
                "Prefix Updated",
                f"Rank `{rank_id}` in group `{group_id}` now uses {label}. Updated **{modified}** rankbind(s)."
            )
        )

    @require_level(30)
    @app_commands.describe(
        group_id="The Roblox group ID to auto-bind ranks for",
        create_missing_roles="Create a Discord role for any rank that doesn't already have a matching-named role (default: true)",
        role_color="Hex color for newly created roles, e.g. FF0000 (leave blank for Discord's default)",
    )
    async def rankbind_autobind(
        self,
        interaction: discord.Interaction,
        group_id: int,
        create_missing_roles: bool = True,
        role_color: str = None,
    ):
        await interaction.response.defer(ephemeral=True)

        group_info = await roblox.get_group_info(group_id)
        if not group_info:
            return await interaction.followup.send(
                embed=embeds.error_embed("Group Not Found", f"Could not find a Roblox group with ID `{group_id}`.")
            )
        group_name = group_info.get("name", "Unknown Group")

        roblox_roles = await roblox.get_group_roles(group_id)
        roblox_roles = [r for r in roblox_roles if r["rank"] != 0]

        if not roblox_roles:
            return await interaction.followup.send(
                embed=embeds.error_embed("No Ranks Found", "Could not find any ranks (above Guest) in that group.")
            )

        color = discord.Color.default()
        if role_color:
            try:
                color = discord.Color(int(role_color.strip("#"), 16))
            except ValueError:
                return await interaction.followup.send(
                    embed=embeds.error_embed("Invalid Color", "Provide role_color as a hex value, e.g. `FF0000`.")
                )

        await db.add_groupbind(interaction.guild.id, group_id, group_name)

        existing_role_names = {r.name.lower(): r for r in interaction.guild.roles}
        created, reused, bound, skipped = [], [], [], []

        for rb_role in roblox_roles:
            rank_id = rb_role["rank"]
            rank_name = rb_role["name"]

            existing_binds = await db.list_rankbinds(interaction.guild.id, group_id)
            already_has_bind_for_this_rank = any(b["rank_id"] == rank_id for b in existing_binds)
            if already_has_bind_for_this_rank:
                skipped.append(rank_name)
                continue

            discord_role = existing_role_names.get(rank_name.lower())

            if discord_role:
                reused.append(rank_name)
            elif create_missing_roles:
                try:
                    discord_role = await interaction.guild.create_role(
                        name=rank_name,
                        color=color,
                        reason=f"Autobind: Roblox rank {rank_id} in group {group_id}",
                    )
                    created.append(rank_name)
                    await asyncio.sleep(0.5)
                except discord.Forbidden:
                    skipped.append(f"{rank_name} (missing Manage Roles permission)")
                    continue
            else:
                skipped.append(f"{rank_name} (no matching role, creation disabled)")
                continue

            await db.add_rankbind(interaction.guild.id, group_id, rank_id, discord_role.id, rank_name, "")
            bound.append(f"{rank_name} → {discord_role.mention}")

        summary = f"**Group:** {group_name}\n\n"
        if bound:
            summary += "**Bound:**\n" + "\n".join(bound[:20])
            if len(bound) > 20:
                summary += f"\n...and {len(bound) - 20} more"
        else:
            summary += "Nothing new was bound."
        if skipped:
            summary += f"\n\n**Skipped:** {len(skipped)} rank(s) (already bound or blocked)"

        await interaction.followup.send(embed=embeds.success_embed("Autobind Complete", summary))

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
    await bot.add_cog(RankBinds(bot))