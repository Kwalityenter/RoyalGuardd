"""cogs/antinuke.py — detects rapid destructive/dangerous actions and auto-bans/strips
the offending account. Covers: mass channel/role delete, mass channel/role create
(spam), mass ban/kick, webhook create/delete abuse, permission escalation (a role
gaining Administrator or other dangerous perms), and malicious bot additions.
/antinuke enable requires bot-owner level specifically (highest bar in the bot)."""

import os
import discord
from discord import app_commands
from discord.ext import commands

from database.mongodb import db
from utils import embeds
from utils.permissions import require_level, require_owner

BOT_OWNER_ID = os.getenv("BOT_OWNER_ID")

DANGEROUS_PERMISSIONS = ("administrator", "ban_members", "kick_members", "manage_guild", "manage_roles", "manage_webhooks")

DEFAULT_THRESHOLDS = {
    "channel_delete": 3, "role_delete": 3, "ban": 5, "kick": 5,
    "channel_create": 5, "role_create": 5, "webhook_create": 3,
    "window_seconds": 30,
}


class AntiNukeGroup(app_commands.Group):
    def __init__(self):
        super().__init__(name="antinuke", description="Configure anti-nuke protection.")


class AntiNuke(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.group = AntiNukeGroup()
        self.group.add_command(app_commands.Command(name="config", description="Configure anti-nuke thresholds and log channel.", callback=self.antinuke_config))
        self.group.add_command(app_commands.Command(name="whitelist", description="Exempt a user from anti-nuke checks.", callback=self.antinuke_whitelist))
        self.group.add_command(app_commands.Command(name="unwhitelist", description="Remove a user's anti-nuke exemption.", callback=self.antinuke_unwhitelist))
        self.group.add_command(app_commands.Command(name="enable", description="Enable anti-nuke protection.", callback=self.antinuke_enable))
        self.group.add_command(app_commands.Command(name="disable", description="Disable anti-nuke protection.", callback=self.antinuke_disable))
        bot.tree.add_command(self.group)

    async def _is_exempt(self, guild: discord.Guild, user_id: int) -> bool:
        if BOT_OWNER_ID and str(user_id) == str(BOT_OWNER_ID):
            return True
        if user_id == guild.owner_id:
            return True
        if user_id == self.bot.user.id:
            return True
        return await db.is_antinuke_whitelisted(guild.id, user_id)

    async def _get_threshold(self, guild_id: int, key: str) -> int:
        config = await db.get_antinuke_config(guild_id)
        return config.get(key, DEFAULT_THRESHOLDS[key])

    async def _punish(self, guild: discord.Guild, member: discord.Member, reason: str):
        try:
            await member.ban(reason=f"Anti-nuke: {reason}", delete_message_days=0)
        except discord.Forbidden:
            try:
                await member.remove_roles(*member.roles[1:], reason=f"Anti-nuke: {reason}")
            except discord.Forbidden:
                pass
        config = await db.get_antinuke_config(guild.id)
        log_channel_id = config.get("log_channel_id")
        if log_channel_id:
            channel = guild.get_channel(int(log_channel_id))
            if channel:
                embed = embeds.error_embed("Anti-Nuke Triggered", f"**User:** {member.mention} (`{member.id}`)\n**Reason:** {reason}\n**Action taken:** Banned and permissions revoked.")
                await channel.send(embed=embed)

    async def _log_alert(self, guild: discord.Guild, title: str, description: str):
        config = await db.get_antinuke_config(guild.id)
        log_channel_id = config.get("log_channel_id")
        if log_channel_id:
            channel = guild.get_channel(int(log_channel_id))
            if channel:
                await channel.send(embed=embeds.error_embed(title, description))

    async def _check_and_act(self, guild: discord.Guild, user, action_type: str, threshold_key: str):
        member = guild.get_member(user.id) if not isinstance(user, discord.Member) else user
        if member is None:
            return
        config = await db.get_antinuke_config(guild.id)
        if not config.get("enabled", False):
            return
        if await self._is_exempt(guild, member.id):
            return
        await db.record_action(guild.id, member.id, action_type)
        window = config.get("window_seconds", DEFAULT_THRESHOLDS["window_seconds"])
        threshold = await self._get_threshold(guild.id, threshold_key)
        count = await db.count_recent_actions(guild.id, member.id, action_type, window)
        if count >= threshold:
            await self._punish(guild, member, f"{count} {action_type.replace('_', ' ')}(s) within {window}s")

    # --- Destructive actions (existing) ---

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel: discord.abc.GuildChannel):
        try:
            async for entry in channel.guild.audit_logs(limit=1, action=discord.AuditLogAction.channel_delete):
                await self._check_and_act(channel.guild, entry.user, "channel_delete", "channel_delete")
                break
        except discord.Forbidden:
            pass

    @commands.Cog.listener()
    async def on_guild_role_delete(self, role: discord.Role):
        try:
            async for entry in role.guild.audit_logs(limit=1, action=discord.AuditLogAction.role_delete):
                await self._check_and_act(role.guild, entry.user, "role_delete", "role_delete")
                break
        except discord.Forbidden:
            pass

    @commands.Cog.listener()
    async def on_member_ban(self, guild: discord.Guild, user):
        try:
            async for entry in guild.audit_logs(limit=1, action=discord.AuditLogAction.ban):
                await self._check_and_act(guild, entry.user, "ban", "ban")
                break
        except discord.Forbidden:
            pass

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        try:
            async for entry in member.guild.audit_logs(limit=1, action=discord.AuditLogAction.kick):
                if entry.target.id == member.id:
                    await self._check_and_act(member.guild, entry.user, "kick", "kick")
                break
        except discord.Forbidden:
            pass

    # --- Creation spam (new) ---

    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel: discord.abc.GuildChannel):
        try:
            async for entry in channel.guild.audit_logs(limit=1, action=discord.AuditLogAction.channel_create):
                await self._check_and_act(channel.guild, entry.user, "channel_create", "channel_create")
                break
        except discord.Forbidden:
            pass

    @commands.Cog.listener()
    async def on_guild_role_create(self, role: discord.Role):
        try:
            async for entry in role.guild.audit_logs(limit=1, action=discord.AuditLogAction.role_create):
                await self._check_and_act(role.guild, entry.user, "role_create", "role_create")
                break
        except discord.Forbidden:
            pass

    # --- Webhook abuse (new) ---

    @commands.Cog.listener()
    async def on_webhooks_update(self, channel: discord.abc.GuildChannel):
        try:
            async for entry in channel.guild.audit_logs(limit=1, action=discord.AuditLogAction.webhook_create):
                await self._check_and_act(channel.guild, entry.user, "webhook_create", "webhook_create")
                break
        except discord.Forbidden:
            pass

    # --- Permission escalation (new) ---

    @commands.Cog.listener()
    async def on_guild_role_update(self, before: discord.Role, after: discord.Role):
        guild = after.guild
        config = await db.get_antinuke_config(guild.id)
        if not config.get("enabled", False):
            return

        gained_dangerous_perm = any(
            getattr(after.permissions, perm) and not getattr(before.permissions, perm)
            for perm in DANGEROUS_PERMISSIONS
        )
        if not gained_dangerous_perm:
            return

        try:
            async for entry in guild.audit_logs(limit=1, action=discord.AuditLogAction.role_update):
                actor = entry.user
                if await self._is_exempt(guild, actor.id):
                    return
                member = guild.get_member(actor.id)
                if member is None:
                    return
                await self._punish(guild, member, f"granted dangerous permissions to role '{after.name}'")
                break
        except discord.Forbidden:
            pass

    # --- Malicious bot additions (new) ---

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        if not member.bot:
            return
        guild = member.guild
        config = await db.get_antinuke_config(guild.id)
        if not config.get("enabled", False):
            return

        try:
            async for entry in guild.audit_logs(limit=1, action=discord.AuditLogAction.bot_add):
                actor = entry.user
                if await self._is_exempt(guild, actor.id):
                    return
                try:
                    await member.kick(reason="Anti-nuke: bot added by a non-exempt user")
                except discord.Forbidden:
                    pass
                await self._log_alert(
                    guild, "Anti-Nuke: Suspicious Bot Add",
                    f"**Bot:** {member.mention} (`{member.id}`)\n**Added by:** {actor.mention} (`{actor.id}`)\n**Action taken:** Bot kicked. Added by a non-exempt user isn't automatically trusted.",
                )
                actor_member = guild.get_member(actor.id)
                if actor_member:
                    await self._punish(guild, actor_member, f"added bot {member} without exemption")
                break
        except discord.Forbidden:
            pass

    @require_owner()
    @app_commands.describe(
        log_channel="Channel to post anti-nuke alerts to",
        window_seconds="Rolling time window in seconds (default 30)",
        channel_delete_threshold="Channel deletes within the window to trigger (default 3)",
        role_delete_threshold="Role deletes within the window to trigger (default 3)",
        ban_threshold="Bans within the window to trigger (default 5)",
        kick_threshold="Kicks within the window to trigger (default 5)",
        channel_create_threshold="Channel creates within the window to trigger (default 5)",
        role_create_threshold="Role creates within the window to trigger (default 5)",
        webhook_create_threshold="Webhook creates within the window to trigger (default 3)",
    )
    async def antinuke_config(self, interaction: discord.Interaction, log_channel: discord.TextChannel = None,
                               window_seconds: int = None, channel_delete_threshold: int = None,
                               role_delete_threshold: int = None, ban_threshold: int = None, kick_threshold: int = None,
                               channel_create_threshold: int = None, role_create_threshold: int = None,
                               webhook_create_threshold: int = None):
        update = {}
        if log_channel:
            update["log_channel_id"] = str(log_channel.id)
        if window_seconds:
            update["window_seconds"] = window_seconds
        if channel_delete_threshold:
            update["channel_delete"] = channel_delete_threshold
        if role_delete_threshold:
            update["role_delete"] = role_delete_threshold
        if ban_threshold:
            update["ban"] = ban_threshold
        if kick_threshold:
            update["kick"] = kick_threshold
        if channel_create_threshold:
            update["channel_create"] = channel_create_threshold
        if role_create_threshold:
            update["role_create"] = role_create_threshold
        if webhook_create_threshold:
            update["webhook_create"] = webhook_create_threshold
        if update:
            await db.set_antinuke_config(interaction.guild.id, **update)
        await interaction.response.send_message(embed=embeds.success_embed("Anti-Nuke Configured", "Settings updated."), ephemeral=True)

    @require_owner()
    async def antinuke_enable(self, interaction: discord.Interaction):
        await db.set_antinuke_config(interaction.guild.id, enabled=True)
        await interaction.response.send_message(embed=embeds.success_embed("Anti-Nuke Enabled", "Protection is now active."), ephemeral=True)

    @require_owner()
    async def antinuke_disable(self, interaction: discord.Interaction):
        await db.set_antinuke_config(interaction.guild.id, enabled=False)
        await interaction.response.send_message(embed=embeds.warning_embed("Anti-Nuke Disabled", "Protection is now off."), ephemeral=True)

    @require_owner()
    @app_commands.describe(user="The user to exempt from anti-nuke checks")
    async def antinuke_whitelist(self, interaction: discord.Interaction, user: discord.Member):
        await db.add_antinuke_whitelist(interaction.guild.id, user.id)
        await interaction.response.send_message(embed=embeds.success_embed("Whitelisted", f"{user.mention} is now exempt from anti-nuke checks."), ephemeral=True)

    @require_owner()
    @app_commands.describe(user="The user to remove from the whitelist")
    async def antinuke_unwhitelist(self, interaction: discord.Interaction, user: discord.Member):
        await db.remove_antinuke_whitelist(interaction.guild.id, user.id)
        await interaction.response.send_message(embed=embeds.success_embed("Unwhitelisted", f"{user.mention} is no longer exempt."), ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(AntiNuke(bot))
