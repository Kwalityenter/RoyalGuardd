"""
cogs/panels.py
---------------
/panel verification  - posts the persistent verification panel (matches
                        the British Army Verification System V5 image)
/panel tickets        - posts the two ticket panels (Report / Other)
"""

import discord
from discord import app_commands
from discord.ext import commands

from utils import embeds
from utils.permissions import require_level
from cogs.verification import VerificationView
from cogs.tickets import ReportTicketView, OtherTicketView


class PanelGroup(app_commands.Group):
    def __init__(self):
        super().__init__(name="panel", description="Post Royal Guard panels.")


class Panels(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.group = PanelGroup()

        self.group.add_command(
            app_commands.Command(name="verification", description="Post the Roblox verification panel.",
                                  callback=self.panel_verification)
        )
        self.group.add_command(
            app_commands.Command(name="tickets", description="Post the ticket support panels.",
                                  callback=self.panel_tickets)
        )
        bot.tree.add_command(self.group)

    @require_level(10)
    async def panel_verification(self, interaction: discord.Interaction):
        embed = embeds.verification_panel_embed()
        await interaction.channel.send(embed=embed, view=VerificationView())
        await interaction.response.send_message(
            embed=embeds.success_embed("Panel Posted", "Verification panel has been posted."), ephemeral=True
        )

    @require_level(10)
    async def panel_tickets(self, interaction: discord.Interaction):
        main_embed = embeds.ticket_panel_embed()
        await interaction.channel.send(embed=main_embed)

        report_embed = embeds.info_embed("📋 Report Tickets", "Select a report type below to open a report ticket.")
        await interaction.channel.send(embed=report_embed, view=ReportTicketView())

        other_embed = embeds.info_embed("🎫 Other Tickets", "Select a category below for bugs, exploits, or applications.")
        await interaction.channel.send(embed=other_embed, view=OtherTicketView())

        await interaction.response.send_message(
            embed=embeds.success_embed("Panels Posted", "Ticket panels have been posted."), ephemeral=True
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(Panels(bot))