"""
config/settings.py
-------------------
Central branding and styling configuration for the Royal Guard bot.
Edit these values to reskin embeds, colors, and panel text without
touching any cog logic.
"""

import os

# ============================================================
# BOT BRANDING
# ============================================================
BOT_NAME = "Royal Guard"
BOT_TAG = "British Army Verification System"
BOT_VERSION = "V5"

# Logo/crest used across embeds (Royal Guard crest, hosted image URL)
BOT_ICON_URL = os.getenv(
    "BOT_ICON_URL",
    "https://i.imgur.com/placeholder_crest.png"  # Replace with your hosted crest image
)

# ============================================================
# COLORS (hex ints, used directly in discord.Color)
# ============================================================
EMBED_COLOR = 0x2B2D31    # Neutral dark embed color (matches Discord dark theme)
SUCCESS_COLOR = 0x57A05A  # Green
ERROR_COLOR = 0xE74C3C    # Red
WARNING_COLOR = 0xF1C40F  # Yellow
INFO_COLOR = 0x3498DB     # Blue

# ============================================================
# FOOTER / AUTHOR
# ============================================================
FOOTER_TEXT = f"{BOT_NAME} {BOT_VERSION}"
FOOTER_ICON = BOT_ICON_URL

AUTHOR_TEXT = BOT_NAME
AUTHOR_ICON = BOT_ICON_URL

# ============================================================
# VERIFICATION PANEL TEXT
# ============================================================
VERIFICATION_PANEL_TITLE = "BRITISH ARMY VERIFICATION SYSTEM V5"
VERIFICATION_PANEL_DESCRIPTION = (
    "Press the **Verify / Reverify** button to verify or reverify your ROBLOX account."
)

# ============================================================
# TICKET PANEL TEXT
# ============================================================
TICKET_PANEL_TITLE = "ROYAL GUARD SUPPORT"
TICKET_PANEL_DESCRIPTION = (
    "Select a category below to open a ticket with the appropriate team.\n\n"
    "Please only open a ticket for genuine matters. Abuse of the ticket system "
    "may result in disciplinary action."
)

REPORT_TICKET_OPTIONS = [
    ("Report High Rank", "report_high_rank", "🎖️"),
    ("Report Exploiter", "report_exploiter", "🛑"),
    ("Report Corruption", "report_corruption", "⚖️"),
    ("Report Abuser", "report_abuser", "🚫"),
    ("Report Rule Breaker", "report_rulebreaker", "📋"),
]

OTHER_TICKET_OPTIONS = [
    ("Report Bug / Glitch", "report_bug", "🐛"),
    ("Report Exploit Script", "report_exploit_script", "💻"),
    ("Developer Application", "dev_application", "🧑‍💻"),
    ("Alliance Application", "alliance_application", "🤝"),
]

# ============================================================
# ADMIN LEVELS
# ============================================================
OWNER_LEVEL = 999999
UPDATEALL_MIN_LEVEL = 10

# ============================================================
# MISC
# ============================================================
COMMAND_PREFIX = "!"