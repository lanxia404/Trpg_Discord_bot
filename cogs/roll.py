import logging
import discord
from discord.ext import commands
from utils.dice import parse_and_roll, DiceError
from utils.config import ConfigManager

logger = logging.getLogger("trpg_bot")

class RollCog(commands.Cog, name="Roll"):
    def __init__(self, bot: commands.Bot, config: ConfigManager):
        self.bot = bot
        self.config = config

    @commands.Cog.listener()
    async def on_ready(self):
        logger.info("RollCog ready.")

    @commands.command(name="roll", help="擲骰：如 rpg!roll 2d6+1、rpg!roll d100<=65")
    async def roll(self, ctx: commands.Context, *, expr: str):
        try:
            crit = self.config.get_crit_rules()
            result = parse_and_roll(
                expr,
                d20_crit_succ=crit.d20_crit_success,
                d20_crit_fail=crit.d20_crit_failure,
                d100_crit_succ=crit.d100_crit_success,
                d100_crit_fail=crit.d100_crit_failure,
            )
        except DiceError as e:
            await ctx.reply(str(e))
            logger.info(f"Bad roll by {ctx.author} in #{ctx.channel}: {e}")
            return

        # 組合一般回覆
        title = "🎲 擲骰結果"
        if result.is_crit_success:
            title = "🎉 大成功！"
        elif result.is_crit_failure:
            title = "💥 大失敗！"

        desc_lines = [
            f"表達式：`{result.expr}`",
            f"擲出：`{result.detail}`",
            f"總和：**{result.total}**",
        ]
        if result.cmp and result.target is not None:
            ok = eval(f"{result.total} {result.cmp} {result.target}")
            desc_lines.append(f"檢定：**{'成功' if ok else '失敗'}**（{result.total} {result.cmp} {result.target}）")

        embed = discord.Embed(
            title=title,
            description="\n".join(desc_lines),
            color=discord.Color.random()
        )
        embed.set_footer(text=f"{ctx.author} • #{ctx.channel}")
        await ctx.reply(embed=embed)

        # 紀錄到指定頻道（只有大成功/大失敗時）
        if result.is_crit_success or result.is_crit_failure:
            channel_id = self.config.get_log_channel_id()
            if channel_id:
                channel = self.bot.get_channel(channel_id)
                if channel:
                    log_embed = discord.Embed(
                        title=title,
                        description=(
                            f"玩家：{ctx.author.mention}\n"
                            f"頻道：#{ctx.channel}\n"
                            f"表達式：`{result.expr}`\n"
                            f"擲出：`{result.detail}`\n"
                            f"總和：**{result.total}**"
                        ),
                        color=discord.Color.red() if result.is_crit_failure else discord.Color.green(),
                    )
                    await channel.send(embed=log_embed)
                else:
                    logger.warning(f"設定的紀錄頻道找不到：{channel_id}")
            else:
                logger.info("尚未設定大成敗紀錄頻道，略過上報。")

    @commands.command(name="setlog", help="設定大成功/大失敗紀錄頻道：rpg!setlog #頻道")
    @commands.has_guild_permissions(manage_guild=True)
    async def set_log_channel(self, ctx: commands.Context, channel: discord.TextChannel):
        self.config.set_log_channel(channel.id)
        await ctx.reply(f"已設定紀錄頻道為 {channel.mention}")
        logger.info(f"Log channel set to {channel.id} by {ctx.author} in guild {ctx.guild.id}")

    @set_log_channel.error
    async def set_log_channel_error(self, ctx: commands.Context, error):
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.reply("用法：`rpg!setlog #頻道`")
        elif isinstance(error, commands.MissingPermissions):
            await ctx.reply("你沒有權限（需要「管理伺服器」）。")
        else:
            await ctx.reply(f"設定失敗：{error}")
            logger.error(f"setlog error: {error}")
