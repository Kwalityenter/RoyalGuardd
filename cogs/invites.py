"""
cogs/invites.py
----------------
Tracks which invite link each new member used, credits the inviter, and
exposes /invites (personal count) and /inviteleaderboard (top inviters).

Discord doesn't tell you directly which invite a member used - we work it
out by snapshotting every invite's use-count, then diffing against a fresh
snapshot whenever someone joins to see which code incremented.
"""

import discord
from discord import app_commands
from discord.ext import commands

from database.mongodb import db
from utils import embeds


class Invites(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        for guild in self.bot.guilds:
            await self._snapshot_guild_invites(guild)

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild):
        await self._snapshot_guild_invites(guild)

    @commands.Cog.listener()
    async def on_invite_create(self, invite: discord.Invite):
        await self._snapshot_guild_invites(invite.guild)

    @commands.Cog.listener()
    async def on_invite_delete(self, invite: discord.Invite):
        await self._snapshot_guild_invites(invite.guild)

    async def _snapshot_guild_invites(self, guild: discord.Guild):
        try:
            current_invites = await guild.invites()
        except discord.Forbidden:
            return

        invite_data = [
            {"code": inv.code, "uses": inv.uses or 0, "inviter_id": str(inv.inviter.id) if inv.inviter else "unknown"}
            for inv in current_invites
        ]
        await db.snapshot_invites(guild.id, invite_data)

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        if member.bot:
            return

        guild = member.guild
        try:
            current_invites = await guild.invites()
        except discord.Forbidden:
            return

        old_snapshots = await db.get_all_invite_snapshots(guild.id)

        used_invite = None
        for inv in current_invites:
            old = old_snapshots.get(inv.code)
            old_uses = old["uses"] if old else 0
            if (inv.uses or 0) > old_uses:
                used_invite = inv
                break

        # Refresh the snapshot regardless, so counts stay accurate going forward
        await self._snapshot_guild_invites(guild)

        if used_invite and used_invite.inviter:
            await db.add_invite_credit(guild.id, used_invite.inviter.id, 1)

    @app_commands.command(name="invites", description="Check how many members you've invited.")
    @app_commands.describe(user="The user to check (defaults to yourself)")
    async def invites_cmd(self, interaction: discord.Interaction, user: discord.Member = None):
        target = user or interaction.user
        count = await db.get_invite_credit(interaction.guild.id, target.id)
        await interaction.response.send_message(
            embed=embeds.info_embed("Invite Count", f"{target.mention} has invited **{count}** member(s).")
        )

    @app_commands.command(name="inviteleaderboard", description="Show the top inviters in this server.")
    async def inviteleaderboard(self, interaction: discord.Interaction):
        top = await db.get_invite_leaderboard(interaction.guild.id, limit=10)
        if not top:
            return await interaction.response.send_message(
                embed=embeds.info_embed("Invite Leaderboard", "No invite data recorded yet.")
            )

        lines = []
        for i, entry in enumerate(top, start=1):
            lines.append(f"**{i}.** <@{entry['inviter_id']}> - {entry['count']} invite(s)")

        await interaction.response.send_message(embed=embeds.info_embed("Invite Leaderboard", "\n".join(lines)))


async def setup(bot: commands.Bot):
    await bot.add_cog(Invites(bot))