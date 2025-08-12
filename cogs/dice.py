# cogs/dice.py
import logging
import discord
from discord.ext import commands
from utils.dice import parse_and_roll, DiceError, extract_repeat
from utils.config import ConfigManager
from utils import coc as coc7

logger = logging.getLogger("trpg_bot")

class DiceCog(commands.Cog, name="Dice"):
    def __init__(self, bot: commands.Bot, config: ConfigManager):
        self.bot = bot
        self.config = config

    @commands.Cog.listener()
    async def on_ready(self):
        logger.info("DiceCog ready.")

    # ---- D&D 骰（取代原 roll），相容舊指令 ----
    @commands.command(name="dnd", help="D&D 擲骰：rpg!dnd [+次數] <骰式> 例：rpg!dnd 2d6+1 / rpg!dnd +5 d20>=15")
    async def dnd(self, ctx: commands.Context, *, expr: str):
        await self._do_dnd(ctx, expr)

    @commands.command(name="roll", help="（相容）請改用 rpg!dnd；語法相同。")
    async def roll_alias(self, ctx: commands.Context, *, expr: str):
        await self._do_dnd(ctx, expr)

    async def _do_dnd(self, ctx: commands.Context, expr: str):
        try:
            times, core = extract_repeat(expr)
        except DiceError as e:
            return await ctx.reply(str(e))

        crit_rules = self.config.get_crit_rules(ctx.guild.id if ctx.guild else None)

        results = []
        crit_count = fumble_count = 0
        for _ in range(times):
            try:
                r = parse_and_roll(
                    core,
                    d20_crit_succ=crit_rules.d20_crit_success,
                    d20_crit_fail=crit_rules.d20_crit_failure,
                    d100_crit_succ=crit_rules.d100_crit_success,
                    d100_crit_fail=crit_rules.d100_crit_failure,
                )
                results.append(r)
                crit_count += int(r.is_crit_success)
                fumble_count += int(r.is_crit_failure)
            except DiceError as e:
                return await ctx.reply(str(e))

        # 組合輸出
        if times == 1:
            title = "🎲 擲骰結果"
            if results[0].is_crit_success: title = "🎉 大成功！"
            if results[0].is_crit_failure: title = "💥 大失敗！"
            lines = [
                f"表達式：`{results[0].expr}`",
                f"擲出：`{results[0].detail}`",
                f"總和：**{results[0].total}**",
            ]
            if results[0].cmp and results[0].target is not None:
                ok = eval(f"{results[0].total} {results[0].cmp} {results[0].target}")
                lines.append(f"檢定：**{'成功' if ok else '失敗'}**（{results[0].total} {results[0].cmp} {results[0].target}）")
        else:
            title = f"🎲 連續擲骰 x{times}"
            shown = min(10, times)
            detail_lines = [f"{i+1:>2}: {r.detail} = {r.total}" for i, r in enumerate(results[:shown])]
            if times > shown:
                detail_lines.append(f"...（僅顯示前 {shown} 次）")
            lines = [
                f"表達式：`{core}`",
                "— 明細 —",
                *detail_lines,
                "— 統計 —",
                f"大成功：{crit_count} 次， 大失敗：{fumble_count} 次",
            ]

        embed = discord.Embed(title=title, description="\n".join(lines), color=discord.Color.random())
        embed.set_footer(text=f"{ctx.author} • #{ctx.channel}")
        await ctx.reply(embed=embed)

        # 上報大成敗
        if ctx.guild and (crit_count or fumble_count):
            ch_id = self.config.get_crit_log_channel_id(ctx.guild.id)
            if ch_id:
                ch = self.bot.get_channel(ch_id)
                if isinstance(ch, discord.TextChannel):
                    desc = (
                        f"玩家：{ctx.author.mention}\n"
                        f"頻道：#{ctx.channel}\n"
                        f"表達式：`{core}`\n"
                        f"連續次數：{times}\n"
                        f"大成功：{crit_count}，大失敗：{fumble_count}"
                    )
                    await ch.send(embed=discord.Embed(
                        title="🎲 D&D 連續擲骰統計",
                        description=desc,
                        color=discord.Color.green() if crit_count >= fumble_count else discord.Color.red()
                    ))

    # ---- CoC 7e ----
    @commands.command(name="cc", help="CoC 7e：rpg!cc [+次數] <技能值>（例：rpg!cc 65 / rpg!cc +5 40）或 rpg!cc d100<=65")
    async def coc(self, ctx: commands.Context, *, expr: str):
        try:
            times, core = extract_repeat(expr)
        except DiceError as e:
            return await ctx.reply(str(e))

        # 解析技能值（容許 'd100<=65' 或純 '65'）
        skill = None
        core_strip = core.replace(" ", "")
        if core_strip.lower().startswith("d100<="):
            try:
                skill = int(core_strip[6:])
            except ValueError:
                return await ctx.reply("技能值格式錯誤。例：`rpg!cc 65` 或 `rpg!cc d100<=65`")
        else:
            try:
                skill = int(core_strip)
            except ValueError:
                return await ctx.reply("技能值格式錯誤。例：`rpg!cc 65` 或 `rpg!cc d100<=65`")

        # 連續擲骰
        bucket = {"大成功":0,"極限成功":0,"困難成功":0,"普通成功":0,"失敗":0,"大失敗":0}
        rolls = []
        for _ in range(times):
            r = coc7.evaluate(skill, coc7.d100())
            rolls.append(r)
            bucket[r.level] += 1

        # 輸出
        if times == 1:
            r = rolls[0]
            title = "🎲 CoC 7e"
            if r.is_crit: title = "🎉 大成功"
            elif r.is_fumble: title = "💥 大失敗"
            lines = [
                f"骰值：**{r.skill}**",
                f"擲出：**{r.roll:02d}**",
                f"判定：**{r.level}**（閾值：極限≤{max(1,r.skill//5)}、困難≤{max(1,r.skill//2)}、普通≤{r.skill}）",
            ]
        else:
            title = f"🎲 CoC 7e 連續擲骰 x{times}"
            shown = min(10, times)
            detail_lines = [f"{i+1:>2}: {r.roll:02d} → {r.level}" for i, r in enumerate(rolls[:shown])]
            if times > shown:
                detail_lines.append(f"...（僅顯示前 {shown} 次）")
            lines = [
                f"骰值：**{skill}**",
                "— 明細 —",
                *detail_lines,
                "— 統計 —",
                f"🎉大成功：{bucket['大成功']}｜極限成功：{bucket['極限成功']}｜困難成功：{bucket['困難成功']}｜普通成功：{bucket['普通成功']}｜失敗：{bucket['失敗']}｜大失敗☠️：{bucket['大失敗']}",
            ]

        embed = discord.Embed(title=title, description="\n".join(lines), color=discord.Color.random())
        embed.set_footer(text=f"{ctx.author} • #{ctx.channel}")
        await ctx.reply(embed=embed)

        # 上報（有 大成功 或 大失敗 時）
        if ctx.guild and (bucket["大成功"] or bucket["大失敗"]):
            ch_id = self.config.get_crit_log_channel_id(ctx.guild.id)
            if ch_id:
                ch = self.bot.get_channel(ch_id)
                if isinstance(ch, discord.TextChannel):
                    desc = (
                        f"玩家：{ctx.author.mention}\n"
                        f"頻道：#{ctx.channel}\n"
                        f"技能值：{skill}\n"
                        f"連續次數：{times}\n"
                        f"🎉大成功：{bucket['大成功']}，大失敗☠️：{bucket['大失敗']}"
                    )
                    await ch.send(embed=discord.Embed(
                        title="🎲 CoC 7e 大成功/大失敗統計",
                        description=desc,
                        color=discord.Color.green() if bucket["大成功"] >= bucket["大失敗"] else discord.Color.red()
                    ))
