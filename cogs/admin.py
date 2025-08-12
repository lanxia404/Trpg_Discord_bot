import logging
import os
import sys
import asyncio
import subprocess 
import discord
from discord.ext import commands
from utils.config import ConfigManager

logger = logging.getLogger("trpg_bot")

def is_dev(ctx: commands.Context, config: ConfigManager, app_owner_id: int | None):
    uid = ctx.author.id
    return (app_owner_id is not None and uid == app_owner_id) or config.is_developer(uid)

class ConfirmRestartView(discord.ui.View):
    def __init__(self, on_confirm, requester_id: int, timeout: float = 30.0):
        super().__init__(timeout=timeout)
        self.on_confirm = on_confirm
        self.requester_id = requester_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.requester_id:
            await interaction.response.send_message("只有發起者可以操作這個確認。", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="確認重啟", style=discord.ButtonStyle.danger)
    async def btn_confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(content="正在重啟……", view=None)
        await self.on_confirm()

    @discord.ui.button(label="取消", style=discord.ButtonStyle.secondary)
    async def btn_cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(content="已取消重啟。", view=None)

class AdminCog(commands.Cog, name="Admin"):
    def __init__(self, bot: commands.Bot, config: ConfigManager, app_owner_id: int | None):
        self.bot = bot
        self.config = config
        self.app_owner_id = app_owner_id

    def _is_dev_or_reply(self, ctx, cfg, owner_id):
        if not ((owner_id is not None and ctx.author.id == owner_id) or cfg.is_developer(ctx.author.id)):
            return False
        return True
    
    @commands.group(name="admin", invoke_without_command=True)
    async def admin_group(self, ctx: commands.Context):
        await ctx.reply("管理指令：`rpg!admin restart`｜`rpg!admin dev add/remove/list`｜"
                        "`rpg!admin rcfg mode/service/show`｜`rpg!admin gstream ...`")
    
    @admin_group.group(name="gstream", invoke_without_command=True)
    async def admin_gstream_group(self, ctx: commands.Context):
        if not self._is_dev_or_reply(ctx, self.config, self.app_owner_id):
            return await ctx.reply("你不是開發者。")
        await ctx.reply("用法：`rpg!admin gstream set <channel_id|#mention>`｜`rpg!admin gstream off`｜"
                        "`rpg!admin gstream mode <live|batch>`｜`rpg!admin gstream throttle <毫秒>`｜`rpg!admin gstream show`")
    
    @admin_gstream_group.command(name="set")
    async def admin_gstream_set(self, ctx: commands.Context, channel: str):
        if not self._is_dev_or_reply(ctx, self.config, self.app_owner_id):
            return await ctx.reply("你不是開發者。")
        # 解析 channel：<#123> 或 純數字
        channel_id = None
        if channel.startswith("<#") and channel.endswith(">"):
            channel_id = int(channel[2:-1])
        elif channel.isdigit():
            channel_id = int(channel)
        else:
            return await ctx.reply("請提供頻道 ID 或在同伺服器使用 #頻道 提及。")
    
        ch = self.bot.get_channel(channel_id)
        if not isinstance(ch, discord.TextChannel):
            return await ctx.reply("找不到該文字頻道，請確認 bot 有在該伺服器內。")
    
        self.config.set_global_stream_channel(channel_id)
        await ctx.reply(f"全域日誌輸出頻道已設定為 {ch.mention}")
    
    @admin_gstream_group.command(name="off")
    async def admin_gstream_off(self, ctx: commands.Context):
        if not self._is_dev_or_reply(ctx, self.config, self.app_owner_id):
            return await ctx.reply("你不是開發者。")
        self.config.clear_global_stream_channel()
        await ctx.reply("已關閉全域日誌輸出。")
    
    @admin_gstream_group.command(name="mode")
    async def admin_gstream_mode(self, ctx: commands.Context, mode: str):
        if not self._is_dev_or_reply(ctx, self.config, self.app_owner_id):
            return await ctx.reply("你不是開發者。")
        try:
            self.config.set_global_stream_mode(mode)
        except ValueError as e:
            return await ctx.reply(str(e))
        await ctx.reply(f"全域日誌串流模式已設為 **{mode}**")
    
    @admin_gstream_group.command(name="throttle")
    async def admin_gstream_throttle(self, ctx: commands.Context, ms: int):
        if not self._is_dev_or_reply(ctx, self.config, self.app_owner_id):
            return await ctx.reply("你不是開發者。")
        self.config.set_global_stream_throttle(ms)
        await ctx.reply(f"全域串流節流已設為 **{ms}ms**")
    
    @admin_gstream_group.command(name="show")
    async def admin_gstream_show(self, ctx: commands.Context):
        if not self._is_dev_or_reply(ctx, self.config, self.app_owner_id):
            return await ctx.reply("你不是開發者。")
        ch_id = self.config.get_global_stream_channel_id()
        s = self.config.get_global_stream_settings()
        await ctx.reply(f"全域輸出：channel_id=`{ch_id}`，mode=`{s.mode}`，throttle=`{s.throttle_ms}ms`，chunk=`{s.chunk_limit}`")
    

    @commands.Cog.listener()
    async def on_ready(self):
        logger.info("AdminCog ready.")

    @commands.group(name="admin", invoke_without_command=True)
    async def admin_group(self, ctx: commands.Context):
        await ctx.reply("管理指令：`rpg!admin restart`｜`rpg!admin dev add @user`｜`rpg!admin dev remove @user`｜`rpg!admin dev list`")

    # ===== 重啟（需要二次確認，開發者限定）=====
    @admin_group.command(name="restart", help="重啟 Bot（開發者限定，需二次確認）")
    async def admin_restart(self, ctx: commands.Context):
        if not is_dev(ctx, self.config, self.app_owner_id):
            return await ctx.reply("你不是開發者，不能使用此指令。")

        r = self.config.get_restart()

        async def do_restart():
            try:
                if r.mode == "execv":
                    # 就地重啟（非 systemd）
                    await asyncio.sleep(0.3)
                    sys.stdout.flush()
                    os.execv(sys.executable, [sys.executable] + sys.argv)

                elif r.mode == "systemd_user":
                    # 使用使用者的 systemd 服務
                    # 提醒：需要 `loginctl enable-linger <user>` 才能常駐
                    subprocess.Popen(["systemctl", "--user", "restart", r.service])
                    # 讓指令送出去，systemd 會接手終止本程序
                    await asyncio.sleep(0.5)

                elif r.mode == "systemd_system":
                    # 系統服務（需要權限，通常要配合 PolicyKit/sudo）
                    subprocess.Popen(["systemctl", "restart", r.service])
                    await asyncio.sleep(0.5)

                else:
                    await ctx.send(f"未知的 restart 模式：{r.mode}")
            except Exception as e:
                await ctx.send(f"重啟失敗：{e}")

        view = ConfirmRestartView(on_confirm=do_restart, requester_id=ctx.author.id)
        await ctx.reply("⚠️ 確認要重啟 Bot？（30 秒內）", view=view)
        
    # ---- 開發者名單管理 ----
    @admin_group.group(name="dev", invoke_without_command=True)
    async def admin_dev_group(self, ctx: commands.Context):
        await ctx.reply("用法：`rpg!admin dev add @user`｜`rpg!admin dev remove @user`｜`rpg!admin dev list`")

    @admin_dev_group.command(name="add")
    async def admin_dev_add(self, ctx: commands.Context, user: discord.User):
        # 只有現有開發者或 App Owner 可以新增
        if not is_dev(ctx, self.config, self.app_owner_id):
            return await ctx.reply("你不是開發者，不能修改開發者名單。")
        self.config.add_dev_user(user.id)
        await ctx.reply(f"已加入開發者：{user.mention}")

    @admin_dev_group.command(name="remove")
    async def admin_dev_remove(self, ctx: commands.Context, user: discord.User):
        if not is_dev(ctx, self.config, self.app_owner_id):
            return await ctx.reply("你不是開發者，不能修改開發者名單。")
        self.config.remove_dev_user(user.id)
        await ctx.reply(f"已移除開發者：{user.mention}")

    @admin_dev_group.command(name="list")
    async def admin_dev_list(self, ctx: commands.Context):
        ids = self.config.get_dev_user_ids()
        if not ids:
            return await ctx.reply("目前沒有開發者。")
        users = [f"<@{uid}>" for uid in ids]
        await ctx.reply("開發者名單：\n" + "\n".join(users))

    # ---- 重啟設定（rcfg）----
    @admin_group.group(name="rcfg", invoke_without_command=True)
    async def restart_cfg_group(self, ctx: commands.Context):
        await ctx.reply("用法：`rpg!admin rcfg mode <execv|systemd_user|systemd_system>`｜`rpg!admin rcfg service <name>`｜`rpg!admin rcfg show`")

    @restart_cfg_group.command(name="mode")
    async def restart_cfg_mode(self, ctx: commands.Context, mode: str):
        if not is_dev(ctx, self.config, self.app_owner_id):
            return await ctx.reply("你不是開發者。")
        try:
            self.config.set_restart_mode(mode)
        except ValueError as e:
            return await ctx.reply(str(e))
        await ctx.reply(f"已設定重啟模式為：**{mode}**")

    @restart_cfg_group.command(name="service")
    async def restart_cfg_service(self, ctx: commands.Context, service_name: str):
        if not is_dev(ctx, self.config, self.app_owner_id):
            return await ctx.reply("你不是開發者。")
        self.config.set_restart_service(service_name)
        await ctx.reply(f"已設定服務名稱為：**{self.config.get_restart().service}**")

    @restart_cfg_group.command(name="show")
    async def restart_cfg_show(self, ctx: commands.Context):
        r = self.config.get_restart()
        await ctx.reply(f"重啟設定：mode=`{r.mode}`，service=`{r.service}`")
