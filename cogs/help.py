# cogs/help.py
from __future__ import annotations

import logging
import discord
from discord.ext import commands

logger = logging.getLogger("trpg_bot")

# ---- 內部：產生各頁 Embed ----
def _embed_home(prefix: str) -> discord.Embed:
    e = discord.Embed(
        title="📖 指令總覽",
        description="按下方按鈕切換分類；支援連續擲骰：在指令後加 `+次數`（上限 50）。",
        color=discord.Color.blurple(),
    )
    e.add_field(
        name="🎲 擲骰",
        value=f"`{prefix}dnd <骰式>`（相容 `{prefix}roll`）｜`{prefix}cc <技能>`",
        inline=False,
    )
    e.add_field(
        name="🧾 日誌",
        value=f"`{prefix}log stream set/off/mode/throttle`｜`{prefix}log level`｜`{prefix}log crit set/off`",
        inline=False,
    )
    e.add_field(
        name="🛠️ 管理（開發者）",
        value=f"`{prefix}admin restart`｜`{prefix}admin dev ...`｜`{prefix}admin rcfg ...`｜`{prefix}admin gstream ...`",
        inline=False,
    )
    e.set_footer(text=f"提示：例如 `{prefix}dnd +5 d20+3`、`{prefix}cc +10 65`")
    return e

def _embed_dice(prefix: str) -> discord.Embed:
    e = discord.Embed(title="🎲 擲骰（D&D / CoC 7e）", color=discord.Color.green())
    e.add_field(
        name=f"{prefix}dnd  /  {prefix}roll（相容）",
        value=(
            "**用法**：\n"
            f"- 一般：`{prefix}dnd 2d6+1`、`{prefix}dnd d100<=65`\n"
            f"- 連續：`{prefix}dnd +10 d20+5`（上限 50）\n"
            "**說明**：d20 自然 20/1 與 d100 自然 1/100 會標記大成功/大失敗（可在設定中調整）。"
        ),
        inline=False,
    )
    e.add_field(
        name=f"{prefix}cc（CoC 7e）",
        value=(
            "**用法**：\n"
            f"- 技能值：`{prefix}cc 65` 或 `{prefix}cc d100<=65`\n"
            f"- 連續：`{prefix}cc +20 40`\n"
            "**判定**：CRITICAL / EXTREME / HARD / REGULAR / FAIL / FUMBLE；"
            "符合 7e（01 為極佳、失手依技能值區間判定）。"
        ),
        inline=False,
    )
    return e

def _embed_logs(prefix: str) -> discord.Embed:
    e = discord.Embed(title="🧾 日誌 / 紀錄", color=discord.Color.orange())
    e.add_field(
        name=f"{prefix}log stream set #頻道",
        value="把**一般日誌**即時串流到該伺服器指定頻道（只需管理員）。",
        inline=False,
    )
    e.add_field(
        name=f"{prefix}log stream off / mode <live|batch> / throttle <毫秒>",
        value="關閉或調整串流模式與節流（建議 100–300ms）。",
        inline=False,
    )
    e.add_field(
        name=f"{prefix}log level <INFO|DEBUG|...>",
        value="調整**全域**日誌等級。",
        inline=False,
    )
    e.add_field(
        name=f"{prefix}log crit set #頻道 / off",
        value="設定/關閉**大成功/大失敗**的上報頻道（每伺服器獨立）。",
        inline=False,
    )
    e.add_field(
        name="全域輸出（跨伺服器）",
        value=f"由 `{prefix}admin gstream ...` 設定單一跨服輸出位置與模式。",
        inline=False,
    )
    return e

def _embed_admin(prefix: str) -> discord.Embed:
    e = discord.Embed(title="🛠️ 管理（開發者限定）", color=discord.Color.red())
    e.add_field(
        name=f"{prefix}admin restart",
        value="二次確認後重啟（支援 execv / systemd_user / systemd_system）。",
        inline=False,
    )
    e.add_field(
        name=f"{prefix}admin dev add/remove/list",
        value="管理開發者名單。",
        inline=False,
    )
    e.add_field(
        name=f"{prefix}admin rcfg mode/service/show",
        value="設定重啟模式與服務名。",
        inline=False,
    )
    e.add_field(
        name=f"{prefix}admin gstream set/off/mode/throttle/show",
        value="設定**全域**日誌輸出頻道與模式。",
        inline=False,
    )
    return e

