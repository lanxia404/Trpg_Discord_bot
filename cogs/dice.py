import logging
import discord
from discord.ext import commands
from utils.dice import parse_and_roll, DiceError
from utils.config import ConfigManager

logger = logging.getLogger("trpg_bot")

class DiceCog(commands.Cog, name="Dice"):
    def __init__(self, bot: commands.Bot, config: ConfigManager):
        self.bot = bot
        self.config = config

    @commands.Cog.listener()
    async def on_ready(self):
        logger.info("DiceCog ready.")

    @commands.command(name="roll", help="擲骰：如 rpg!roll 2d6+1、rpg!roll d100<=65")
    async def roll(self, ctx: commands.Context, *, expr: str):
        try:
            guild_id = ctx.guild.id if ctx.guild else None
            crit = self.config.get_crit_rules(guild_id)
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

        title = "🎲 擲骰結果"
        if result.is_crit_success: title = "🎉 大成功！"
        elif result.is_crit_failure: title = "💥 大失敗！"

        lines = [
            f"表達式：`{result.expr}`",
            f"擲出：`{result.detail}`",
            f"總和：**{result.total}**",
        ]
        if result.cmp and result.target is not None:
            ok = eval(f"{result.total} {result.cmp} {result.target}")
            lines.append(f"檢定：**{'成功' if ok else '失敗'}**（{result.total} {result.cmp} {result.target}）")

        embed = discord.Embed(title=title, description="\n".join(lines), color=discord.Color.random())
        embed.set_footer(text=f"{ctx.author} • #{ctx.channel}")
        await ctx.reply(embed=embed)

        # 大成敗送到該伺服器的紀錄頻道
        if (result.is_crit_success or result.is_crit_failure) and ctx.guild:
            channel_id = self.config.get_crit_log_channel_id(ctx.guild.id)
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

    @commands.command(name="setlog", help="（已移動）請改用：rpg!log crit set #頻道")
    @commands.has_guild_permissions(manage_guild=True)
    async def setlog_deprecated(self, ctx: commands.Context, channel: discord.TextChannel = None):
        await ctx.reply("此指令已移動到 `rpg!log crit set #頻道`。")
