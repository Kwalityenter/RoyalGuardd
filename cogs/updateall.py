@app_commands.command(name="updateall")
async def updateall(
    self,
    interaction: discord.Interaction
):
    level = await get_admin_level(
        interaction.user.id
    )

    if level < 10:
        return await interaction.response.send_message(
            "Admin Level 10 required.",
            ephemeral=True
        )

    for member in interaction.guild.members:
        await update_member(
            interaction.guild,
            member
        )

    await interaction.response.send_message(
        "Server updated."
    )