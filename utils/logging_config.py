import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

def setup_logging():
    Path("logs").mkdir(exist_ok=True)
    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    root = logging.getLogger()
    root.setLevel(logging.INFO)

    # 檔案
    fh = RotatingFileHandler("logs/bot.log", maxBytes=2_000_000, backupCount=3, encoding="utf-8")
    fh.setFormatter(formatter)
    root.addHandler(fh)

    # 終端
    sh = logging.StreamHandler()
    sh.setFormatter(formatter)
    root.addHandler(sh)
