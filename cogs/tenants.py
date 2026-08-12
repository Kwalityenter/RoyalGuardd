"""cogs/tenants.py — Owner-only tenant management."""
import asyncio

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

        chunks = []
        current, current_len = [], 0
        for line in lines:
            if current_len + len(line) + 1 > 3900:
                chunks.append(current)
                current, current_len = [], 0
            current.append(line)
            current_len += len(line) + 1
        if current:
            chunks.append(current)

        for i, chunk in enumerate(chunks, start=1):
            title = "Registered Tenants" if len(chunks) == 1 else f"Registered Tenants ({i}/{len(chunks)})"
            try:
                await interaction.followup.send(embed=embeds.info_embed(title, "\n".join(chunk)), ephemeral=True)
            except discord.HTTPException as e:
                await interaction.followup.send(embed=embeds.error_embed("Error", f"Failed to send page {i}/{len(chunks)}: {e}"), ephemeral=True)
                break
            if i < len(chunks):
                await asyncio.sleep(0.5)

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


    @group.command(name="pending", description="List bots awaiting approval.")
    @is_owner()
    async def tenant_pending(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        pending = await db.list_pending_tenants()

        if not pending:
            return await interaction.followup.send(embed=embeds.info_embed("Pending Tenants", "No submissions awaiting review."))

        lines = []
        for p in pending:
            name = p.get("bot_name") or "(unnamed)"
            lines.append(f"`{p['_id']}` — {name} — submitted by `{p['owner_discord_id']}`")

        await interaction.followup.send(embed=embeds.info_embed("Pending Tenants", "\n".join(lines)))

    @group.command(name="approve", description="Approve a pending submission and activate it.")
    @is_owner()
    @app_commands.describe(pending_id="The pending submission ID (from /tenant pending)")
    async def tenant_approve(self, interaction: discord.Interaction, pending_id: str):
        await interaction.response.defer(ephemeral=True)

        pending = await db.get_pending_tenant(pending_id)
        if not pending:
            return await interaction.followup.send(embed=embeds.error_embed("Not Found", f"No pending submission with ID `{pending_id}`."))

        tenant_id = await db.add_tenant(
            pending["owner_discord_id"], pending["encrypted_token"], bot_name=pending.get("bot_name", "")
        )
        await db.remove_pending_tenant(pending_id)

        await interaction.followup.send(embed=embeds.success_embed(
            "Tenant Approved",
            f"Activated as `{tenant_id}`. It will come online automatically within 30 seconds.",
        ))

        try:
            owner = self.bot.get_user(pending["owner_discord_id"]) or await self.bot.fetch_user(pending["owner_discord_id"])
            await owner.send(embed=embeds.success_embed("Your Bot Has Been Approved", "Your bot will come online shortly. Check the server it's in to confirm."))
        except (discord.Forbidden, discord.NotFound):
            pass

    @group.command(name="reject", description="Reject a pending submission without activating it.")
    @is_owner()
    @app_commands.describe(pending_id="The pending submission ID (from /tenant pending)")
    async def tenant_reject(self, interaction: discord.Interaction, pending_id: str):
        await interaction.response.defer(ephemeral=True)

        pending = await db.get_pending_tenant(pending_id)
        if not pending:
            return await interaction.followup.send(embed=embeds.error_embed("Not Found", f"No pending submission with ID `{pending_id}`."))

        await db.remove_pending_tenant(pending_id)
        await interaction.followup.send(embed=embeds.success_embed("Rejected", f"`{pending_id}` deleted."))

        try:
            owner = self.bot.get_user(pending["owner_discord_id"]) or await self.bot.fetch_user(pending["owner_discord_id"])
            await owner.send(embed=embeds.error_embed("Submission Rejected", "Your bot submission was not approved. Contact the server owner for details."))
        except (discord.Forbidden, discord.NotFound):
            pass

async def setup(bot: commands.Bot):
    await bot.add_cog(Tenants(bot))
