"""cogs/bgcheck.py — !bgcheck @user, paginated Discord/Roblox/Group info embed.
Pagination is done via message REACTIONS (⬅️ / ➡️ / 🗑️), not buttons.
Bot requires 'Add Reactions' and 'Manage Messages' (to remove other users' reactions) permissions.
"""

import asyncio
import discord
from discord.ext import commands
from datetime import datetime, timezone

from database.mongodb import db
from utils import embeds, roblox
from config import settings

PREV_EMOJI = "⬅️"
NEXT_EMOJI = "➡️"
DELETE_EMOJI = "🗑️"


class BGCheck(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def _build_pages(self, ctx: commands.Context, member: discord.Member):
        verification = await db.get_verification(member.id)
        admin_level = await db.get_admin_level(ctx.guild.id, member.id)

        pages = []

        discord_embed = embeds.base_embed(title=f"Background Check — {member}")
        discord_embed.set_thumbnail(url=member.display_avatar.url)
        discord_embed.add_field(name="Username", value=str(member), inline=True)
        discord_embed.add_field(name="ID", value=str(member.id), inline=True)
        discord_embed.add_field(name="Account Created", value=discord.utils.format_dt(member.created_at, style="R"), inline=True)
        discord_embed.add_field(name="Joined Server", value=discord.utils.format_dt(member.joined_at, style="R") if member.joined_at else "Unknown", inline=True)
        discord_embed.add_field(name="Verification Status", value="Verified" if verification else "Not Verified", inline=True)
        label = "Owner (Infinite)" if admin_level >= settings.OWNER_LEVEL else str(admin_level)
        discord_embed.add_field(name="Admin Level", value=label, inline=True)

        if verification:
            roblox_id = int(verification["roblox_id"])
            roblox_user = await roblox.get_user_by_id(roblox_id)
            avatar_url = await roblox.get_avatar_headshot_url(roblox_id)
            is_premium = await roblox.get_premium_status(roblox_id)
            followers = await roblox.get_followers_count(roblox_id)
            following = await roblox.get_following_count(roblox_id)
            friends = await roblox.get_friends_count(roblox_id)
            groups = await roblox.get_user_groups(roblox_id)

            roblox_embed = embeds.base_embed(title=f"Roblox Information — {verification['roblox_username']}")
            if avatar_url:
                roblox_embed.set_thumbnail(url=avatar_url)
            if roblox_user and roblox_user.get("created"):
                created_dt = datetime.fromisoformat(roblox_user["created"].replace("Z", "+00:00"))
                age_days = (datetime.now(timezone.utc) - created_dt).days
                roblox_embed.add_field(name="Account Age", value=f"{age_days} days", inline=True)
                roblox_embed.add_field(name="Created", value=discord.utils.format_dt(created_dt, style="D"), inline=True)
            roblox_embed.add_field(name="Roblox ID", value=str(roblox_id), inline=True)
            roblox_embed.add_field(name="Premium", value="Yes" if is_premium else "No", inline=True)
            roblox_embed.add_field(name="Followers", value=str(followers), inline=True)
            roblox_embed.add_field(name="Following", value=str(following), inline=True)
            roblox_embed.add_field(name="Friends", value=str(friends), inline=True)

            group_embed = embeds.base_embed(title="Group Information")
            if groups:
                lines = [f"**{g['group']['name']}** — {g['role']['name']} (Rank {g['role']['rank']})" for g in groups[:15]]
                group_embed.description = "\n".join(lines)
                extra = len(groups) - 15
            else:
                group_embed.description = "This user is not in any groups."
                extra = 0

            pages.extend([discord_embed, roblox_embed, group_embed])
        else:
            not_verified_embed = embeds.warning_embed("Roblox Information", "This user has not verified their Roblox account.")
            pages.extend([discord_embed, not_verified_embed])
            extra = 0

        total = len(pages)
        for i, page in enumerate(pages, start=1):
            footer_extra = f" | +{extra} more groups" if (i == total and extra) else ""
            page.set_footer(text=f"{settings.FOOTER_TEXT} | Page {i}/{total}{footer_extra}", icon_url=settings.FOOTER_ICON)

        return pages

    @commands.command(name="bgcheck")
    async def bgcheck(self, ctx: commands.Context, member: discord.Member = None):
        member = member or ctx.author
        loading = embeds.info_embed("Running Background Check", f"Gathering data for {member.mention}...")
        message = await ctx.send(embed=loading)

        pages = await self._build_pages(ctx, member)
        current = 0
        await message.edit(embed=pages[current])

        for emoji in (PREV_EMOJI, NEXT_EMOJI, DELETE_EMOJI):
            try:
                await message.add_reaction(emoji)
            except discord.HTTPException:
                pass

        def check(reaction: discord.Reaction, user: discord.User):
            return (
                reaction.message.id == message.id
                and user.id == ctx.author.id
                and str(reaction.emoji) in (PREV_EMOJI, NEXT_EMOJI, DELETE_EMOJI)
            )

        while True:
            try:
                reaction, user = await self.bot.wait_for("reaction_add", timeout=120.0, check=check)
            except asyncio.TimeoutError:
                try:
                    await message.clear_reactions()
                except discord.HTTPException:
                    pass
                break

            emoji = str(reaction.emoji)

            try:
                await message.remove_reaction(emoji, user)
            except discord.HTTPException:
                pass

            if emoji == DELETE_EMOJI:
                try:
                    await message.delete()
                except discord.HTTPException:
                    pass
                break
            elif emoji == NEXT_EMOJI and current < len(pages) - 1:
                current += 1
                await message.edit(embed=pages[current])
            elif emoji == PREV_EMOJI and current > 0:
                current -= 1
                await message.edit(embed=pages[current])


async def setup(bot: commands.Bot):
    await bot.add_cog(BGCheck(bot))