import discord
from discord import app_commands
from discord.ext import commands

from config.settings import FOOTER_TEXT
from utils.permissions import require_level

CHECK_EMOJI = "✅"


class ActivityCheck(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="activitycheck",
        description="Host an activity check in a channel",
    )
    @app_commands.describe(
        channel="Channel to post the activity check in (defaults to this channel)"
    )
    @require_level(20)
    async def activitycheck(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel = None,
    ):
        target = channel or interaction.channel

        embed = discord.Embed(
            title="Activity Check!",
            description=(
                "An activity check is being hosted right now. Use the "
                f"{CHECK_EMOJI} reaction below to mark your activity.\n\n"
                f"Hosted By: {interaction.user.mention}"
            ),
            color=discord.Color.blurple(),
        )
        embed.set_footer(text=FOOTER_TEXT)

        msg = await target.send(
            content="@everyone",
            embed=embed,
            allowed_mentions=discord.AllowedMentions(everyone=True),
        )
        await msg.add_reaction(CHECK_EMOJI)

        await interaction.response.send_message(
            f"Activity check posted in {target.mention}",
            ephemeral=True,
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(ActivityCheck(bot))
