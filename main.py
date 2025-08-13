import logging
import os
from dotenv import load_dotenv, find_dotenv
import discord
from discord.ext import commands

from utils.logging_config import setup_logging
from utils.config import ConfigManager

# --- 啟動階段 ---
load_dotenv(find_dotenv())
setup_logging()
logger = logging.getLogger("trpg_bot")

TOKEN = os.getenv("DISCORD_TOKEN")
if not TOKEN:
    raise RuntimeError("請在 .env 設定 DISCORD_TOKEN")

intents = discord.Intents.default()
intents.message_content = True  # 需要讀取訊息內容才能解析擲骰
bot = commands.Bot(command_prefix="rpg!", intents=intents, help_command=None)

# 共用設定管理器（讓各 cogs 使用）
config_manager = ConfigManager()
# 取得應用程式擁有者（做為預設開發者）
app_own_id = None

@bot.event
async def setup_hook():
    # 取得應用程式擁有者
    try:
        info = await bot.application_info()
        if info and info.owner:
            global app_owner_id
            app_owner_id = info.owner.id
            # 如果 config 沒有任何開發者，預設把 app owner 加進去
            if not config_manager.get_dev_user_ids():
                config_manager.add_dev_user(app_owner_id)
                logger.info(f"預設開發者加入：{app_owner_id}")
    except Exception as e:
        logger.warning(f"讀取 application owner 失敗：{e}")

    # 載入各類 cogs
    await bot.add_cog(
        __import__("cogs.dice", fromlist=["DiceCog"]).DiceCog(bot, config_manager))
        
    await bot.add_cog(
        __import__("cogs.logs", fromlist=["LogsCog"]).LogsCog(bot, config_manager))
    await bot.add_cog(
        __import__("cogs.admin", fromlist=["AdminCog"]).AdminCog(bot, config_manager, app_owner_id))
    await bot.add_cog(
        __import__("cogs.help", fromlist=["HelpCog"]).HelpCog(bot))
@bot.event
async def on_ready():
    logger.info(f"Logged in as {bot.user} (id={bot.user.id})")
    try:
        await bot.tree.sync()
    except Exception as e:
        logger.warning(f"App commands sync failed: {e}")

    
bot.run(TOKEN)
