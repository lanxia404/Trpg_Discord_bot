from __future__ import annotations

import json
from dataclasses import dataclass, asdict, field
from pathlib import Path
import logging
from typing import Dict, Optional, List

logger = logging.getLogger("trpg_bot")

@dataclass
class CritRules:
    d20_crit_success: int = 20
    d20_crit_failure: int = 1
    d100_crit_success: int = 1
    d100_crit_failure: int = 100

@dataclass
class StreamSettings:
    mode: str = "live"      # "live" | "batch"
    throttle_ms: int = 200
    chunk_limit: int = 1800

@dataclass
class RestartSettings:
    mode: str = "execv"         # "execv" | "systemd_user" | "systemd_system"
    service: str = "trpg-bot.service"

@dataclass
class GlobalConfig:
    dev_user_ids: List[int] = field(default_factory=list)
    restart: RestartSettings = field(default_factory=RestartSettings)
     # ↓↓↓ 新增：全域日誌串流位置與設定
    gstream_channel_id: int = 0
    gstream: StreamSettings = field(default_factory=StreamSettings)

@dataclass
class GuildConfig:
    crit_log_channel_id: int = 0
    stream_log_channel_id: int = 0
    stream: StreamSettings = field(default_factory=StreamSettings)
    crit: CritRules = field(default_factory=CritRules)

