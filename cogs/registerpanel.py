"""cogs/registerpanel.py — Public self-serve bot registration panel.

Posts a "Register Bot" button. Clicking it DMs the user step-by-step
instructions plus a "Submit Token" button that opens a Discord modal.
The token is encrypted immediately on submission and never appears in any
channel — modal input is only visible to the person submitting it.

Submissions land in the `pending_tenants` queue and do NOT go live
automatically. The bot owner reviews and activates them with
/tenant pending and /tenant approve.
"""

import discord
from discord import app_commands
from discord.ext import commands

from database.mongodb import db
from utils import embeds
from utils.token_crypto import encrypt_token
from utils.permissions import require_level
from config import settings
import os

BOT_OWNER_ID = os.getenv("BOT_OWNER_ID")


def build_instructions_embed() -> discord.Embed:
    embed = embeds.base_embed()
    embed.title = "Register Your Bot — Royal Guard Hosting"
    embed.description = (
        "Follow these steps to get your own hosted bot running with Royal Guard's features.\n\n"
        "**1.** Go to the [Discord Developer Portal](https://discord.com/developers/applications) "
        "and create a **New Application**.\n"
        "**2.** Open the **Bot** tab, click **Reset Token**, and copy the token shown.\n"
        "**3.** Under **Privileged Gateway Intents**, enable **Server Members Intent** and "
        "**Message Content Intent**.\n"
        "**4.** Press **Submit Token** below. It's encrypted immediately and is never posted "
        "in any channel — only you can see this DM.\n"
        "**5.** Your submission is reviewed before your bot goes live. You'll be notified here "
        "once it's approved.\n\n"
        "⚠️ Never share your bot token anywhere else. Only submit it through the button below."
    )
    embed.set_footer(text=settings.FOOTER_TEXT, icon_url=settings.FOOTER_ICON)
    return embed


class TokenSubmitModal(discord.ui.Modal, title="Register Your Bot"):
    token = discord.ui.TextInput(
        label="Bot Token",
        style=discord.TextStyle.short,
        placeholder="Paste your bot token here",
        required=True,
        max_length=200,
    )
    bot_name = discord.ui.TextInput(
        label="Bot Name (optional)",
        style=discord.TextStyle.short,
        placeholder="e.g. My Regiment Bot",
        required=False,
        max_length=100,
    )

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        encrypted = encrypt_token(str(self.token.value).strip())
        pending_id = await db.add_pending_tenant(
            interaction.user.id, encrypted, str(self.bot_name.value or "").strip()
        )

        await interaction.followup.send(
            embed=embeds.success_embed(
                "Submitted",
                "Your bot has been submitted for review. You'll be notified here once it's approved.",
            ),
            ephemeral=True,
        )

        if BOT_OWNER_ID:
            try:
                owner = interaction.client.get_user(int(BOT_OWNER_ID)) or await interaction.client.fetch_user(int(BOT_OWNER_ID))
                await owner.send(
                    embed=embeds.info_embed(
                        "New Tenant Submission",
                        f"`{pending_id}` submitted by {interaction.user} (`{interaction.user.id}`).\n"
                        f"Run `/tenant pending` to review it, or `/tenant approve pending_id:{pending_id}` to activate it directly.",
                    )
                )
            except (discord.Forbidden, discord.NotFound):
                pass

    async def on_error(self, interaction: discord.Interaction, error: Exception):
        if interaction.response.is_done():
            await interaction.followup.send(embed=embeds.error_embed("Submission Failed", "Something went wrong. Please try again."), ephemeral=True)
        else:
            await interaction.response.send_message(embed=embeds.error_embed("Submission Failed", "Something went wrong. Please try again."), ephemeral=True)


class DMInstructionsView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Submit Token", style=discord.ButtonStyle.success, custom_id="register_bot_submit_token", emoji="🔑")
    async def submit_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(TokenSubmitModal())


class RegisterPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Register Bot", style=discord.ButtonStyle.primary, custom_id="register_bot_panel_button", emoji="📝")
    async def register_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            await interaction.user.send(embed=build_instructions_embed(), view=DMInstructionsView())
        except discord.Forbidden:
            return await interaction.response.send_message(
                embed=embeds.error_embed("DMs Closed", "Please enable direct messages from server members and try again."),
                ephemeral=True,
            )
        await interaction.response.send_message(
            embed=embeds.success_embed("Check Your DMs", "We've sent you instructions on how to register your bot."),
            ephemeral=True,
        )


class RegisterPanel(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="postregisterpanel", description="Post the bot registration panel in this channel.")
    @require_level(10)
    async def post_register_panel(self, interaction: discord.Interaction):
        embed = embeds.base_embed()
        embed.title = "Get Your Own Hosted Bot"
        embed.description = "Press **Register Bot** below to get started. You'll receive setup instructions and a secure submission form via DM."
        embed.set_footer(text=settings.FOOTER_TEXT, icon_url=settings.FOOTER_ICON)

        await interaction.response.send_message(embed=embed, view=RegisterPanelView())


async def setup(bot: commands.Bot):
    await bot.add_cog(RegisterPanel(bot))
