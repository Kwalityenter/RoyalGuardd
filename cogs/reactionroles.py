"""
cogs/reactionroles.py
----------------------
/reactionrole add     - attaches an emoji -> role binding to a message
/reactionrole remove  - removes a binding
/reactionrole list     - lists all bindings for a message

Listens for raw reaction add/remove events (works even on messages not
in the bot's cache) and toggles roles accordingly.
"""

import discord
from discord import app_commands
from discord.ext import commands

from database.mongodb import db
from utils import embeds
from utils.permissions import require_level


class ReactionRoleGroup(app_commands.Group):
    def __init__(self):
        super().__init__(name="reactionrole", description="Manage reaction roles.")


class ReactionRoles(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.group = ReactionRoleGroup()

        self.group.add_command(
            app_commands.Command(name="add", description="Bind an emoji reaction on a message to a role.",
                                  callback=self.rr_add)
        )
        self.group.add_command(
            app_commands.Command(name="remove", description="Remove an emoji-role binding from a message.",
                                  callback=self.rr_remove)
        )
        self.group.add_command(
            app_commands.Command(name="list", description="List reaction role bindings for a message.",
                                  callback=self.rr_list)
        )
        bot.tree.add_command(self.group)

    @require_level(10)
    @app_commands.describe(
        channel="Channel the message is in",
        message_id="The message ID to attach the reaction to",
        emoji="The emoji to react with (unicode or custom)",
        role="The role to grant/remove when reacted",
    )
    async def rr_add(self, interaction: discord.Interaction, channel: discord.TextChannel, message_id: str, emoji: str, role: discord.Role):
        await interaction.response.defer(ephemeral=True)

        try:
            message = await channel.fetch_message(int(message_id))
        except (discord.NotFound, ValueError):
            return await interaction.followup.send(
                embed=embeds.error_embed("Message Not Found", "Could not find that message in the specified channel.")
            )

        try:
            await message.add_reaction(emoji)
        except discord.HTTPException:
            return await interaction.followup.send(
                embed=embeds.error_embed("Invalid Emoji", "I couldn't react with that emoji. Make sure it's a valid unicode emoji or one from a server I'm in.")
            )

        await db.add_reaction_role(interaction.guild.id, channel.id, message.id, emoji, role.id)

        await interaction.followup.send(
            embed=embeds.success_embed("Reaction Role Added", f"Reacting with {emoji} on that message now grants {role.mention}.")
        )

    @require_level(10)
    @app_commands.describe(message_id="The message ID to remove a binding from", emoji="The emoji binding to remove")
    async def rr_remove(self, interaction: discord.Interaction, message_id: str, emoji: str):
        await db.remove_reaction_role(int(message_id), emoji)
        await interaction.response.send_message(
            embed=embeds.success_embed("Reaction Role Removed", f"Removed the {emoji} binding from that message."),
            ephemeral=True,
        )

    @app_commands.describe(message_id="The message ID to list bindings for")
    async def rr_list(self, interaction: discord.Interaction, message_id: str):
        bindings = await db.list_reaction_roles(int(message_id))
        if not bindings:
            return await interaction.response.send_message(
                embed=embeds.info_embed("No Bindings", "No reaction roles are set up on that message."), ephemeral=True
            )

        lines = [f"{b['emoji']} -> <@&{b['role_id']}>" for b in bindings]
        await interaction.response.send_message(
            embed=embeds.info_embed("Reaction Role Bindings", "\n".join(lines)), ephemeral=True
        )

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        if payload.member is None or payload.member.bot:
            return

        emoji_str = str(payload.emoji)
        binding = await db.get_reaction_role(payload.message_id, emoji_str)
        if not binding:
            return

        guild = self.bot.get_guild(payload.guild_id)
        if not guild:
            return
        role = guild.get_role(int(binding["role_id"]))
        if not role:
            return

        try:
            await payload.member.add_roles(role, reason="Reaction role")
        except discord.Forbidden:
            pass

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent):
        emoji_str = str(payload.emoji)
        binding = await db.get_reaction_role(payload.message_id, emoji_str)
        if not binding:
            return

        guild = self.bot.get_guild(payload.guild_id)
        if not guild:
            return
        member = guild.get_member(payload.user_id)
        if not member or member.bot:
            return
        role = guild.get_role(int(binding["role_id"]))
        if not role:
            return

        try:
            await member.remove_roles(role, reason="Reaction role removed")
        except discord.Forbidden:
            pass


async def setup(bot: commands.Bot):
    await bot.add_cog(ReactionRoles(bot))