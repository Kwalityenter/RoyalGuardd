"""
cogs/bgcheck.py
----------------
!bgcheck @user - paginated background check embed (Discord info, Roblox
info, Group info) with a loading state and executor-only buttons.
"""

import discord
from discord.ext import commands
from datetime import datetime, timezone

from database.mongodb import db
from utils import embeds, roblox
from config import settings


class BGCheckView(discord.ui.View):
    def __init__(self, executor_id: int, pages: list[discord.Embed]):
        super().__init__(timeout=120)
        self.executor_id = executor_id
        self.pages = pages
        self.current = 0
        self._update_buttons()

    def _update_buttons(self):
        self.previous_page.disabled = self.current == 0
        self.next_page.disabled = self.current == len(self.pages) - 1

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.executor_id:
            await interaction.response.send_message(
                embed=embeds.error_embed("Not Allowed", "Only the command executor can use these buttons."),
                ephemeral=True,
            )
            return False
        return True

    @discord.ui.button(label="◀ Previous", style=discord.ButtonStyle.secondary, custom_id="bg_prev")
    async def previous_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current -= 1
        self._update_buttons()
        await interaction.response.edit_message(embed=self.pages[self.current], view=self)

    @discord.ui.button(label="Next ▶", style=discord.ButtonStyle.secondary, custom_id="bg_next")
    async def next_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current += 1
        self._update_buttons()
        await interaction.response.edit_message(embed=self.pages[self.current], view=self)

    @discord.ui.button(label="🗑️ Delete", style=discord.ButtonStyle.danger, custom_id="bg_delete")
    async def delete(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.message.delete()


class BGCheck(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name="bgcheck")
    async def bgcheck(self, ctx: commands.Context, member: discord.Member = None):
        member = member or ctx.author

        loading = embeds.info_embed("🔎 Running Background Check", f"Gathering data for {member.mention}...")
        message = await ctx.send(embed=loading)

        verification = await db.get_verification(member.id)
        admin_level = await db.get_admin_level(member.id)

        pages = []

        # ---------------- PAGE 1: Discord Info ----------------
        discord_embed = embeds.base_embed(title=f"Background Check — {member}")
        discord_embed.set_thumbnail(url=member.display_avatar.url)
        discord_embed.add_field(name="Username", value=str(member), inline=True)
        discord_embed.add_field(name="ID", value=str(member.id), inline=True)
        discord_embed.add_field(
            name="Account Created",
            value=discord.utils.format_dt(member.created_at, style="R"), inline=True
        )
        discord_embed.add_field(
            name="Joined Server",
            value=discord.utils.format_dt(member.joined_at, style="R") if member.joined_at else "Unknown",
            inline=True,
        )
        discord_embed.add_field(
            name="Verification Status",
            value="✅ Verified" if verification else "❌ Not Verified", inline=True
        )
        label = "Owner (Infinite)" if admin_level >= settings.OWNER_LEVEL else str(admin_level)
        discord_embed.add_field(name="Admin Level", value=label, inline=True)
        discord_embed.set_footer(text=f"{settings.FOOTER_TEXT} | Page 1/3", icon_url=settings.FOOTER_ICON)
        pages.append(discord_embed)

        if verification:
            roblox_id = int(verification["roblox_id"])
            roblox_user = await roblox.get_user_by_id(roblox_id)
            avatar_url = await roblox.get_avatar_headshot_url(roblox_id)
            is_premium = await roblox.get_premium_status(roblox_id)
            followers = await roblox.get_followers_count(roblox_id)
            following = await roblox.get_following_count(roblox_id)
            friends = await roblox.get_friends_count(roblox_id)
            groups = await roblox.get_user_groups(roblox_id)

            # ---------------- PAGE 2: Roblox Info ----------------
            roblox_embed = embeds.base_embed(title=f"Roblox Information — {verification['roblox_username']}")
            if avatar_url:
                roblox_embed.set_thumbnail(url=avatar_url)

            if roblox_user and roblox_user.get("created"):
                created_dt = datetime.fromisoformat(roblox_user["created"].replace("Z", "+00:00"))
                age_days = (datetime.now(timezone.utc) - created_dt).days
                roblox_embed.add_field(name="Account Age", value=f"{age_days} days", inline=True)
                roblox_embed.add_field(name="Created", value=discord.utils.format_dt(created_dt, style="D"), inline=True)

            roblox_embed.add_field(name="Roblox ID", value=str(roblox_id), inline=True)
            roblox_embed.add_field(name="Premium", value="✅ Yes" if is_premium else "❌ No", inline=True)
            roblox_embed.add_field(name="Followers", value=str(followers), inline=True)
            roblox_embed.add_field(name="Following", value=str(following), inline=True)
            roblox_embed.add_field(name="Friends", value=str(friends), inline=True)
            roblox_embed.set_footer(text=f"{settings.FOOTER_TEXT} | Page 2/3", icon_url=settings.FOOTER_ICON)
            pages.append(roblox_embed)

            # ---------------- PAGE 3: Group Info ----------------
            group_embed = embeds.base_embed(title="Group Information")
            if groups:
                lines = [
                    f"**{g['group']['name']}** — {g['role']['name']} (Rank {g['role']['rank']})"
                    for g in groups[:15]
                ]
                group_embed.description = "\n".join(lines)
                if len(groups) > 15:
                    group_embed.set_footer(text=f"{settings.FOOTER_TEXT} | Page 3/3 | +{len(groups) - 15} more groups", icon_url=settings.FOOTER_ICON)
                else:
                    group_embed.set_footer(text=f"{settings.FOOTER_TEXT} | Page 3/3", icon_url=settings.FOOTER_ICON)
            else:
                group_embed.description = "This user is not in any groups."
                group_embed.set_footer(text=f"{settings.FOOTER_TEXT} | Page 3/3", icon_url=settings.FOOTER_ICON)
            pages.append(group_embed)
        else:
            not_verified_embed = embeds.warning_embed("Roblox Information", "This user has not verified their Roblox account.")
            not_verified_embed.set_footer(text=f"{settings.FOOTER_TEXT} | Page 2/2", icon_url=settings.FOOTER_ICON)
            pages.append(not_verified_embed)

        view = BGCheckView(ctx.author.id, pages)
        await message.edit(embed=pages[0], view=view)


async def setup(bot: commands.Bot):
    await bot.add_cog(BGCheck(bot))