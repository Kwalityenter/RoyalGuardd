"""
cogs/rankrequest.py
--------------------
/rankrequestconfig    - sets which role can approve/deny, and which
                        channel requests get posted to
/rank request         - lets a verified member request a rank change;
                        posts an Approve/Deny embed to the configured
                        channel, gated to members with the approver role
"""

import discord
from discord import app_commands
from discord.ext import commands

from database.mongodb import db
from utils import embeds, roblox
from utils.permissions import require_level
from cogs.update import sync_member_roles


async def _has_approver_role(interaction: discord.Interaction) -> bool:
    config = await db.get_rank_request_config(interaction.guild.id)
    role_id = config.get("approver_role_id")
    if not role_id:
        return False
    role = interaction.guild.get_role(int(role_id))
    return role is not None and role in interaction.user.roles


class RankRequestView(discord.ui.View):
    """One instance per pending request; custom_id encodes the request id
    so these remain clickable even after a bot restart, once re-registered
    in main.py's setup_hook from the pending requests stored in Mongo."""

    def __init__(self, request_id: str):
        super().__init__(timeout=None)
        self.request_id = request_id

        approve_button = discord.ui.Button(
            label="Approve", style=discord.ButtonStyle.success,
            custom_id=f"royalguard:rankreq_approve:{request_id}"
        )
        approve_button.callback = self.approve
        self.add_item(approve_button)

        deny_button = discord.ui.Button(
            label="Deny", style=discord.ButtonStyle.danger,
            custom_id=f"royalguard:rankreq_deny:{request_id}"
        )
        deny_button.callback = self.deny