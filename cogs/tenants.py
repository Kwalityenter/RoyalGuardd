"""cogs/tenants.py — Owner-only tenant management."""

import discord
from discord import app_commands
from discord.ext import commands

from database.mongodb import db
from utils import embeds
from utils.token_crypto import encrypt_token
import os
BOT_OWNER_ID = os.getenv("BOT_OWNER_ID")


def is_owner():
    async def predicate(interaction: discord.Interaction) -> bool:
        if interaction.user.id != int(BOT_OWNER_ID):
            raise app_commands.CheckFailure("Owner only.")
        return True
    return app_commands.check(predicate)


class Tenants(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    group = app_commands.Group(name="tenant", description="Manage hosted tenant bots (owner only).")

    @group.command(name="register", description="Register a new tenant bot. DM only.")
    @is_owner()
    @app_commands.describe(token="The tenant's Discord bot token", owner_id="The Discord user ID this bot belongs to", name="A label for this tenant")
    async def tenant_register(self, interaction: discord.Interaction, token: str, owner_id: str, name: str = ""):
        if interaction.guild is not None:
            return await interaction.response.send_message(
                embed=embeds.error_embed("Wrong Channel", "Run this command in a DM to the bot, never in a server channel."),
                ephemeral=True,
            )

        if not owner_id.isdigit():
            return await interaction.response.send_message(embed=embeds.error_embed("Invalid Owner ID", "owner_id must be numeric."))

        await interaction.response.defer(ephemeral=True)

        encrypted = encrypt_token(token)
        tenant_id = await db.add_tenant(int(owner_id), encrypted, bot_name=name)

        await interaction.followup.send(embed=embeds.success_embed(
            "Tenant Registered",
            f"Tenant `{tenant_id}` registered for owner `{owner_id}`.\n\nRedeploy the tenant-runner service to start it.",
        ))

    @group.command(name="list", description="List all registered tenants.")
    @is_owner()
    async def tenant_list(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        tenants = await db.list_tenants()

        if not tenants:
            return await interaction.followup.send(embed=embeds.info_embed("Tenants", "No tenants registered yet."))

        lines = []
        for t in tenants:
            status_icon = {"active": "🟢", "error": "🔴", "stopped": "⚪"}.get(t["status"], "❓")
            name = t.get("bot_name") or "(unnamed)"
            lines.append(f"{status_icon} `{t['_id']}` — {name} — owner `{t['owner_discord_id']}` — {t['status']}")
            if t.get("last_error"):
                lines.append(f"    ⤷ {t['last_error']}")

        await interaction.followup.send(embed=embeds.info_embed("Registered Tenants", "\n".join(lines)))

    @group.command(name="stop", description="Mark a tenant as stopped.")
    @is_owner()
    @app_commands.describe(tenant_id="The tenant's MongoDB ID")
    async def tenant_stop(self, interaction: discord.Interaction, tenant_id: str):
        await interaction.response.defer(ephemeral=True)
        await db.set_tenant_status(tenant_id, "stopped")
        await interaction.followup.send(embed=embeds.success_embed("Tenant Stopped", f"`{tenant_id}` marked as stopped."))

    @group.command(name="remove", description="Permanently delete a tenant's stored token and record.")
    @is_owner()
    @app_commands.describe(tenant_id="The tenant's MongoDB ID")
    async def tenant_remove(self, interaction: discord.Interaction, tenant_id: str):
        await interaction.response.defer(ephemeral=True)
        await db.remove_tenant(tenant_id)
        await interaction.followup.send(embed=embeds.success_embed("Tenant Removed", f"`{tenant_id}` deleted permanently."))


async def setup(bot: commands.Bot):
    await bot.add_cog(Tenants(bot))
