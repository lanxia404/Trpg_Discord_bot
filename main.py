import logging
import os
from dotenv import load_dotenv, find_dotenv
import discord
from discord.ext import commands

from utils.logging_config import setup_logging
from utils.config import ConfigManager

# --- 啟動階段 ---
setup_logging()
logger = logging.getLogger("trpg_bot")

load_dotenv(find_dotenv())
TOKEN = os.getenv("DISCORD_TOKEN")
if not TOKEN:
    raise RuntimeError("請在 .env 設定 DISCORD_TOKEN")

intents = discord.Intents.default()
intents.message_content = True  # 需要讀取訊息內容才能解析擲骰
bot = commands.Bot(command_prefix="rpg!", intents=intents)

# 共用設定管理器（讓各 cogs 使用）
config_manager = ConfigManager()

@bot.event
async def on_ready():
    logger.info(f"Logged in as {bot.user} (id={bot.user.id})")
    try:
        await bot.tree.sync()
    except Exception as e:
        logger.warning(f"App commands sync failed: {e}")

# 載入擲骰 cog
async def setup_extensions():
    await bot.add_cog(
        __import__("cogs.roll", fromlist=["RollCog"]).RollCog(bot, config_manager)
    )

@bot.event
async def setup_hook():
    await setup_extensions()
    logger.info("All cogs loaded.")

bot.run(TOKEN)
