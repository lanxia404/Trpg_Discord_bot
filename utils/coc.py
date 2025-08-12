# utils/coc.py
from dataclasses import dataclass
import random
import math

@dataclass
class CcResult:
    roll: int
    skill: int
    level: str             # "CRITICAL" | "EXTREME" | "HARD" | "REGULAR" | "FAIL" | "FUMBLE"
    is_crit: bool
    is_fumble: bool

def d100() -> int:
    # 1~100，00 視為 100
    return random.randint(1, 100)

def evaluate(skill: int, roll: int) -> CcResult:
    skill = max(0, min(99 if skill < 100 else 100, skill))  # 常見桌規：99 前正常、100 幾乎必失敗
    hard = math.floor(skill / 2)
    extreme = math.floor(skill / 5)

    is_crit = (roll == 1)  # 01
    # 7e 失手：技能<50 → 96-100；技能≥50 → 100
    is_fumble = (roll >= 96 and skill < 50) or (roll == 100 and skill >= 50)

    if is_crit:
        level = "大成功"
    elif roll <= extreme:
        level = "極限成功"
    elif roll <= hard:
        level = "困難成功"
    elif roll <= skill:
        level = "普通成功"
    elif is_fumble:
        level = "大失敗"
    else:
        level = "失敗"

    return CcResult(roll=roll, skill=skill, level=level, is_crit=is_crit, is_fumble=is_fumble)
