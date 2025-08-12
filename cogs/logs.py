# cogs/logs.py
from __future__ import annotations

import logging
import asyncio
import time
from dataclasses import dataclass, field
import discord
from discord.ext import commands

from utils.config import ConfigManager
from utils.logging_config import LOG_QUEUE

logger = logging.getLogger("trpg_bot")

def to_level(name: str) -> int:
    name = (name or "").upper()
    return getattr(logging, name, logging.INFO)

@dataclass
class LiveState:
    message: discord.Message | None = None
    buffer: list[str] = field(default_factory=list)
    last_edit_ts: float = 0.0

class LogsCog(commands.Cog, name="Logs"):
    def __init__(self, bot: commands.Bot, config: ConfigManager):
        self.bot = bot
        self.config = config
        self._relay_task: asyncio.Task | None = None
        # guild_id -> LiveState；0 代表全域
        self._live_state: dict[int, LiveState] = {}

    @commands.Cog.listener()
    async def on_ready(self):
        logger.info("LogsCog ready.")
        if self._relay_task is None:
            self._relay_task = self.bot.loop.create_task(self._relay_logs())

    # ---------- live 模式輔助 ----------
    def _state(self, guild_id: int) -> LiveState:
        st = self._live_state.get(guild_id)
        if st is None:
            st = LiveState()
            self._live_state[guild_id] = st
        return st

    def _render_live_text(self, guild_id: int) -> str:
        st = self._state(guild_id)
        s = "\n".join(st.buffer)
        if guild_id == 0:
            limit = self.config.get_global_stream_settings().chunk_limit
        else:
            limit = self.config.get_stream_settings(guild_id).chunk_limit
        if len(s) > limit:
            s = s[-limit:]
        return "🔴 **Live Log**\n```log\n" + s + "\n```"

    async def _ensure_live_message(self, guild_id: int, channel: discord.TextChannel):
        st = self._state(guild_id)
        content = self._render_live_text(guild_id)
        try:
            if st.message is None:
                st.message = await channel.send(content if content.strip() else "🔴 **Live Log**\n```log\n(啟動)\n```")
            else:
                if len(content) > 1950:
                    st.message = await channel.send("🔴 **Live Log**\n```log\n(續)\n```")
                    st.buffer.clear()
        except Exception:
            st.message = None

    async def _live_push(self, guild_id: int, channel: discord.TextChannel, line: str):
        st = self._state(guild_id)
        st.buffer.append(line)
        await self._ensure_live_message(guild_id, channel)

        throttle = (
            self.config.get_global_stream_settings().throttle_ms
            if guild_id == 0 else
            self.config.get_stream_settings(guild_id).throttle_ms
        ) / 1000.0

        now = time.monotonic()
        if now - st.last_edit_ts < throttle:
            return
        if st.message is None:
            return

        try:
            await st.message.edit(content=self._render_live_text(guild_id))
            st.last_edit_ts = time.monotonic()
        except Exception:
            st.message = None

    async def _batch_push(self, guild_id: int, channel: discord.TextChannel, first_line: str):
        batch = [first_line]
        try:
            while True:
                msg = await asyncio.wait_for(LOG_QUEUE.get(), timeout=1.0)
                batch.append(msg)
                if sum(len(x) for x in batch) > 1800:
                    break
        except asyncio.TimeoutError:
            pass

        text = "```log\n" + "\n".join(batch[-200:]) + "\n```"
        try:
            await channel.send(text)
        except Exception:
            pass

    async def _relay_logs(self):
        while not self.bot.is_closed():
            try:
                line = await LOG_QUEUE.get()

                # 先送全域
                try:
                    gch_id = self.config.get_global_stream_channel_id()
                    if gch_id:
                        gch = self.bot.get_channel(gch_id)
                        if isinstance(gch, discord.TextChannel):
                            gmode = self.config.get_global_stream_settings().mode
                            if gmode == "live":
                                await self._live_push(0, gch, line)
                            else:
                                await self._batch_push(0, gch, line)
                except Exception:
                    # 全域串流失敗不應中斷整體
                    pass

                # 再送每個伺服器
                try:
                    for guild_id in self.config.guilds_with_stream_channel():
                        ch_id = self.config.get_stream_log_channel_id(guild_id)
                        if not ch_id:
                            continue
                        ch = self.bot.get_channel(ch_id)
                        if not isinstance(ch, discord.TextChannel):
                            continue
                        mode = self.config.get_stream_settings(guild_id).mode
                        if mode == "live":
                            await self._live_push(guild_id, ch, line)
                        else:
                            await self._batch_push(guild_id, ch, line)
                except Exception:
                    # 個別伺服器錯誤也不應中斷整體
                    pass

            except Exception:
                # 主 loop catch；避免整個任務崩潰
                await asyncio.sleep(0.5)

    # ---------- 指令 ----------
    @commands.group(name="log", invoke_without_command=True)
    @commands.has_guild_permissions(manage_guild=True)
    async def log_group(self, ctx: commands.Context):
        await ctx.reply(
            "用法：\n"
            "`rpg!log stream set #頻道`｜`rpg!log stream off`\n"
            "`rpg!log stream mode <live|batch>`｜`rpg!log stream throttle <毫秒>`\n"
            "`rpg!log level <INFO|DEBUG|...>`｜`rpg!log crit set/off`"
        )

    @log_group.group(name="stream", invoke_without_command=True)
    async def log_stream_group(self, ctx: commands.Context):
        await ctx.reply("用法：`rpg!log stream set #頻道`｜`rpg!log stream off`｜`rpg!log stream mode <live|batch>`｜`rpg!log stream throttle <毫秒>`")

    @log_stream_group.command(name="set")
    async def log_stream_set(self, ctx: commands.Context, channel: discord.TextChannel):
        self.config.set_stream_log_channel(ctx.guild.id, channel.id)
        await ctx.reply(f"[{ctx.guild.name}] 一般日誌輸出頻道已設定為 {channel.mention}")
        if self.config.get_stream_settings(ctx.guild.id).mode == "live":
            st = self._state(ctx.guild.id)
            try:
                st.message = await channel.send("🔴 **Live Log**\n```log\n(啟動)\n```")
            except Exception:
                st.message = None
            st.buffer.clear()
            st.last_edit_ts = 0.0

    @log_stream_group.command(name="off")
    async def log_stream_off(self, ctx: commands.Context):
        self.config.clear_stream_log_channel(ctx.guild.id)
        st = self._state(ctx.guild.id)
        st.message = None
        st.buffer.clear()
        await ctx.reply(f"[{ctx.guild.name}] 已關閉一般日誌輸出到頻道。")

    @log_stream_group.command(name="mode")
    async def log_stream_mode(self, ctx: commands.Context, mode: str):
        try:
            self.config.set_stream_mode(ctx.guild.id, mode)
        except ValueError as e:
            return await ctx.reply(str(e))
        await ctx.reply(f"[{ctx.guild.name}] 日誌串流模式已設為 **{mode}**")
        if mode == "live":
            ch_id = self.config.get_stream_log_channel_id(ctx.guild.id)
            if ch_id:
                ch = self.bot.get_channel(ch_id)
                if isinstance(ch, discord.TextChannel):
                    st = self._state(ctx.guild.id)
                    try:
                        st.message = await ch.send("🔴 **Live Log**\n```log\n(啟動)\n```")
                    except Exception:
                        st.message = None
                    st.buffer.clear()
                    st.last_edit_ts = 0.0

    @log_stream_group.command(name="throttle")
    async def log_stream_throttle(self, ctx: commands.Context, ms: int):
        self.config.set_stream_throttle(ctx.guild.id, ms)
        await ctx.reply(f"[{ctx.guild.name}] live 模式節流時間已設為 **{ms}ms**（0 代表每行都更新，可能觸發速率限制）")

    @log_group.command(name="level")
    async def log_level(self, ctx: commands.Context, level: str):
        lvl = to_level(level)
        logging.getLogger().setLevel(lvl)
        await ctx.reply(f"全域日誌等級已設為 **{logging.getLevelName(lvl)}**")

    @log_group.group(name="crit", invoke_without_command=True)
    async def log_crit_group(self, ctx: commands.Context):
        await ctx.reply("用法：`rpg!log crit set #頻道` 或 `rpg!log crit off`")

    @log_crit_group.command(name="set")
    async def log_crit_set(self, ctx: commands.Context, channel: discord.TextChannel):
        self.config.set_crit_log_channel(ctx.guild.id, channel.id)
        await ctx.reply(f"[{ctx.guild.name}] 大成功/大失敗紀錄頻道已設定為 {channel.mention}")

    @log_crit_group.command(name="off")
    async def log_crit_off(self, ctx: commands.Context):
        self.config.set_crit_log_channel(ctx.guild.id, 0)
        await ctx.reply(f"[{ctx.guild.name}] 已關閉大成功/大失敗紀錄上報。")
