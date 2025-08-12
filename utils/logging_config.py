# utils/logging_config.py
import logging
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path
import asyncio
import gzip
import os
import shutil
from datetime import datetime

LOG_QUEUE: asyncio.Queue[str] = asyncio.Queue()

class DiscordQueueHandler(logging.Handler):
    def emit(self, record: logging.LogRecord):
        try:
            msg = self.format(record)
            LOG_QUEUE.put_nowait(msg)
        except Exception:
            pass

def _gzip_rotator(source: str, dest: str):
    """把旋轉出的檔案壓成 .gz（dest 可能是預設名，這裡統一加 .gz）"""
    # 例：source=logs/latest.log.2025-08-13 → 轉成 logs/2025-08-13.log.gz
    base = Path(source).name  # latest.log.YYYY-MM-DD
    try:
        date_str = base.split(".")[-1]  # YYYY-MM-DD
        out = Path(source).with_name(f"{date_str}.log.gz")
    except Exception:
        out = Path(dest).with_suffix(".gz")

    with open(source, "rb") as f_in, gzip.open(out, "wb") as f_out:
        shutil.copyfileobj(f_in, f_out)
    os.remove(source)

def _namer(default_name: str):
    # 讓旋轉暫存名長成 logs/latest.log.YYYY-MM-DD（之後 rotator 會把它壓成 YYYY-MM-DD.log.gz）
    return default_name

def setup_logging():
    Path("logs").mkdir(exist_ok=True)
    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    root = logging.getLogger()
    root.setLevel(logging.INFO)

    # 檔案：latest.log（午夜輪替，保留 30 份，歷史自動 .gz）
    fh = TimedRotatingFileHandler(
        "logs/latest.log",
        when="midnight",
        backupCount=30,
        encoding="utf-8",
        utc=False,
    )
    # 預設命名：logs/latest.log.YYYY-MM-DD，後由 rotator 壓成 logs/YYYY-MM-DD.log.gz
    fh.namer = _namer
    fh.rotator = _gzip_rotator
    fh.setFormatter(formatter)
    root.addHandler(fh)

    # 終端
    sh = logging.StreamHandler()
    sh.setFormatter(formatter)
    root.addHandler(sh)

    # 丟到 Discord Queue（INFO 以上）
    qh = DiscordQueueHandler()
    qh.setFormatter(formatter)
    qh.setLevel(logging.INFO)
    root.addHandler(qh)

    # 開機時打一行，方便看分隔
    root.info("==== Bot started at %s ====", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
