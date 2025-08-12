import json
from dataclasses import dataclass, asdict, field
from pathlib import Path
import logging

logger = logging.getLogger("trpg_bot")

@dataclass
class CritRules:
    d20_crit_success: int = 20
    d20_crit_failure: int = 1
    d100_crit_success: int = 1
    d100_crit_failure: int = 100

@dataclass
class BotConfig:
    log_channel_id: int = 0          # 記錄頻道（0 表示未設定）
    crit: CritRules = field(default_factory=CritRules)   # 大成敗規則

class ConfigManager:
    def __init__(self, path: str = "data/config.json"):
        self.path = Path(path)
        self.path.parent.mkdir(exist_ok=True)
        if not self.path.exists():
            self.config = BotConfig()
            self._save()
        else:
            self.config = self._load()

    def _load(self) -> BotConfig:
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            crit = raw.get("crit", {})
            return BotConfig(
                log_channel_id=raw.get("log_channel_id", 0),
                crit=CritRules(
                    d20_crit_success=crit.get("d20_crit_success", 20),
                    d20_crit_failure=crit.get("d20_crit_failure", 1),
                    d100_crit_success=crit.get("d100_crit_success", 1),
                    d100_crit_failure=crit.get("d100_crit_failure", 100),
                ),
            )
        except Exception as e:
            logger.error(f"讀取設定失敗，使用預設值：{e}")
            return BotConfig()

    def _save(self):
        payload = asdict(self.config)
        self.path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info("設定已儲存")

    def set_log_channel(self, channel_id: int):
        self.config.log_channel_id = channel_id
        self._save()

    def get_log_channel_id(self) -> int:
        return self.config.log_channel_id

    def get_crit_rules(self) -> CritRules:
        return self.config.crit
