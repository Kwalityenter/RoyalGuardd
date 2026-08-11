"""cogs/antiraid.py — detects mass-join raids (many new members joining in a
short window) and auto-kicks accounts newer than a configured minimum age while
raid mode is active. Also supports a manual lockdown/unlock toggle.
Config is stored in guild_config under antiraid_* keys."""

import discord
from discord import app_commands
from discord.ext import commands

from database.mongodb import db
from utils import embeds
from utils.permissions import require_owner

DEFAULT_JOIN_THRESHOLD = 10
DEFAULT_WINDOW_SECONDS = 30
DEFAULT_MIN_ACCOUNT_AGE_DAYS = 3


class AntiRaidGroup(app_commands.Group):
    def __init__(self):
        super().__init__(name="antiraid", description="Configure anti-raid protection.")


class AntiRaid(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.group = AntiRaidGroup()
        self.group.add_command(app_commands.Command(name="config", description="Configure anti-raid thresholds.", callback=self.antiraid_config))
        self.group.add_command(app_commands.Command(name="enable", description="Enable anti-raid protection.", callback=self.antiraid_enable))
        self.group.add_command(app_commands.Command(name="disable", description="Disable anti-raid protection.", callback=self.antiraid_disable))
        self.group.add_command(app_commands.Command(name="lockdown", description="Manually trigger raid lockdown.", callback=self.antiraid_lockdown))
        self.group.add_command(app_commands.Command(name="unlock", description="Lift a manual or auto-triggered lockdown.", callback=self.antiraid_unlock))
        bot.tree.add_command(self.group)

    async def _get_config(self, guild_id: int) -> dict:
        config = await db.get_guild_config(guild_id)
        return {
            "enabled": config.get("antiraid_enabled", False),
            "join_threshold": config.get("antiraid_join_threshold", DEFAULT_JOIN_THRESHOLD),
            "window_seconds": config.get("antiraid_window_seconds", DEFAULT_WINDOW_SECONDS),
            "min_account_age_days": config.get("antiraid_min_account_age_days", DEFAULT_MIN_ACCOUNT_AGE_DAYS),
            "log_channel_id": config.get("antiraid_log_channel_id"),
            "raid_mode": config.get("antiraid_raid_mode", False),
        }

    async def _log(self, guild: discord.Guild, log_channel_id, title: str, description: str):
        if not log_channel_id:
            return
        channel = guild.get_channel(int(log_channel_id))
        if channel:
            await channel.send(embed=embeds.error_embed(title, description))

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        if member.bot:
            return

        guild = member.guild
        config = await self._get_config(guild.id)
        if not config["enabled"]:
            return

        await db.record_join_event(guild.id)
        recent_joins = await db.count_recent_joins(guild.id, config["window_seconds"])

        account_age_days = (discord.utils.utcnow() - member.created_at).days

        if config["raid_mode"] and account_age_days < config["min_account_age_days"]:
            try:
                await member.kick(reason=f"Anti-raid: account age {account_age_days}d < minimum {config['min_account_age_days']}d during active raid lockdown")
                await self._log(
                    guild, config["log_channel_id"], "Anti-Raid: Member Kicked",
                    f"{member.mention} (`{member.id}`) kicked — account age {account_age_days} days, "
                    f"below the {config['min_account_age_days']}-day minimum during active raid lockdown.",
                )
            except discord.Forbidden:
                pass
            return

        if not config["raid_mode"] and recent_joins >= config["join_threshold"]:
            await db.set_guild_config(guild.id, antiraid_raid_mode=True)
            await self._log(
                guild, config["log_channel_id"], "🚨 Anti-Raid Triggered",
                f"**{recent_joins}** members joined within **{config['window_seconds']}s** — raid mode is now **active**.\n"
                f"New accounts younger than **{config['min_account_age_days']} days** will be auto-kicked until `/antiraid unlock` is run.",
            )

    @require_owner()
    @app_commands.describe(
        log_channel="Channel to post anti-raid alerts to",
        join_threshold="Joins within the window to trigger raid mode (default 10)",
        window_seconds="Rolling time window in seconds (default 30)",
        min_account_age_days="Minimum Discord account age in days required during active raid mode (default 3)",
    )
    async def antiraid_config(self, interaction: discord.Interaction, log_channel: discord.TextChannel = None,
                               join_threshold: int = None, window_seconds: int = None, min_account_age_days: int = None):
        update = {}
        if log_channel:
            update["antiraid_log_channel_id"] = str(log_channel.id)
        if join_threshold:
            update["antiraid_join_threshold"] = join_threshold
        if window_seconds:
            update["antiraid_window_seconds"] = window_seconds
        if min_account_age_days is not None:
            update["antiraid_min_account_age_days"] = min_account_age_days
        if update:
            await db.set_guild_config(interaction.guild.id, **update)
        await interaction.response.send_message(embed=embeds.success_embed("Anti-Raid Configured", "Settings updated."), ephemeral=True)

    @require_owner()
    async def antiraid_enable(self, interaction: discord.Interaction):
        await db.set_guild_config(interaction.guild.id, antiraid_enabled=True)
        await interaction.response.send_message(embed=embeds.success_embed("Anti-Raid Enabled", "Protection is now active."), ephemeral=True)

    @require_owner()
    async def antiraid_disable(self, interaction: discord.Interaction):
        await db.set_guild_config(interaction.guild.id, antiraid_enabled=False, antiraid_raid_mode=False)
        await interaction.response.send_message(embed=embeds.warning_embed("Anti-Raid Disabled", "Protection is now off."), ephemeral=True)

    @require_owner()
    async def antiraid_lockdown(self, interaction: discord.Interaction):
        await db.set_guild_config(interaction.guild.id, antiraid_raid_mode=True)
        await interaction.response.send_message(embed=embeds.warning_embed("Lockdown Active", "Raid mode manually enabled. New accounts below the minimum age will be auto-kicked."), ephemeral=True)

    @require_owner()
    async def antiraid_unlock(self, interaction: discord.Interaction):
        await db.set_guild_config(interaction.guild.id, antiraid_raid_mode=False)
        await interaction.response.send_message(embed=embeds.success_embed("Lockdown Lifted", "Raid mode disabled."), ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(AntiRaid(bot))
