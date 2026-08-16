"""cogs/bmt.py — Basic Military Training bulk-graduation system.
/bmt walks an instructor through submitting before/after training images and
a list of trainee usernames via three chained modals, validates each name
against the configured main Roblox group and current rank, then bulk-promotes
everyone valid to the configured BMT graduate rank after explicit confirmation.
Results are logged to the configured BMT logs channel, including both images.
"""

import asyncio
import discord
from discord import app_commands
from discord.ext import commands

from database.mongodb import db
from utils import embeds, roblox
from utils.permissions import require_level


class StartImageModal(discord.ui.Modal, title="BMT System"):
    starting_image = discord.ui.TextInput(
        label="Link to your starting image",
        style=discord.TextStyle.short,
        placeholder="https://gyazo.com/...",
        required=True,
        max_length=300,
    )

    def __init__(self, cog: "BMT"):
        super().__init__()
        self.cog = cog

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.send_modal(EndImageModal(self.cog, str(self.starting_image.value).strip()))


class EndImageModal(discord.ui.Modal, title="BMT System"):
    ending_image = discord.ui.TextInput(
        label="Link to your ending image",
        style=discord.TextStyle.short,
        placeholder="https://gyazo.com/...",
        required=True,
        max_length=300,
    )

    def __init__(self, cog: "BMT", starting_image: str):
        super().__init__()
        self.cog = cog
        self.starting_image = starting_image

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.send_modal(UsernamesModal(self.cog, self.starting_image, str(self.ending_image.value).strip()))


class UsernamesModal(discord.ui.Modal, title="BMT System"):
    usernames = discord.ui.TextInput(
        label="Name the users in your BMT",
        style=discord.TextStyle.paragraph,
        placeholder="Username1, Username2, Username3",
        required=True,
        max_length=1900,
    )

    def __init__(self, cog: "BMT", starting_image: str, ending_image: str):
        super().__init__()
        self.cog = cog
        self.starting_image = starting_image
        self.ending_image = ending_image

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        raw_names = [n.strip() for n in str(self.usernames.value).split(",") if n.strip()]
        await self.cog.process_bmt_submission(interaction, self.starting_image, self.ending_image, raw_names)


class ConfirmBMTView(discord.ui.View):
    def __init__(self, cog: "BMT", starting_image: str, ending_image: str, valid_users: list, invoker_id: int):
        super().__init__(timeout=120)
        self.cog = cog
        self.starting_image = starting_image
        self.ending_image = ending_image
        self.valid_users = valid_users  # list of (username, roblox_id)
        self.invoker_id = invoker_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.invoker_id

    @discord.ui.button(label="Submit", style=discord.ButtonStyle.success)
    async def submit(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        await self.cog.finalize_bmt(interaction, self.starting_image, self.ending_image, self.valid_users)
        self.stop()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(embed=embeds.info_embed("Cancelled", "No ranks were changed."), view=None)
        self.stop()


class BMT(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="bmt", description="Submit a Basic Military Training graduation request.")
    @require_level(10)
    async def bmt(self, interaction: discord.Interaction):
        await interaction.response.send_modal(StartImageModal(self))

    async def process_bmt_submission(self, interaction: discord.Interaction, starting_image: str, ending_image: str, raw_names: list):
        guild_config = await db.get_guild_config(interaction.guild.id)
        main_group_id = guild_config.get("main_group_id")
        graduate_rank_id = guild_config.get("bmt_graduate_rank_id")

        if not main_group_id or not graduate_rank_id:
            return await interaction.followup.send(
                embed=embeds.error_embed(
                    "Not Configured",
                    "An admin must set **Main Group ID** (Verification) and **BMT Graduate Rank** (Ranking) in `/setup` before this can be used.",
                ),
                ephemeral=True,
            )

        main_group_id = int(main_group_id)
        graduate_rank_id = int(graduate_rank_id)

        valid_users = []
        invalid_entries = []

        for name in raw_names:
            roblox_user = await roblox.get_user_by_username(name)
            if not roblox_user:
                invalid_entries.append((name, "Invalid ROBLOX username"))
                continue

            roblox_id = roblox_user["id"]
            rank_id, _ = await roblox.get_user_rank_in_group(roblox_id, main_group_id)

            if not rank_id:
                invalid_entries.append((name, "Wasn't inside of group"))
                continue

            if rank_id >= graduate_rank_id:
                invalid_entries.append((name, "Rank too high to be ranked"))
                continue

            valid_users.append((name, roblox_id))

        summary_lines = [f"Usernames ({len(valid_users)})"]
        if invalid_entries:
            summary_lines.append(f"Invalid Usernames ({len(invalid_entries)})")
            for name, reason in invalid_entries:
                summary_lines.append(f"• {name}; ({reason})")

        description = "Are you sure you wish to submit the BMT request.\n\n" + "\n".join(summary_lines)

        if not valid_users:
            embed = embeds.error_embed("BMT System", description + "\n\nNo valid users to promote.")
            return await interaction.followup.send(embed=embed, ephemeral=True)

        embed = embeds.warning_embed("BMT System", description)
        view = ConfirmBMTView(self, starting_image, ending_image, valid_users, interaction.user.id)
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)

    async def finalize_bmt(self, interaction: discord.Interaction, starting_image: str, ending_image: str, valid_users: list):
        guild_config = await db.get_guild_config(interaction.guild.id)
        main_group_id = int(guild_config["main_group_id"])
        graduate_rank_id = int(guild_config["bmt_graduate_rank_id"])

        promoted, failed = [], []
        for name, roblox_id in valid_users:
            success = await roblox.set_group_rank(main_group_id, roblox_id, graduate_rank_id)
            if success:
                promoted.append(name)
            else:
                failed.append(name)
            await asyncio.sleep(1)  # avoid hammering Roblox's ranking endpoint

        result_embed = embeds.success_embed(
            "BMT Complete",
            f"**Promoted ({len(promoted)}):** {', '.join(promoted) if promoted else 'None'}\n"
            f"**Failed ({len(failed)}):** {', '.join(failed) if failed else 'None'}",
        )
        await interaction.edit_original_response(embed=result_embed, view=None)

        log_channel_id = guild_config.get("bmt_logs_channel_id")
        if log_channel_id:
            channel = interaction.guild.get_channel(int(log_channel_id))
            if channel:
                log_embed = embeds.base_embed()
                log_embed.title = "BMT Graduation Logged"
                log_embed.description = (
                    f"**Instructor:** {interaction.user.mention}\n"
                    f"**Promoted ({len(promoted)}):** {', '.join(promoted) if promoted else 'None'}\n"
                    f"**Failed ({len(failed)}):** {', '.join(failed) if failed else 'None'}"
                )
                log_embed.set_image(url=ending_image)
                log_embed.set_thumbnail(url=starting_image)
                try:
                    await channel.send(embed=log_embed)
                except discord.Forbidden:
                    pass


async def setup(bot: commands.Bot):
    await bot.add_cog(BMT(bot))
