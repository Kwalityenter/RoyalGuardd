import discord


class TicketDropdown(discord.ui.Select):
    def __init__(self):

        options = [
            discord.SelectOption(
                label="Report High Rank"
            ),
            discord.SelectOption(
                label="Report Exploiter"
            ),
            discord.SelectOption(
                label="Report Corruption"
            ),
            discord.SelectOption(
                label="Report Abuser"
            ),
            discord.SelectOption(
                label="Report Rule Breaker"
            )
        ]

        super().__init__(
            placeholder="Select Ticket Type",
            options=options
        )

    async def callback(
        self,
        interaction: discord.Interaction
    ):

        guild = interaction.guild

        category = discord.utils.get(
            guild.categories,
            name="Tickets"
        )

        if not category:
            category = await guild.create_category(
                "Tickets"
            )

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(
                view_channel=False
            ),
            interaction.user: discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True
            )
        }

        channel = await guild.create_text_channel(
            name=f"ticket-{interaction.user.name}",
            category=category,
            overwrites=overwrites
        )

        embed = discord.Embed(
            title=self.values[0],
            description="Support will assist you shortly.",
            color=0x3498db
        )

        await channel.send(
            interaction.user.mention,
            embed=embed,
            view=CloseTicketView()
        )

        await interaction.response.send_message(
            f"Created {channel.mention}",
            ephemeral=True
        )


class TicketDropdownView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(TicketDropdown())


class CloseTicketView(discord.ui.View):

    @discord.ui.button(
        label="Close Ticket",
        style=discord.ButtonStyle.danger
    )
    async def close(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        await interaction.response.send_message(
            "Closing ticket..."
        )

        await interaction.channel.delete()


class TicketPanelView(discord.ui.View):

    @discord.ui.button(
        label="Create Ticket",
        style=discord.ButtonStyle.primary
    )
    async def create_ticket(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        await interaction.response.send_message(
            "Choose a ticket type.",
            view=TicketDropdownView(),
            ephemeral=True
        )