def _embed_all(prefix: str) -> discord.Embed:
    e = discord.Embed(title="📚 全部指令速覽", color=discord.Color.light_grey())
    e.description = (
        f"**D&D**：`{prefix}dnd [+次數] <骰式>`（例：`{prefix}dnd 2d6+1`，`{prefix}dnd +5 d20>=15`）\n"
        f"**相容**：`{prefix}roll ...`\n"
        f"**CoC 7e**：`{prefix}cc [+次數] <技能>` 或 `d100<=技能`\n"
        f"**日誌**：`{prefix}log stream set/off/mode/throttle`，`{prefix}log level`，`{prefix}log crit set/off`\n"
        f"**管理**：`{prefix}admin restart`；`{prefix}admin dev ...`；`{prefix}admin rcfg ...`；`{prefix}admin gstream ...`"
    )
    return e

# ---- 互動面板 ----
class HelpView(discord.ui.View):
    def __init__(self, author_id: int, prefix: str, timeout: float = 180.0):
        super().__init__(timeout=timeout)
        self.author_id = author_id
        self.prefix = prefix
        self.page = "home"
        self.message: discord.Message | None = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("只有發起者可以操作這個幫助面板。", ephemeral=True)
            return False
        return True

    async def on_timeout(self) -> None:
        for c in self.children:
            if isinstance(c, (discord.ui.Button,)):
                c.disabled = True
        if self.message:
            try:
                await self.message.edit(view=self)
            except Exception:
                pass

    async def _show(self, interaction: discord.Interaction, page: str):
        self.page = page
        emb = {
            "home": _embed_home(self.prefix),
            "dice": _embed_dice(self.prefix),
            "logs": _embed_logs(self.prefix),
            "admin": _embed_admin(self.prefix),
            "all": _embed_all(self.prefix),
        }.get(page, _embed_home(self.prefix))
        await interaction.response.edit_message(embed=emb, view=self)

    @discord.ui.button(label="總覽", style=discord.ButtonStyle.secondary)
    async def btn_home(self, interaction: discord.Interaction, _: discord.ui.Button):
        await self._show(interaction, "home")

    @discord.ui.button(label="擲骰", style=discord.ButtonStyle.primary)
    async def btn_dice(self, interaction: discord.Interaction, _: discord.ui.Button):
        await self._show(interaction, "dice")

    @discord.ui.button(label="日誌", style=discord.ButtonStyle.secondary)
    async def btn_logs(self, interaction: discord.Interaction, _: discord.ui.Button):
        await self._show(interaction, "logs")

    @discord.ui.button(label="管理", style=discord.ButtonStyle.secondary)
    async def btn_admin(self, interaction: discord.Interaction, _: discord.ui.Button):
        await self._show(interaction, "admin")

    @discord.ui.button(label="全部", style=discord.ButtonStyle.secondary)
    async def btn_all(self, interaction: discord.Interaction, _: discord.ui.Button):
        await self._show(interaction, "all")

    @discord.ui.button(label="關閉", style=discord.ButtonStyle.danger)
    async def btn_close(self, interaction: discord.Interaction, _: discord.ui.Button):
        await interaction.response.edit_message(content="（已關閉說明）", embed=None, view=None)

# ---- Cog ----
class HelpCog(commands.Cog, name="Help"):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        logger.info("HelpCog ready.")

    @commands.command(name="help", aliases=["h"], help="顯示互動式說明")
    async def help_cmd(self, ctx: commands.Context, *, section: str | None = None):
        prefix = ctx.prefix or "rpg!"
        view = HelpView(author_id=ctx.author.id, prefix=prefix)
        # 選擇預設頁
        sec = (section or "").lower().strip()
        page = {
            "dice": "dice", "dnd": "dice", "roll": "dice", "cc": "dice",
            "log": "logs", "logs": "logs",
            "admin": "admin", "all": "all"
        }.get(sec, "home")
        emb = {
            "home": _embed_home(prefix),
            "dice": _embed_dice(prefix),
            "logs": _embed_logs(prefix),
            "admin": _embed_admin(prefix),
            "all": _embed_all(prefix),
        }[page]
        msg = await ctx.reply(embed=emb, view=view)
        view.message = msg
