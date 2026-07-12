"""
cogs/verification.py
---------------------
Roblox OAuth2 verification system. The panel posted by /panel verification
uses a persistent View so buttons keep working after bot restarts.

Flow:
1. User clicks "Verify via Roblox Login"
2. Bot DMs (or ephemeral-replies) a link to the Railway-hosted OAuth site
3. Website handles the Roblox OAuth2 code exchange and calls back into
   MongoDB directly (see website/routes/oauth.py) storing the link
4. User clicks "Update Roles" (or runs /update) to sync roles immediately
"""

import os
import secrets
import discord
from discord import app_commands
from discord.ext import commands

from database.mongodb import db
from utils import embeds, roblox
from cogs.update import sync_member_roles

WEBSITE_BASE_URL = os.getenv("WEBSITE_BASE_URL", "https://your-railway-app.up.railway.app")


class VerificationView(discord.ui.View):
    """Persistent view - registered once in main.py with view=VerificationView(), timeout=None."""

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Verify via ROBLOX Login", style=discord.ButtonStyle.success,
                        custom_id="royalguard:verify_login", row=0)
    async def verify_login(self, interaction: discord.Interaction, button: discord.ui.Button):
        state = secrets.token_urlsafe(24)
        await db.create_oauth_state(state, interaction.user.id)

        oauth_url = f"{WEBSITE_BASE_URL}/authorize?state={state}"

        embed = embeds.info_embed(
            "Verify Your Roblox Account",
            f"Click the link below to securely link your Roblox account via OAuth2:\n\n[**Click here to verify**]({oauth_url})\n\n"
            "This link is unique to you and expires in 10 minutes."
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="Verify via ROBLOX Game", style=discord.ButtonStyle.success,
                        custom_id="royalguard:verify_game", row=1)
    async def verify_game(self, interaction: discord.Interaction, button: discord.ui.Button):
        # In-game verification typically works via a join-code system.
        # This generates a short code the user enters in the verification
        # game, which a game-side webhook then confirms against MongoDB.
        code = secrets.token_hex(3).upper()
        await db.create_oauth_state(f"gamecode:{code}", interaction.user.id)

        embed = embeds.info_embed(
            "Verify via ROBLOX Game",
            f"Join the verification game and enter this code when prompted:\n\n"
            f"**`{code}`**\n\nThis code expires in 10 minutes."
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="Update Roles", style=discord.ButtonStyle.success,
                        custom_id="royalguard:update_roles", row=1)
    async def update_roles(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)

        verification = await db.get_verification(interaction.user.id)
        if not verification:
            return await interaction.followup.send(
                embed=embeds.error_embed("Not Verified", "You need to verify your Roblox account first.")
            )

        added, removed = await sync_member_roles(interaction.guild, interaction.user, int(verification["roblox_id"]))

        desc = "Your roles are now up to date."
        if added:
            desc += f"\n**Added:** {', '.join(added)}"
        if removed:
            desc += f"\n**Removed:** {', '.join(removed)}"

        await interaction.followup.send(embed=embeds.success_embed("Roles Updated", desc))


class Verification(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="verify", description="Check or start your Roblox verification.")
    async def verify(self, interaction: discord.Interaction):
        verification = await db.get_verification(interaction.user.id)
        if verification:
            embed = embeds.success_embed(
                "Already Verified",
                f"Linked to **{verification['roblox_username']}** (`{verification['roblox_id']}`)."
            )
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        state = secrets.token_urlsafe(24)
        await db.create_oauth_state(state, interaction.user.id)
        oauth_url = f"{WEBSITE_BASE_URL}/authorize?state={state}"

        embed = embeds.info_embed("Verify Your Roblox Account", f"[**Click here to verify**]({oauth_url})")
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Verification(bot))