class ConfigManager:
    def __init__(self, global_path: str = "data/config.global.json", guilds_dir: str = "data/guilds"):
        self.global_path = Path(global_path)
        self.guilds_dir = Path(guilds_dir)
        self.guilds_dir.mkdir(parents=True, exist_ok=True)
        self.global_path.parent.mkdir(parents=True, exist_ok=True)

        # 舊版 config.json -> 全域設定遷移
        legacy_path = self.global_path.parent / "config.json"
        if legacy_path.exists() and not self.global_path.exists():
            try:
                raw = json.loads(legacy_path.read_text(encoding="utf-8"))
                g = GlobalConfig(
                    dev_user_ids=raw.get("dev_user_ids", []),
                    restart=RestartSettings(
                        mode=raw.get("restart", {}).get("mode", "execv"),
                        service=raw.get("restart", {}).get("service", "trpg-bot.service"),
                    )
                )
                self.global_config = g
                self._save_global()
                logger.info("已從舊版 data/config.json 移轉全域設定到 data/config.global.json")
            except Exception as e:
                logger.warning(f"舊版設定移轉失敗：{e}")
                self.global_config = GlobalConfig()
                self._save_global()
        else:
            self.global_config = self._load_global()

        self.guild_cache: Dict[int, GuildConfig] = {}
        # 預先載入已存在的 guild 設定
        for p in self.guilds_dir.glob("*.json"):
            try:
                gid = int(p.stem)
                self.guild_cache[gid] = self._load_guild(gid)
            except Exception:
                continue

    # ---------- Global ----------
    def _load_global(self) -> GlobalConfig:
        try:
            if self.global_path.exists():
                raw = json.loads(self.global_path.read_text(encoding="utf-8"))
                r = raw.get("restart", {})
                s = raw.get("gstream", {})  # 可能不存在
                return GlobalConfig(
                    dev_user_ids=raw.get("dev_user_ids", []),
                    restart=RestartSettings(
                        mode=r.get("mode", "execv"),
                        service=r.get("service", "trpg-bot.service"),
                    ),
                    gstream_channel_id=raw.get("gstream_channel_id", 0),
                    gstream=StreamSettings(
                        mode=s.get("mode", "live"),
                        throttle_ms=s.get("throttle_ms", 200),
                        chunk_limit=s.get("chunk_limit", 1800),
                    ),
                )
        except Exception as e:
            logger.error(f"讀取全域設定失敗：{e}")
        return GlobalConfig()

    def _save_global(self):
        payload = asdict(self.global_config)
        self.global_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info("全域設定已儲存")

    # Developer（全域）
    def get_dev_user_ids(self) -> List[int]:
        return list(self.global_config.dev_user_ids)

    def add_dev_user(self, user_id: int):
        if user_id not in self.global_config.dev_user_ids:
            self.global_config.dev_user_ids.append(user_id)
            self._save_global()

    def remove_dev_user(self, user_id: int):
        if user_id in self.global_config.dev_user_ids:
            self.global_config.dev_user_ids.remove(user_id)
            self._save_global()

    def is_developer(self, user_id: int) -> bool:
        return user_id in self.global_config.dev_user_ids

    # Restart（全域）
    def get_restart(self) -> RestartSettings:
        return self.global_config.restart

    def set_restart_mode(self, mode: str):
        if mode not in ("execv", "systemd_user", "systemd_system"):
            raise ValueError("mode 必須是 execv / systemd_user / systemd_system")
        self.global_config.restart.mode = mode
        self._save_global()

    def set_restart_service(self, name: str):
        if not name.endswith(".service"):
            name += ".service"
        self.global_config.restart.service = name
        self._save_global()

    # ---------- Guild ----------
    def _guild_file(self, guild_id: int) -> Path:
        return self.guilds_dir / f"{guild_id}.json"

    def _load_guild(self, guild_id: int) -> GuildConfig:
        path = self._guild_file(guild_id)
        if not path.exists():
            cfg = GuildConfig()
            self.guild_cache[guild_id] = cfg
            self._save_guild(guild_id)
            return cfg
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            s = raw.get("stream", {})
            c = raw.get("crit", {})
            return GuildConfig(
                crit_log_channel_id=raw.get("crit_log_channel_id", 0),
                stream_log_channel_id=raw.get("stream_log_channel_id", 0),
                stream=StreamSettings(
                    mode=s.get("mode", "live"),
                    throttle_ms=s.get("throttle_ms", 200),
                    chunk_limit=s.get("chunk_limit", 1800),
                ),
                crit=CritRules(
                    d20_crit_success=c.get("d20_crit_success", 20),
                    d20_crit_failure=c.get("d20_crit_failure", 1),
                    d100_crit_success=c.get("d100_crit_success", 1),
                    d100_crit_failure=c.get("d100_crit_failure", 100),
                )
            )
        except Exception as e:
            logger.error(f"讀取伺服器設定失敗（{guild_id}）：{e}，使用預設值")
            return GuildConfig()

    def _save_guild(self, guild_id: int):
        cfg = self.guild_cache.get(guild_id)
        if cfg is None:
            return
        path = self._guild_file(guild_id)
        payload = asdict(cfg)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info(f"伺服器設定已儲存：{guild_id}")

    def get_guild_cfg(self, guild_id: int) -> GuildConfig:
        cfg = self.guild_cache.get(guild_id)
        if cfg is None:
            cfg = self._load_guild(guild_id)
            self.guild_cache[guild_id] = cfg
        return cfg

    # Guild 欄位存取
    def get_crit_rules(self, guild_id: Optional[int] = None) -> CritRules:
        if guild_id is None:
            return CritRules()
        return self.get_guild_cfg(guild_id).crit

    def set_crit_rules(self, guild_id: int, **kwargs):
        cfg = self.get_guild_cfg(guild_id)
        for k, v in kwargs.items():
            if hasattr(cfg.crit, k):
                setattr(cfg.crit, k, int(v))
        self._save_guild(guild_id)

    def get_crit_log_channel_id(self, guild_id: int) -> int:
        return self.get_guild_cfg(guild_id).crit_log_channel_id

    def set_crit_log_channel(self, guild_id: int, channel_id: int):
        cfg = self.get_guild_cfg(guild_id)
        cfg.crit_log_channel_id = int(channel_id)
        self._save_guild(guild_id)

    def get_stream_log_channel_id(self, guild_id: int) -> int:
        return self.get_guild_cfg(guild_id).stream_log_channel_id

    def set_stream_log_channel(self, guild_id: int, channel_id: int):
        cfg = self.get_guild_cfg(guild_id)
        cfg.stream_log_channel_id = int(channel_id)
        self._save_guild(guild_id)

    def clear_stream_log_channel(self, guild_id: int):
        cfg = self.get_guild_cfg(guild_id)
        cfg.stream_log_channel_id = 0
        self._save_guild(guild_id)

    def get_stream_settings(self, guild_id: int) -> StreamSettings:
        return self.get_guild_cfg(guild_id).stream

    def set_stream_mode(self, guild_id: int, mode: str):
        if mode not in ("live", "batch"):
            raise ValueError("mode 必須是 live / batch")
        cfg = self.get_guild_cfg(guild_id)
        cfg.stream.mode = mode
        self._save_guild(guild_id)

    def set_stream_throttle(self, guild_id: int, ms: int):
        cfg = self.get_guild_cfg(guild_id)
        cfg.stream.throttle_ms = max(0, int(ms))
        self._save_guild(guild_id)

    def set_stream_chunk_limit(self, guild_id: int, n: int):
        cfg = self.get_guild_cfg(guild_id)
        cfg.stream.chunk_limit = max(200, int(n))
        self._save_guild(guild_id)

    def guilds_with_stream_channel(self) -> List[int]:
        ids: List[int] = []
        # 先看快取
        for gid, cfg in self.guild_cache.items():
            if cfg.stream_log_channel_id:
                ids.append(gid)
        # 再掃描磁碟補上未載入的
        for p in self.guilds_dir.glob("*.json"):
            try:
                gid = int(p.stem)
                if gid in self.guild_cache:
                    continue
                raw = json.loads(p.read_text(encoding="utf-8"))
                if raw.get("stream_log_channel_id", 0):
                    ids.append(gid)
                    # 載入到快取
                    self.guild_cache[gid] = self._load_guild(gid)
            except Exception:
                continue
        return ids

    # ---------- Global stream（新） ----------
    def get_global_stream_channel_id(self) -> int:
        return self.global_config.gstream_channel_id

    def set_global_stream_channel(self, channel_id: int):
        self.global_config.gstream_channel_id = int(channel_id)
        self._save_global()

    def clear_global_stream_channel(self):
        self.global_config.gstream_channel_id = 0
        self._save_global()

    def get_global_stream_settings(self) -> StreamSettings:
        return self.global_config.gstream

    def set_global_stream_mode(self, mode: str):
        if mode not in ("live", "batch"):
            raise ValueError("mode 必須是 live / batch")
        self.global_config.gstream.mode = mode
        self._save_global()

    def set_global_stream_throttle(self, ms: int):
        self.global_config.gstream.throttle_ms = max(0, int(ms))
        self._save_global()

    def set_global_stream_chunk_limit(self, n: int):
        self.global_config.gstream.chunk_limit = max(200, int(n))
        self._save_global()
